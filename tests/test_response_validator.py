"""
Tests du validateur de reponse (Sprint 2) :
- Mismatch detector
- Sanitization (anti-gras, anti-italique)
"""

import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.response_validator import (  # noqa: E402
    detect_response_type,
    is_mismatch,
    sanitize_response,
)


# ═════════════════════════════════════════════════════════
# detect_response_type
# ═════════════════════════════════════════════════════════

def test_detect_exercise():
    response = "### Exercices de Mathématiques — CM2\n\n### Exercice 1 — Calcul\nUn élève..."
    types = detect_response_type(response)
    assert "exercises" in types


def test_detect_fiche():
    response = """### Fiche Pédagogique — Mathématiques — CM2

Durée : 45 minutes
Compétence visée : ...
"""
    types = detect_response_type(response)
    assert "fiche" in types


def test_detect_corrections():
    response = """### Corrigés des exercices

### Exercice 1
Solution : 18 ÷ 3 = 6
Réponse : 6 étagères"""
    types = detect_response_type(response)
    assert "corrections" in types


def test_detect_nothing_in_greeting():
    response = "Bonjour Fatou ! Comment puis-je vous aider ?"
    types = detect_response_type(response)
    assert types == set()


# ═════════════════════════════════════════════════════════
# is_mismatch — la regle critique
# ═════════════════════════════════════════════════════════

def test_greeting_with_exercises_is_mismatch():
    """Bug historique : greeting + exercices = mismatch."""
    response = "Bonjour ! Voici 3 exercices :\n### Exercice 1 — Calcul\n..."
    mismatch, reason = is_mismatch("greeting", response)
    assert mismatch is True
    assert "exercises" in reason


def test_greeting_clean_is_ok():
    response = "Bonjour Fatou ! Comment puis-je vous aider ?"
    mismatch, _ = is_mismatch("greeting", response)
    assert mismatch is False


def test_smalltalk_with_fiche_is_mismatch():
    response = "Avec plaisir !\n### Fiche Pédagogique — Mathématiques\nDurée : 45 minutes"
    mismatch, _ = is_mismatch("smalltalk", response)
    assert mismatch is True


def test_exercise_request_with_exercises_is_ok():
    response = "### Exercices de Maths — CM2\n### Exercice 1 — Calcul\n..."
    mismatch, _ = is_mismatch("exercise_request", response)
    assert mismatch is False


def test_exercise_request_without_exercises_is_mismatch():
    """Si on demande des exos mais le LLM repond autre chose."""
    response = "Bien sur, je peux vous aider !"
    mismatch, _ = is_mismatch("exercise_request", response)
    assert mismatch is True


def test_correction_request_with_corrections_is_ok():
    response = "### Corrigés des exercices\n### Exercice 1\nSolution : ...\nRéponse : 6"
    mismatch, _ = is_mismatch("correction_request", response)
    assert mismatch is False


def test_clarification_response_passes():
    """Une reponse de clarification (avec 'voulez-vous') ne doit pas etre rejetee
    meme si elle ne contient pas d'exercices alors que l'intent est exercise_request."""
    response = (
        "Pour vous proposer des exercices parfaitement adaptés, "
        "voulez-vous me préciser le niveau ?"
    )
    mismatch, _ = is_mismatch("exercise_request", response)
    assert mismatch is False  # La clarification est tolérée


# ═════════════════════════════════════════════════════════
# sanitize_response — anti-gras ultime
# ═════════════════════════════════════════════════════════

def test_strip_bold_simple():
    text = "Voici **un mot** important."
    out = sanitize_response(text)
    assert "**" not in out
    assert "un mot" in out


def test_strip_bold_in_title():
    text = "### **Exercice 1** — Calcul"
    out = sanitize_response(text)
    assert "**" not in out
    assert "Exercice 1" in out


def test_strip_underscore_bold():
    text = "Texte avec __gras alternatif__ ici."
    out = sanitize_response(text)
    assert "__" not in out
    assert "gras alternatif" in out


def test_strip_italic():
    text = "Voici un *texte* en italique."
    out = sanitize_response(text)
    assert "texte" in out
    # Les asterisques inline sont retires
    assert "*texte*" not in out


def test_preserve_markdown_lists():
    """Les listes Markdown qui commencent par '* ' doivent etre preservees."""
    text = "* Premier item\n* Deuxieme item"
    out = sanitize_response(text)
    # Au minimum les items eux-memes restent
    assert "Premier item" in out
    assert "Deuxieme item" in out


def test_strip_html_strong():
    text = "Voici <strong>un mot</strong> important."
    out = sanitize_response(text)
    assert "<strong>" not in out
    assert "</strong>" not in out
    assert "un mot" in out


def test_strip_llm_artifacts():
    text = "<<SYS>>Système<</SYS>>\n[INST]instruction[/INST]\n</s>Reponse"
    out = sanitize_response(text)
    assert "<<SYS>>" not in out
    assert "[INST]" not in out
    assert "</s>" not in out


def test_nested_bold():
    text = "Voici **texte avec **gras imbrique** dedans**"
    out = sanitize_response(text)
    assert "**" not in out


def test_orphan_asterisks():
    text = "Voici un mot ** sans paire correspondante"
    out = sanitize_response(text)
    assert "**" not in out


def test_empty_input():
    assert sanitize_response("") == ""
    assert sanitize_response(None) is None
