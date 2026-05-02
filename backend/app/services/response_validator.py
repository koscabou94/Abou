"""
Validateur d'output LLM (Sprint 2).

Deux roles :
1. MISMATCH DETECTOR : verifier que la reponse correspond bien a l'intent.
   Ex : si intent=greeting mais la reponse contient "Exercice 1", c'est un
   bug -> on rejette pour declencher un retry.

2. OUTPUT SANITIZATION : strip ultime de tout residu de gras/italique/HTML
   meme si le LLM a ignore le SYSTEM_PROMPT. C'est la derniere ligne de
   defense avant l'envoi au frontend.
"""

import re
import structlog

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────
# MISMATCH DETECTOR
# ─────────────────────────────────────────────────────────────────

# Patterns qui indiquent qu'une reponse contient des exercices
EXERCISE_PATTERNS = [
    r"###\s*Exercice\s+\d+",
    r"###\s*Exercices?\s+de\s+\w+",
    r"\bExercice\s+\d+\s*[—–:-]",
]

# Patterns qui indiquent qu'une reponse contient une fiche pedagogique
FICHE_PATTERNS = [
    r"###\s*Fiche\s+P[eé]dagogique",
    r"\bDur[eé]e\s*:\s*\d+\s*minutes",
    r"\bComp[eé]tence\s+vis[eé]e\s*:",
    r"###\s*D[eé]roulement\s+de\s+la\s+s[eé]ance",
]

# Patterns qui indiquent qu'une reponse contient des corriges
CORRECTION_PATTERNS = [
    r"###\s*Corrig[eé]s?",
    r"\bSolution\s*:",
    r"\bR[eé]ponse\s*:",
]


def detect_response_type(response: str) -> set[str]:
    """Identifie ce que contient la reponse : exercises, fiche, corrections, etc."""
    types = set()
    if any(re.search(p, response, re.IGNORECASE) for p in EXERCISE_PATTERNS):
        types.add("exercises")
    if any(re.search(p, response, re.IGNORECASE) for p in FICHE_PATTERNS):
        types.add("fiche")
    if any(re.search(p, response, re.IGNORECASE) for p in CORRECTION_PATTERNS):
        types.add("corrections")
    return types


# Ce que chaque intent est CENSÉ produire (et ce qu'il ne doit PAS produire).
# Si la reponse contient un type non autorise, c'est un mismatch.
INTENT_EXPECTED_TYPES = {
    "greeting":           {"forbidden": {"exercises", "fiche"}, "allowed_extra": set()},
    "smalltalk":          {"forbidden": {"exercises", "fiche"}, "allowed_extra": set()},
    "factual_question":   {"forbidden": {"exercises", "fiche"}, "allowed_extra": set()},
    "explain":            {"forbidden": {"exercises"},          "allowed_extra": set()},
    "exercise_request":   {"required": {"exercises"},            "allowed_extra": {"corrections"}},
    "correction_request": {"required": {"corrections"},          "allowed_extra": set()},
    "fiche_request":      {"required": {"fiche"},                "allowed_extra": set()},
    "planete_help":       {"forbidden": {"exercises", "fiche"}, "allowed_extra": set()},
    "guidance":           {"forbidden": {"exercises", "fiche"}, "allowed_extra": set()},
    "complaint_emotion":  {"forbidden": {"exercises", "fiche"}, "allowed_extra": set()},
    "unclear":            {"forbidden": {"exercises", "fiche"}, "allowed_extra": set()},
}


def is_mismatch(intent: str, response: str) -> tuple[bool, str]:
    """Detecte si la reponse ne correspond pas a l'intent.

    Returns (is_mismatch, reason).
    """
    if not response or not intent:
        return False, ""

    types = detect_response_type(response)
    rules = INTENT_EXPECTED_TYPES.get(intent)
    if not rules:
        return False, ""

    forbidden = rules.get("forbidden", set())
    required = rules.get("required", set())

    # Check forbidden : la reponse ne doit PAS contenir ces types
    intersection = types & forbidden
    if intersection:
        return True, f"Intent '{intent}' ne devrait PAS contenir {intersection}"

    # Check required : la reponse DOIT contenir ces types (sauf court-circuit clarification)
    if required and not (types & required):
        # Tolerance : si la reponse contient un message de clarification, OK
        if any(p in response.lower() for p in ["voulez-vous", "quel niveau", "quelle matière"]):
            return False, ""
        return True, f"Intent '{intent}' devrait contenir {required} mais a {types or '∅'}"

    return False, ""


# ─────────────────────────────────────────────────────────────────
# OUTPUT SANITIZATION (anti-gras ultime)
# ─────────────────────────────────────────────────────────────────

def sanitize_response(text: str) -> str:
    """Strip ultime de tout residu de formatting non autorise.

    C'est la DERNIERE ligne de defense avant l'envoi au frontend.
    Le LLM peut ignorer le SYSTEM_PROMPT, ici on garantit le format.
    """
    if not text:
        return text

    # 3 passes pour gerer les imbrications type **a **b** c**
    for _ in range(3):
        # Gras+italique ***...***
        text = re.sub(r"\*\*\*([^*]+?)\*\*\*", r"\1", text, flags=re.DOTALL)
        # Gras **...**
        text = re.sub(r"\*\*\s*([^*]+?)\s*\*\*", r"\1", text, flags=re.DOTALL)
        text = re.sub(r"\*\*\s*([\s\S]+?)\s*\*\*", r"\1", text, flags=re.DOTALL)
        # Gras __...__
        text = re.sub(r"__\s*([\s\S]+?)\s*__", r"\1", text, flags=re.DOTALL)

    # Asterisques orphelins (** restants)
    text = re.sub(r"\*{2,}", "", text)

    # Italique simple *texte* (preserver les listes Markdown qui commencent par *)
    text = re.sub(r"(?<!\n)(?<!^)\*([^\s*][^*\n]*?[^\s*])\*", r"\1", text)

    # HTML strong/b/em/i (au cas où)
    text = re.sub(r"</?(strong|b|em|i)\s*[^>]*>", "", text, flags=re.IGNORECASE)

    # Tags <<SYS>>, [INST], </s>... qui peuvent fuir des LLMs raw
    for tag in ["<<SYS>>", "<</SYS>>", "[INST]", "[/INST]", "</s>", "<s>"]:
        text = text.replace(tag, "")

    # Espaces multiples consecutifs (sans toucher les sauts de ligne)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()
