"""
Tests unitaires du classifier d'intent (Sprint 1 — refonte coeur).

Focus sur le FALLBACK HEURISTIQUE qui marche sans Groq (utilisable en CI).
Les tests LLM-based ne sont executes que si GROQ_API_KEY est definie.

Lance :
    cd backend && pytest tests/test_intent_classifier.py -v
"""

import os
import sys
import pytest

# S'assurer que le backend est dans le path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))


# Eviter de charger app.config (qui plante avec un .env Postgres legacy)
# en testant uniquement la classe IntentClassifier de maniere isolee
from app.services.intent_classifier import (  # noqa: E402
    IntentClassifier,
    IntentResult,
    VALID_INTENTS,
)


@pytest.fixture
def classifier():
    return IntentClassifier()


# ─────────────────────────────────────────────────────────
# TESTS DU FALLBACK HEURISTIQUE (sans LLM)
# ─────────────────────────────────────────────────────────

GREETING_CASES = [
    "Bonjour",
    "Salut",
    "bonsoir",
    "Hello",
    "Coucou EduBot",
]

SMALLTALK_CASES = [
    "Merci beaucoup",
    "Au revoir",
    "comment ça va ?",
    "ça va bien",
]

EXERCISE_EXPLICIT_CASES = [
    "Donne-moi 3 exercices de maths CM2",
    "Fais-moi un exercice de français",
    "Je veux des exos de physique",
    "Génère 5 exercices de SVT en 3ème",
    "Des devoirs de calcul pour le CE1",
    "Entraînement en lecture",
]

PLANETE_CASES = [
    "Comment me connecter à PLANETE ?",
    "PLANETE me bloque",
    "L'URL planete3.education.sn ne marche pas",
    "Mon compte simen est bloqué",
]

QUESTION_CASES = [
    "Quel est le programme de maths CM2 ?",
    "Comment ça marche le BFEM ?",
    "Pourquoi le CFEE existe ?",
    "Quand commence l'année scolaire ?",
]

EXPLAIN_CASES = [
    "Comment expliquer la photosynthèse ?",
    "Aide-moi à expliquer les fractions",
]

UNCLEAR_CASES = [
    "Aide-moi",
    "J'ai besoin",
    "asdfgh",
]

CORRECTION_CASES = [
    "Donne-moi les corrigés",
    "Les corrections s'il te plaît",
    "Tu peux corriger ces exercices ?",
    "Donne les solutions",
    "Les réponses des exercices",
    "Donne-moi le corrigé",
]


@pytest.mark.parametrize("msg", GREETING_CASES)
def test_heuristic_greeting(classifier, msg):
    """Une salutation doit etre classee 'greeting'."""
    result = classifier._classify_heuristic(msg, user_context=None)
    assert result.primary_intent == "greeting", (
        f"'{msg}' devrait etre 'greeting', got '{result.primary_intent}'"
    )
    assert result.confidence >= 0.7


@pytest.mark.parametrize("msg", SMALLTALK_CASES)
def test_heuristic_smalltalk(classifier, msg):
    """Une conversation courtoise doit etre classee 'smalltalk' (ou greeting)."""
    result = classifier._classify_heuristic(msg, user_context=None)
    assert result.primary_intent in ("smalltalk", "greeting"), (
        f"'{msg}' devrait etre smalltalk/greeting, got '{result.primary_intent}'"
    )


@pytest.mark.parametrize("msg", EXERCISE_EXPLICIT_CASES)
def test_heuristic_exercise_explicit(classifier, msg):
    """Une demande EXPLICITE d'exercice doit etre classee 'exercise_request'."""
    result = classifier._classify_heuristic(msg, user_context=None)
    assert result.primary_intent == "exercise_request", (
        f"'{msg}' devrait etre 'exercise_request', got '{result.primary_intent}'"
    )


@pytest.mark.parametrize("msg", CORRECTION_CASES)
def test_heuristic_correction(classifier, msg):
    """Demande de corriges -> 'correction_request' (jamais exercise_request)."""
    result = classifier._classify_heuristic(msg, user_context=None)
    assert result.primary_intent == "correction_request", (
        f"'{msg}' devrait etre 'correction_request', got '{result.primary_intent}'"
    )


def test_correction_vs_new_exercise(classifier):
    """Si l'utilisateur dit 'd'autres exercices' c'est exercise_request,
    PAS correction_request, meme s'il dit 'corriger' ailleurs."""
    msg = "Donne-moi d'autres exercices"
    result = classifier._classify_heuristic(msg, user_context=None)
    assert result.primary_intent == "exercise_request"


def test_exercises_with_corrige_is_exercise(classifier):
    """'donne-moi des exercices avec corrige' -> exercise_request."""
    msg = "Donne-moi 3 exercices avec corrigé"
    result = classifier._classify_heuristic(msg, user_context=None)
    assert result.primary_intent == "exercise_request", (
        f"'{msg}' devrait etre exercise_request, got '{result.primary_intent}'"
    )


def test_correction_alone_is_correction(classifier):
    """'donne les corriges' SANS demande d'exercices -> correction_request."""
    for msg in ["Donne les corriges", "Les corrigés s'il te plaît",
                "Tu peux corriger ?"]:
        result = classifier._classify_heuristic(msg, user_context=None)
        assert result.primary_intent == "correction_request", (
            f"'{msg}' devrait etre correction_request, got '{result.primary_intent}'"
        )


@pytest.mark.parametrize("msg", PLANETE_CASES)
def test_heuristic_planete(classifier, msg):
    """Une question PLANETE doit etre classee 'planete_help'."""
    result = classifier._classify_heuristic(msg, user_context=None)
    assert result.primary_intent == "planete_help", (
        f"'{msg}' devrait etre 'planete_help', got '{result.primary_intent}'"
    )


@pytest.mark.parametrize("msg", QUESTION_CASES)
def test_heuristic_factual_question(classifier, msg):
    """Question factuelle qui commence par quel/comment/quand."""
    result = classifier._classify_heuristic(msg, user_context=None)
    assert result.primary_intent in ("factual_question", "explain"), (
        f"'{msg}' devrait etre une question, got '{result.primary_intent}'"
    )


@pytest.mark.parametrize("msg", EXPLAIN_CASES)
def test_heuristic_explain(classifier, msg):
    """Demande d'explication."""
    result = classifier._classify_heuristic(msg, user_context=None)
    assert result.primary_intent == "explain", (
        f"'{msg}' devrait etre 'explain', got '{result.primary_intent}'"
    )


# ═════════════════════════════════════════════════════════
# Le bug N°1 historique : "ci" dans "exerCIces"
# ═════════════════════════════════════════════════════════

def test_no_false_exercise_with_just_level(classifier):
    """'Bonjour CM2' ne doit PAS etre classe exercise_request."""
    result = classifier._classify_heuristic("Bonjour CM2", user_context=None)
    assert result.primary_intent == "greeting", (
        "Une salutation avec un niveau scolaire reste une salutation"
    )


def test_explain_not_misclassified_as_exercise(classifier):
    """'Comment expliquer la photosynthese' ne doit JAMAIS etre exercise_request."""
    msg = "Comment expliquer la photosynthèse à un CM2 ?"
    result = classifier._classify_heuristic(msg, user_context=None)
    assert result.primary_intent != "exercise_request", (
        f"'{msg}' ne doit pas etre exercise_request, got '{result.primary_intent}'"
    )


def test_question_with_level_not_exercise(classifier):
    """Une question contenant un niveau ne doit pas devenir exercice."""
    msg = "Quel est le programme de maths en CM2 ?"
    result = classifier._classify_heuristic(msg, user_context=None)
    assert result.primary_intent in ("factual_question", "explain"), (
        f"'{msg}' devrait etre question/explain, got '{result.primary_intent}'"
    )


# ═════════════════════════════════════════════════════════
# Tests du dataclass IntentResult
# ═════════════════════════════════════════════════════════

def test_intent_result_default():
    r = IntentResult(primary_intent="greeting")
    assert r.confidence == 0.7
    assert r.is_confident is True
    assert r.entities == {}
    assert r.needs_retrieval == []


def test_intent_result_low_confidence():
    r = IntentResult(primary_intent="unclear", confidence=0.3)
    assert r.is_confident is False


def test_intent_result_to_dict():
    r = IntentResult(
        primary_intent="exercise_request",
        confidence=0.95,
        entities={"niveau": "CM2"},
    )
    d = r.to_dict()
    assert d["primary_intent"] == "exercise_request"
    assert d["confidence"] == 0.95
    assert d["entities"] == {"niveau": "CM2"}


# ═════════════════════════════════════════════════════════
# Validation taxonomie
# ═════════════════════════════════════════════════════════

def test_taxonomy_complete():
    """Les 11 intents prevus existent tous (10 + correction_request)."""
    expected = {
        "greeting", "smalltalk", "factual_question", "explain",
        "exercise_request", "correction_request", "fiche_request",
        "planete_help", "guidance", "complaint_emotion", "unclear",
    }
    assert VALID_INTENTS == expected


# ═════════════════════════════════════════════════════════
# Test des matieres officielles CEB par niveau
# ═════════════════════════════════════════════════════════

def test_subjects_for_level_elementaire():
    """Les niveaux elementaires CI..CM2 retournent des matieres alignees CEB."""
    from app.services.chat_service import ChatService

    # CI/CP : etape integree
    cicp = ChatService._get_subjects_for_level("CI")
    assert any("Français" in s or "Français" in s for s in cicp)
    assert any("Mathématiques" in s for s in cicp)

    # CM1/CM2 : prepa CFEE
    cm = ChatService._get_subjects_for_level("CM2")
    assert any("Mathématiques" in s for s in cm)
    assert any("Français" in s for s in cm)
    assert any("Anglais" in s for s in cm)
    assert any("Histoire" in s for s in cm)


def test_subjects_for_level_college():
    """College : SVT, Sciences Physiques, etc."""
    from app.services.chat_service import ChatService

    sixieme = ChatService._get_subjects_for_level("6ème")
    assert any("Mathématiques" in s for s in sixieme)
    assert any("SVT" in s or "Vie et de la Terre" in s for s in sixieme)
    assert any("Sciences Physiques" in s for s in sixieme)
    assert any("Anglais" in s for s in sixieme)

    # 4eme/3eme : LV2 disponible
    quatrieme = ChatService._get_subjects_for_level("4ème")
    assert any("Espagnol" in s for s in quatrieme)


def test_subjects_for_level_lycee():
    """Lycee : Philosophie + Physique-Chimie."""
    from app.services.chat_service import ChatService

    term = ChatService._get_subjects_for_level("Terminale")
    assert any("Mathématiques" in s for s in term)
    assert any("Philosophie" in s for s in term)
    assert any("Physique-Chimie" in s for s in term)
