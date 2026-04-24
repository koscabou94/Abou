"""
Service de gestion des FAQ avec recherche sémantique TF-IDF (scikit-learn).
Remplace sentence-transformers pour éviter les dépendances ML lourdes.
"""

import json
import asyncio
from typing import Optional
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class FAQService:
    """
    Service de FAQ avec correspondance sémantique TF-IDF + similarité cosinus.
    Utilise scikit-learn, sans GPU ni modèle lourd à télécharger.
    """

    def __init__(self) -> None:
        self._vectorizer = None
        self._tfidf_matrix = None
        self._faq_cache: list = []
        self._model_loaded = False
        self._loading_lock = asyncio.Lock()
        logger.info("Service FAQ initialisé (TF-IDF)")

    def _load_vectorizer(self) -> None:
        """Charge le vectorizer TF-IDF (synchrone, très rapide)."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer = TfidfVectorizer(
            analyzer='word',
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )

    def _fit_faqs(self) -> None:
        """Entraîne le TF-IDF sur les FAQ chargées."""
        if not self._faq_cache or self._vectorizer is None:
            return
        questions = [faq.get("question", "") + " " + " ".join(faq.get("keywords", [])) for faq in self._faq_cache]
        self._tfidf_matrix = self._vectorizer.fit_transform(questions)
        logger.info("TF-IDF entraîné", faq_count=len(self._faq_cache))

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

    async def load_faqs(self, db) -> int:
        """Charge les FAQ depuis la base de données en cache."""
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
            logger.info("FAQ chargées en cache", count=len(self._faq_cache))
            return len(self._faq_cache)
        except Exception as exc:
            logger.error("Erreur chargement FAQ", error=str(exc))
            return 0

    async def seed_from_json(self, json_path: str, db) -> int:
        """Importe les FAQ depuis un fichier JSON vers la base de données."""
        try:
            import os
            if not os.path.exists(json_path):
                logger.warning("Fichier FAQ introuvable", path=json_path)
                return 0

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            faqs_data = data.get("faqs", [])
            if not faqs_data:
                logger.warning("Aucune FAQ dans le fichier JSON")
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

            # Recharger le cache
            await self.load_faqs(db)
            logger.info("FAQ importées depuis JSON", count=count)
            return count

        except Exception as exc:
            logger.error("Erreur import FAQ JSON", error=str(exc))
            return 0

    async def find_best_match(self, query: str, language: str = "fr") -> Optional[dict]:
        """
        Trouve la meilleure FAQ correspondant à la requête via TF-IDF.
        """
        if not self._faq_cache or self._tfidf_matrix is None:
            return None

        try:
            model_ok = await self._ensure_model_loaded()
            if not model_ok or self._vectorizer is None:
                return None

            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            query_vec = self._vectorizer.transform([query])
            scores = cosine_similarity(query_vec, self._tfidf_matrix).flatten()
            best_idx = int(np.argmax(scores))
            best_score = float(scores[best_idx])

            if best_score < settings.FAQ_MATCH_THRESHOLD:
                return None

            faq = self._faq_cache[best_idx]
            logger.debug("FAQ match trouvé", score=best_score, faq_id=faq.get("id"))
            return {**faq, "score": best_score}

        except Exception as exc:
            logger.error("Erreur recherche FAQ", error=str(exc))
            return None

    async def get_all_faqs(self, category: Optional[str] = None) -> list:
        """Retourne toutes les FAQ (filtrées par catégorie si précisé)."""
        if category:
            return [f for f in self._faq_cache if f.get("category") == category]
        return self._faq_cache

    async def get_faq_by_id(self, faq_id: int, db) -> Optional[dict]:
        """Récupère une FAQ par son ID."""
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
