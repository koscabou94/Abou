"""Tests pour le service NLP (classification d'intention)."""

import pytest
from app.services.nlp_service import NLPService


@pytest.fixture
def nlp_service():
    return NLPService()


class TestIntentClassification:
    """Tests de la classification d'intention par mots-clés."""

    def test_inscription_intent(self, nlp_service):
        intent, confidence = nlp_service.classify_intent(
            "Comment s'inscrire à l'école primaire ?"
        )
        assert intent == "inscription"
        assert confidence > 0.5

    def test_examen_intent(self, nlp_service):
        intent, confidence = nlp_service.classify_intent(
            "Quand sont les résultats du BFEM ?"
        )
        assert intent == "examen"
        assert confidence > 0.5

    def test_bourse_intent(self, nlp_service):
        intent, confidence = nlp_service.classify_intent(
            "Je cherche une bourse pour financer mes études"
        )
        assert intent == "bourse"
        assert confidence > 0.5

    def test_calendrier_intent(self, nlp_service):
        intent, confidence = nlp_service.classify_intent(
            "Quand est la rentrée scolaire ? Quelle est la date des vacances ?"
        )
        assert intent == "calendrier"
        assert confidence > 0.5

    def test_orientation_intent(self, nlp_service):
        intent, confidence = nlp_service.classify_intent(
            "Quelle filière choisir après le BFEM ?"
        )
        assert intent == "orientation"
        assert confidence > 0.5

    def test_programme_intent(self, nlp_service):
        intent, confidence = nlp_service.classify_intent(
            "Quel est le programme de mathématiques en cours moyen ?"
        )
        assert intent == "programme"
        assert confidence > 0.5

    def test_administratif_intent(self, nlp_service):
        intent, confidence = nlp_service.classify_intent(
            "Comment obtenir une attestation de scolarité ?"
        )
        assert intent == "administratif"
        assert confidence > 0.5

    def test_enseignant_intent(self, nlp_service):
        intent, confidence = nlp_service.classify_intent(
            "Comment devenir professeur au Sénégal ? Concours enseignant FASTEF"
        )
        assert intent == "enseignant"
        assert confidence > 0.5

    def test_general_intent_for_unrelated(self, nlp_service):
        intent, confidence = nlp_service.classify_intent(
            "Bonjour, comment allez-vous ?"
        )
        assert intent == "general"
        assert confidence == 0.5

    def test_empty_text(self, nlp_service):
        intent, confidence = nlp_service.classify_intent("")
        assert intent == "general"
        assert confidence == 0.5

    def test_confidence_bounded(self, nlp_service):
        """La confiance doit toujours être entre 0 et 1."""
        for text in [
            "inscription dossier formulaire nouveau matricule enregistrement",
            "bonjour",
            "",
        ]:
            _, confidence = nlp_service.classify_intent(text)
            assert 0 <= confidence <= 1


class TestFallbackResponses:
    """Tests des réponses de secours."""

    def test_fallback_for_known_intents(self, nlp_service):
        for intent in ["inscription", "examen", "bourse"]:
            response = nlp_service._get_fallback_response(intent)
            assert len(response) > 20

    def test_fallback_for_general(self, nlp_service):
        response = nlp_service._get_fallback_response("general")
        assert "désolé" in response.lower() or "difficultés" in response.lower()

    def test_fallback_for_unknown_intent(self, nlp_service):
        response = nlp_service._get_fallback_response("unknown_intent")
        assert len(response) > 10
