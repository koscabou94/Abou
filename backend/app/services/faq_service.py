"""
Service de gestion des FAQ avec recherche sémantique.
- Avec JINA_API_KEY : embeddings Jina AI (recherche par sens, multilingue)
- Sans clé : TF-IDF scikit-learn (fallback) + normalisation + synonymes + fuzzy
"""

import json
import asyncio
from typing import Optional
import structlog

from app.config import settings
# Réutilise les utilitaires de PlaneteFAQService pour la cohérence
from app.services.planete_faq_service import (
    normalize_text,
    expand_query_with_synonyms,
)

logger = structlog.get_logger(__name__)


class FAQService:
    """
    Service de FAQ avec correspondance sémantique.
    Utilise Jina AI embeddings si disponible, TF-IDF sinon.
    """

    def __init__(self, embedding_service=None) -> None:
        self._embedding_service = embedding_service
        self._vectorizer = None
        self._tfidf_matrix = None
        self._faq_cache: list = []
        self._faq_embeddings: list = []   # embeddings Jina des questions
        self._model_loaded = False
        self._loading_lock = asyncio.Lock()
        logger.info("Service FAQ initialisé (TF-IDF)")

    def set_embedding_service(self, embedding_service) -> None:
        self._embedding_service = embedding_service

    # ─────────────────────────────────────────────────────────────────
    # CHARGEMENT
    # ─────────────────────────────────────────────────────────────────

    def _load_vectorizer(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer = TfidfVectorizer(
            analyzer='word',
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )

    def _fit_faqs(self) -> None:
        if not self._faq_cache or self._vectorizer is None:
            return
        # On indexe les questions enrichies : question + keywords + synonymes,
        # le tout normalisé (sans accents, minuscules) pour matcher les
        # reformulations utilisateurs de manière robuste.
        questions = []
        for faq in self._faq_cache:
            base = faq.get("question", "") + " " + " ".join(faq.get("keywords", []))
            normalized = normalize_text(base)
            expanded = expand_query_with_synonyms(normalized)
            questions.append(expanded)
        self._tfidf_matrix = self._vectorizer.fit_transform(questions)
        logger.info("TF-IDF entraîné (normalisé + synonymes)", faq_count=len(self._faq_cache))

    async def _ensure_model_loaded(self) -> bool:
        if self._model_loaded:
            return True
        async with self._loading_lock:
            if self._model_loaded:
                return True
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._load_vectorizer)
                self._model_loaded = True
                logger.info("Vectorizer TF-IDF chargé")
                return True
            except Exception as exc:
                logger.error("Échec chargement TF-IDF", error=str(exc))
                return False

    async def _build_jina_embeddings(self) -> None:
        """Génère les embeddings Jina pour toutes les FAQ (appelé après le chargement)."""
        if not self._embedding_service or not self._embedding_service.is_jina_enabled:
            return
        if not self._faq_cache:
            return
        try:
            questions = [
                faq.get("question", "") + " " + " ".join(faq.get("keywords", []))
                for faq in self._faq_cache
            ]
            embeddings = await self._embedding_service.embed_texts(questions)
            if embeddings and len(embeddings) == len(self._faq_cache):
                self._faq_embeddings = embeddings
                logger.info("Embeddings Jina FAQ générés", count=len(embeddings))
            else:
                logger.warning("Échec génération embeddings FAQ, fallback TF-IDF")
                self._faq_embeddings = []
        except Exception as exc:
            logger.error("Erreur génération embeddings FAQ", error=str(exc))
            self._faq_embeddings = []

    async def load_faqs(self, db) -> int:
        try:
            from sqlalchemy import select
            from app.database.models import FAQ
            stmt = select(FAQ).where(FAQ.is_active == True)
            result = await db.execute(stmt)
            faqs = result.scalars().all()
            self._faq_cache = [
                {
                    "id": f.id,
                    "question": f.question,
                    "answer": f.answer,
                    "category": f.category,
                    "keywords": f.keywords or [],
                }
                for f in faqs
            ]
            await self._ensure_model_loaded()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._fit_faqs)
            await self._build_jina_embeddings()
            logger.info("FAQ chargées en cache", count=len(self._faq_cache))
            return len(self._faq_cache)
        except Exception as exc:
            logger.error("Erreur chargement FAQ", error=str(exc))
            return 0

    async def seed_from_json(self, json_path: str, db) -> int:
        try:
            import os
            if not os.path.exists(json_path):
                logger.warning("Fichier FAQ introuvable", path=json_path)
                return 0
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            faqs_data = data.get("faqs", [])
            if not faqs_data:
                return 0
            from app.database.models import FAQ
            count = 0
            for faq_item in faqs_data:
                faq = FAQ(
                    question=faq_item.get("question", ""),
                    answer=faq_item.get("answer", ""),
                    category=faq_item.get("category", "general"),
                    keywords=faq_item.get("keywords", []),
                    language=faq_item.get("language", "fr"),
                    is_active=True,
                )
                db.add(faq)
                count += 1
            await db.commit()
            await self.load_faqs(db)
            logger.info("FAQ importées depuis JSON", count=count)
            return count
        except Exception as exc:
            logger.error("Erreur import FAQ JSON", error=str(exc))
            return 0

    async def load_from_json_direct(self, json_path: str) -> int:
        """Charge les FAQ depuis JSON en mémoire (fallback BD inaccessible)."""
        import os
        try:
            if not os.path.exists(json_path):
                logger.warning("Fichier FAQ introuvable", path=json_path)
                return 0
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            faqs_data = data.get("faqs", [])
            self._faq_cache = [
                {
                    "id": i + 1,
                    "question": f.get("question", ""),
                    "answer": f.get("answer", ""),
                    "category": f.get("category", "general"),
                    "keywords": f.get("keywords", []),
                }
                for i, f in enumerate(faqs_data)
                if f.get("question") and f.get("answer")
            ]
            await self._ensure_model_loaded()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._fit_faqs)
            # Générer les embeddings Jina pour les FAQ
            await self._build_jina_embeddings()
            logger.info("FAQ chargées depuis JSON (fallback)", count=len(self._faq_cache))
            return len(self._faq_cache)
        except Exception as exc:
            logger.error("Erreur chargement FAQ JSON direct", error=str(exc))
            return 0

    # ─────────────────────────────────────────────────────────────────
    # RECHERCHE
    # ─────────────────────────────────────────────────────────────────

    async def find_best_match(self, query: str, language: str = "fr") -> Optional[dict]:
        """
        Trouve la meilleure FAQ correspondant à la requête.
        Utilise Jina AI si disponible, sinon TF-IDF.
        """
        if not self._faq_cache:
            return None

        # ── Mode Jina AI (sémantique) ──
        if (self._embedding_service
                and self._embedding_service.is_jina_enabled
                and self._faq_embeddings
                and len(self._faq_embeddings) == len(self._faq_cache)):
            return await self._find_match_jina(query)

        # ── Mode TF-IDF (fallback) ──
        return await self._find_match_tfidf(query)

    async def _find_match_jina(self, query: str) -> Optional[dict]:
        """Recherche sémantique via embeddings Jina."""
        try:
            import numpy as np
            query_vec = await self._embedding_service.embed_query_jina(query)
            if query_vec is None:
                return await self._find_match_tfidf(query)

            scores = self._embedding_service.cosine_similarity_batch(
                query_vec, self._faq_embeddings
            )
            best_idx = int(np.argmax(scores))
            best_score = float(scores[best_idx])

            # Seuil plus bas pour les embeddings (plus précis que TF-IDF)
            JINA_THRESHOLD = 0.45
            if best_score < JINA_THRESHOLD:
                return None

            faq = self._faq_cache[best_idx]
            logger.info(
                "Réponse FAQ trouvée (Jina)",
                score=round(best_score, 3),
                faq_id=faq.get("id"),
                category=faq.get("category"),
            )
            return {**faq, "score": best_score}
        except Exception as exc:
            logger.error("Erreur recherche Jina FAQ", error=str(exc))
            return await self._find_match_tfidf(query)

    async def _find_match_tfidf(self, query: str) -> Optional[dict]:
        """Recherche TF-IDF avec normalisation + synonymes + fuzzy."""
        if self._tfidf_matrix is None:
            return None
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            model_ok = await self._ensure_model_loaded()
            if not model_ok or self._vectorizer is None:
                return None

            # Normaliser et étendre la requête avec les synonymes (les
            # questions FAQ sont elles-mêmes indexées avec ce traitement).
            q_expanded = expand_query_with_synonyms(query)
            query_vec = self._vectorizer.transform([q_expanded])
            tfidf_scores = cosine_similarity(query_vec, self._tfidf_matrix).flatten()

            # Fuzzy matching question vs requête (rattrape les fautes de frappe)
            fuzzy_scores = self._compute_fuzzy_scores(query)

            # Combinaison : 75% TF-IDF + 25% fuzzy
            combined = 0.75 * tfidf_scores + 0.25 * fuzzy_scores

            best_idx = int(np.argmax(combined))
            best_score = float(combined[best_idx])

            if best_score < settings.FAQ_MATCH_THRESHOLD:
                return None

            faq = self._faq_cache[best_idx]
            logger.debug(
                "FAQ match TF-IDF",
                score=round(best_score, 3),
                tfidf=round(float(tfidf_scores[best_idx]), 3),
                fuzzy=round(float(fuzzy_scores[best_idx]), 3),
                faq_id=faq.get("id"),
            )
            return {**faq, "score": best_score}
        except Exception as exc:
            logger.error("Erreur recherche FAQ TF-IDF", error=str(exc))
            return None

    def _compute_fuzzy_scores(self, query: str):
        """Calcule un score fuzzy [0..1] entre la requête et chaque FAQ.
        Utilise rapidfuzz si dispo, sinon fallback Jaccard sur les mots."""
        import numpy as np
        q_norm = normalize_text(query)
        scores = np.zeros(len(self._faq_cache), dtype=float)

        try:
            from rapidfuzz import fuzz
            for i, faq in enumerate(self._faq_cache):
                qn = normalize_text(faq.get("question", ""))
                scores[i] = fuzz.token_set_ratio(q_norm, qn) / 100.0
        except ImportError:
            q_words = set(q_norm.split())
            for i, faq in enumerate(self._faq_cache):
                w = set(normalize_text(faq.get("question", "")).split())
                if not q_words or not w:
                    continue
                inter = len(q_words & w)
                union = len(q_words | w)
                scores[i] = inter / union if union else 0.0
        return scores

    # ─────────────────────────────────────────────────────────────────
    # UTILITAIRES
    # ─────────────────────────────────────────────────────────────────

    async def get_all_faqs(self, category: Optional[str] = None) -> list:
        if category:
            return [f for f in self._faq_cache if f.get("category") == category]
        return self._faq_cache

    async def get_faq_by_id(self, faq_id: int, db) -> Optional[dict]:
        try:
            from sqlalchemy import select
            from app.database.models import FAQ
            stmt = select(FAQ).where(FAQ.id == faq_id)
            result = await db.execute(stmt)
            faq = result.scalar_one_or_none()
            if faq:
                return {
                    "id": faq.id,
                    "question": faq.question,
                    "answer": faq.answer,
                    "category": faq.category,
                    "keywords": faq.keywords or [],
                    "view_count": faq.view_count or 0,
                }
            return None
        except Exception as exc:
            logger.error("Erreur récupération FAQ", error=str(exc))
            return None
