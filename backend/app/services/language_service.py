"""
Service de gestion de langue — uniquement le français.
"""

import structlog

logger = structlog.get_logger(__name__)


class LanguageService:
    """Service de langue simplifié — français uniquement."""

    LANGUAGE_MAP: dict[str, str] = {
        "fr": "fra_Latn",
    }

    REVERSE_MAP: dict[str, str] = {v: k for k, v in LANGUAGE_MAP.items()}

    def __init__(self) -> None:
        logger.info("Service de langue initialisé", supported_languages=["fr"])

    def detect_language(self, text: str) -> str:
        return "fr"

    def get_nllb_code(self, lang_code: str) -> str:
        return "fra_Latn"

    def get_iso_code(self, nllb_code: str) -> str:
        return "fr"

    def is_supported(self, lang_code: str) -> bool:
        return lang_code == "fr"

    def get_language_name(self, lang_code: str) -> str:
        return "Français"
