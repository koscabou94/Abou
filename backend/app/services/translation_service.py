"""
Service de traduction - mode cloud simplifié.
En mode cloud (USE_LIGHTWEIGHT_MODE=True), renvoie le texte original sans traduction.
Le français est la langue principale du chatbot.
"""

import structlog
from app.services.language_service import LanguageService
from app.config import settings

logger = structlog.get_logger(__name__)


class TranslationService:
    """
    Service de traduction simplifié pour le déploiement cloud.
    La traduction lourde (NLLB-200) est désactivée ; le chatbot fonctionne
    principalement en français avec détection de langue côté client.
    """

    def __init__(self, language_service: LanguageService) -> None:
        self.language_service = language_service
        logger.info("Service de traduction initialisé (mode passthrough cloud)")

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Retourne le texte tel quel (traduction lourde désactivée en cloud)."""
        return text

    async def translate_to_pivot(self, text: str, source_lang: str) -> str:
        """Retourne le texte tel quel (pas de traduction en mode cloud)."""
        return text

    async def translate_from_pivot(self, text: str, target_lang: str) -> str:
        """Retourne le texte tel quel (pas de traduction en mode cloud)."""
        return text

    async def batch_translate(self, texts: list, source_lang: str, target_lang: str) -> list:
        return texts

    @property
    def is_available(self) -> bool:
        return False
