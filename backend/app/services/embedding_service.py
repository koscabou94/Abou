"""
Service d'embeddings sémantiques via Jina AI API.
Remplace TF-IDF par une recherche par sens (plus intelligente).
Fallback automatique sur TF-IDF si la clé API n'est pas configurée.

Jina AI : https://jina.ai — 1 million de tokens/mois GRATUIT
"""

import asyncio
import numpy as np
import structlog
from typing import Optional

logger = structlog.get_logger(__name__)

JINA_API_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v3"


class EmbeddingService:
    """
    Service d'embeddings sémantiques.
    - Avec JINA_API_KEY : embeddings de haute qualité (multilingues, par sens)
    - Sans clé : fallback TF-IDF automatique
    """

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key.strip()
        self._use_jina = bool(self.api_key)
        self._tfidf_vectorizer = None
        self._lock = asyncio.Lock()

        if self._use_jina:
            logger.info("EmbeddingService: mode Jina AI (sémantique)", model=JINA_MODEL)
        else:
            logger.info("EmbeddingService: mode TF-IDF (fallback, pas de JINA_API_KEY)")

    @property
    def is_jina_enabled(self) -> bool:
        return self._use_jina

    # ─────────────────────────────────────────────────────────────────
    # API PUBLIQUE
    # ─────────────────────────────────────────────────────────────────

    async def embed_texts(self, texts: list[str]) -> Optional[list[list[float]]]:
        """
        Génère des embeddings pour une liste de textes.
        Retourne une liste de vecteurs flottants, ou None en cas d'erreur.
        """
        if not texts:
            return []

        if self._use_jina:
            return await self._jina_embed(texts)
        return None  # Le mode TF-IDF est géré directement dans FAQService / KnowledgeService

    async def embed_query(self, query: str) -> Optional[list[float]]:
        """
        Génère un embedding pour une requête unique.
        """
        result = await self.embed_texts([query])
        if result and len(result) > 0:
            return result[0]
        return None

    @staticmethod
    def cosine_similarity_batch(query_vec: list[float], corpus_vecs: list[list[float]]) -> list[float]:
        """
        Calcule la similarité cosinus entre un vecteur requête et un corpus.
        Retourne la liste des scores (float entre -1 et 1).
        """
        q = np.array(query_vec, dtype=np.float32)
        C = np.array(corpus_vecs, dtype=np.float32)

        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return [0.0] * len(corpus_vecs)

        C_norms = np.linalg.norm(C, axis=1)
        C_norms[C_norms == 0] = 1e-8

        scores = (C @ q) / (C_norms * q_norm)
        return scores.tolist()

    # ─────────────────────────────────────────────────────────────────
    # JINA AI
    # ─────────────────────────────────────────────────────────────────

    async def _jina_embed(self, texts: list[str]) -> Optional[list[list[float]]]:
        """Appelle l'API Jina AI pour générer des embeddings."""
        try:
            import httpx

            # Jina accepte max 2048 textes par appel — on découpe si nécessaire
            all_embeddings = []
            batch_size = 128

            async with httpx.AsyncClient(timeout=30.0) as client:
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i + batch_size]
                    response = await client.post(
                        JINA_API_URL,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": JINA_MODEL,
                            "input": batch,
                            "task": "retrieval.passage",  # optimisé pour la recherche
                            "dimensions": 512,            # compact mais précis
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    batch_embeddings = [item["embedding"] for item in data["data"]]
                    all_embeddings.extend(batch_embeddings)

            logger.debug("Jina embeddings générés", count=len(all_embeddings))
            return all_embeddings

        except Exception as exc:
            logger.error("Erreur Jina AI embed", error=str(exc))
            return None

    async def embed_query_jina(self, query: str) -> Optional[list[float]]:
        """Embedding optimisé pour les requêtes (task=retrieval.query)."""
        if not self._use_jina:
            return None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    JINA_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": JINA_MODEL,
                        "input": [query],
                        "task": "retrieval.query",
                        "dimensions": 512,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]
        except Exception as exc:
            logger.error("Erreur Jina query embed", error=str(exc))
            return None
