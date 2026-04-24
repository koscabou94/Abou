"""Tests pour le service de détection de langue."""

import pytest
from app.services.language_service import LanguageService


@pytest.fixture
def lang_service():
    return LanguageService()


class TestLanguageDetection:
    """Tests de détection de langue."""

    def test_french_detected(self, lang_service):
        """Le français doit être détecté pour du texte français."""
        result = lang_service.detect_language("Comment s'inscrire à l'école primaire ?")
        assert result == "fr"

    def test_wolof_detected(self, lang_service):
        """Le wolof doit être détecté avec assez de mots-clés wolof."""
        result = lang_service.detect_language("Maa ngi dëkk ci Dakar ak sama xale yi")
        assert result == "wo"

    def test_arabic_detected(self, lang_service):
        """L'arabe doit être détecté par son script."""
        result = lang_service.detect_language("كيف يمكنني تسجيل ابني في المدرسة")
        assert result == "ar"

    def test_pulaar_detected(self, lang_service):
        """Le pulaar doit être détecté avec assez de mots-clés pulaar."""
        result = lang_service.detect_language("Mi yidam jannde waawi ɗum ko gooto")
        assert result == "ff"

    def test_empty_text_defaults_to_french(self, lang_service):
        """Un texte vide doit renvoyer le français par défaut."""
        assert lang_service.detect_language("") == "fr"
        assert lang_service.detect_language("ab") == "fr"

    def test_short_text_defaults_to_french(self, lang_service):
        """Un texte très court doit renvoyer le français par défaut."""
        assert lang_service.detect_language("ok") == "fr"


class TestNLLBCodes:
    """Tests des codes de langue NLLB-200."""

    def test_french_nllb_code(self, lang_service):
        assert lang_service.get_nllb_code("fr") == "fra_Latn"

    def test_wolof_nllb_code(self, lang_service):
        assert lang_service.get_nllb_code("wo") == "wol_Latn"

    def test_arabic_nllb_code(self, lang_service):
        assert lang_service.get_nllb_code("ar") == "arb_Arab"

    def test_pulaar_nllb_code(self, lang_service):
        assert lang_service.get_nllb_code("ff") == "fuf_Latn"

    def test_unknown_defaults_to_french(self, lang_service):
        assert lang_service.get_nllb_code("xx") == "fra_Latn"

    def test_reverse_mapping(self, lang_service):
        assert lang_service.get_iso_code("fra_Latn") == "fr"
        assert lang_service.get_iso_code("wol_Latn") == "wo"


class TestLanguageSupport:
    """Tests de la validation des langues supportées."""

    def test_supported_languages(self, lang_service):
        assert lang_service.is_supported("fr") is True
        assert lang_service.is_supported("wo") is True
        assert lang_service.is_supported("ff") is True
        assert lang_service.is_supported("ar") is True

    def test_unsupported_language(self, lang_service):
        assert lang_service.is_supported("en") is False
        assert lang_service.is_supported("xx") is False

    def test_language_names(self, lang_service):
        assert lang_service.get_language_name("fr") == "Français"
        assert lang_service.get_language_name("wo") == "Wolof"
        assert lang_service.get_language_name("ff") == "Pulaar"
        assert lang_service.get_language_name("ar") == "Arabe"
