"""
Service de recherche dans la base de connaissances éducatives.
- Avec JINA_API_KEY : embeddings sémantiques (recherche par sens)
- Sans clé : TF-IDF (fallback)
"""

import json
import os
import asyncio
from typing import Optional
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class KnowledgeService:
    """
    Service de recherche dans la base de connaissances éducatives.
    Charge les documents depuis knowledge_base.json.
    Utilise Jina AI embeddings si disponible, TF-IDF sinon.
    """

    def __init__(self, faq_service=None, embedding_service=None) -> None:
        self._documents: list = []
        self._vectorizer = None
        self._tfidf_matrix = None
        self._doc_embeddings: list = []
        self._embedding_service = embedding_service
        self._loaded = False
        logger.info("Service de connaissances initialisé (TF-IDF)")

    def set_embedding_service(self, embedding_service) -> None:
        self._embedding_service = embedding_service

    async def initialize(self) -> bool:
        if self._loaded:
            return True
        try:
            documents = self._load_documents()
            if not documents:
                logger.warning("Aucun document dans la base de connaissances")
                return False
            self._documents = documents

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._fit_tfidf)

            # Générer les embeddings Jina si disponible
            await self._build_jina_embeddings()

            self._loaded = True
            logger.info("Base de connaissances prête", documents=len(self._documents))
            return True
        except Exception as exc:
            logger.error("Erreur chargement KB", error=str(exc))
            return False

    def _load_documents(self) -> list:
        candidate_paths = [
            "/data/knowledge_base.json",
            settings.KNOWLEDGE_BASE_PATH,
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "knowledge_base.json"
            ),
        ]
        path = next((p for p in candidate_paths if os.path.exists(p)), None)
        if not path:
            logger.warning("knowledge_base.json introuvable")
            return []

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entries = data.get("entries", data.get("knowledge", []))
        documents = []
        for entry in entries:
            content = entry.get("content", "")
            if content:
                documents.append({
                    "title": entry.get("title", ""),
                    "content": content,
                    "category": entry.get("category", "general"),
                    "tags": entry.get("tags", []),
                    "search_text": f"{entry.get('title', '')} {content}",
                })
        return documents

    def _fit_tfidf(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer = TfidfVectorizer(
            analyzer='word',
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        texts = [doc["search_text"] for doc in self._documents]
        self._tfidf_matrix = self._vectorizer.fit_transform(texts)

    async def _build_jina_embeddings(self) -> None:
        """Génère les embeddings Jina pour tous les documents KB."""
        if not self._embedding_service or not self._embedding_service.is_jina_enabled:
            return
        if not self._documents:
            return
        try:
            texts = [doc["search_text"] for doc in self._documents]
            embeddings = await self._embedding_service.embed_texts(texts)
            if embeddings and len(embeddings) == len(self._documents):
                self._doc_embeddings = embeddings
                logger.info("Embeddings Jina KB générés", count=len(embeddings))
            else:
                logger.warning("Échec génération embeddings KB, fallback TF-IDF")
                self._doc_embeddings = []
        except Exception as exc:
            logger.error("Erreur génération embeddings KB", error=str(exc))
            self._doc_embeddings = []

    # ─────────────────────────────────────────────────────────────────
    # RECHERCHE
    # ─────────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        limit: int = 3,
        threshold: float = 0.05,
        category: Optional[str] = None
    ) -> list:
        if not self._loaded or not self._documents:
            return []

        # ── Mode Jina AI ──
        if (self._embedding_service
                and self._embedding_service.is_jina_enabled
                and self._doc_embeddings
                and len(self._doc_embeddings) == len(self._documents)):
            return await self._search_jina(query, limit, threshold, category)

        # ── Mode TF-IDF ──
        return await self._search_tfidf(query, limit, threshold, category)

    async def _search_jina(self, query: str, limit: int, threshold: float, category: Optional[str]) -> list:
        """Recherche sémantique via embeddings Jina."""
        try:
            import numpy as np
            query_vec = await self._embedding_service.embed_query_jina(query)
            if query_vec is None:
                return await self._search_tfidf(query, limit, threshold, category)

            scores = self._embedding_service.cosine_similarity_batch(
                query_vec, self._doc_embeddings
            )
            sorted_indices = np.argsort(scores)[::-1]

            JINA_KB_THRESHOLD = 0.35
            results = []
            for idx in sorted_indices:
                if len(results) >= limit:
                    break
                score = float(scores[idx])
                if score < JINA_KB_THRESHOLD:
                    break
                doc = self._documents[idx]
                if category and doc.get("category") != category:
                    continue
                result = {k: v for k, v in doc.items() if k != "search_text"}
                result["score"] = score
                results.append(result)

            return results
        except Exception as exc:
            logger.error("Erreur recherche Jina KB", error=str(exc))
            return await self._search_tfidf(query, limit, threshold, category)

    async def _search_tfidf(self, query: str, limit: int, threshold: float, category: Optional[str]) -> list:
        """Recherche TF-IDF (fallback)."""
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            query_vec = self._vectorizer.transform([query])
            scores = cosine_similarity(query_vec, self._tfidf_matrix).flatten()
            sorted_indices = np.argsort(scores)[::-1]

            results = []
            for idx in sorted_indices:
                if len(results) >= limit:
                    break
                score = float(scores[idx])
                if score < threshold:
                    break
                doc = self._documents[idx]
                if category and doc.get("category") != category:
                    continue
                result = {k: v for k, v in doc.items() if k != "search_text"}
                result["score"] = score
                results.append(result)

            return results
        except Exception as exc:
            logger.error("Erreur recherche KB TF-IDF", error=str(exc))
            return self._text_search(query, limit, category)

    def _text_search(self, query: str, limit: int, category: Optional[str]) -> list:
        query_words = set(query.lower().split())
        results = []
        for doc in self._documents:
            if category and doc.get("category") != category:
                continue
            doc_words = set(doc["search_text"].lower().split())
            overlap = len(query_words & doc_words)
            if overlap > 0:
                result = {k: v for k, v in doc.items() if k != "search_text"}
                result["score"] = overlap / max(len(query_words), 1)
                results.append(result)
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_context_for_llm(self, documents: list, max_chars: int = 1000) -> str:
        if not documents:
            return ""
        parts = []
        for doc in documents[:2]:
            title = doc['title'].replace("**", "").strip()
            content = doc['content']
            if len(content) > max_chars:
                cut = content[:max_chars]
                last_period = max(cut.rfind('.'), cut.rfind('\n'))
                content = cut[:last_period + 1] if last_period > 200 else cut + "..."
            parts.append(f"### {title}\n{content}")

        if parts:
            return (
                "Contexte documentaire (reformule avec tes mots, réponds à la question posée) :\n\n"
                + "\n\n".join(parts)
            )
        return ""

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def is_available(self) -> bool:
        return self._loaded and len(self._documents) > 0
