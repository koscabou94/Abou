"""
Classifier d'intention LLM-based avec output JSON structure.

Remplace l'ancienne logique par regles dans nlp_service.classify_intent()
qui produisait des faux positifs massifs (intent=exercice declenche par
n'importe quelle mention de niveau ou matiere).

Architecture :
    USER MSG  -->  Haiku/8B-instant (LLM rapide)
                   + few-shot prompting (15 exemples)
                   + JSON mode strict
              -->  IntentResult { primary_intent, confidence, entities, ... }

Couts : ~$0.0002/requete, latence ~200ms.

Fallback : si le LLM echoue ou repond mal, on retombe sur une heuristique
keyword simple (uniquement sur les intents les plus surs : greeting,
exercice, planete) pour ne jamais bloquer l'app.
"""

import json
import asyncio
import re
from dataclasses import dataclass, field, asdict
from typing import Optional
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────
# TAXONOMIE D'INTENTS
# ─────────────────────────────────────────────────────────────────

VALID_INTENTS = {
    "greeting",          # "Bonjour", "Salut", "Hello"
    "smalltalk",         # "Comment ca va ?", "Merci", "Au revoir"
    "factual_question",  # "Quel est le programme du CM2 ?"
    "explain",           # "Comment expliquer la photosynthese ?"
    "exercise_request",  # "Donne 3 exercices de maths CM2"
    "fiche_request",     # "Fiche pedagogique sur les fractions"
    "planete_help",      # "Comment justifier une absence ?"
    "guidance",          # "Comment aider mon enfant ?"
    "complaint_emotion", # "Je n'y arrive pas"
    "unclear",           # Intent ambigu / multiple
}

# Intents qui necessitent une recherche dans la base de connaissances
RETRIEVAL_INTENTS = {
    "factual_question", "explain", "exercise_request",
    "fiche_request", "planete_help", "guidance",
}

# Intents qui peuvent se traiter sans LLM 70B (Haiku/8B suffit)
LIGHT_INTENTS = {"greeting", "smalltalk"}


# ─────────────────────────────────────────────────────────────────
# DATACLASS DE RESULTAT
# ─────────────────────────────────────────────────────────────────

@dataclass
class IntentResult:
    """Resultat de classification d'intention."""
    primary_intent: str
    confidence: float = 0.7
    secondary_intent: Optional[str] = None
    entities: dict = field(default_factory=dict)  # niveau, matiere, sujet, emotion...
    is_followup: bool = False
    needs_retrieval: list[str] = field(default_factory=list)  # ["faq", "curriculum"...]
    language: str = "fr"
    summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_confident(self) -> bool:
        """True si on peut agir sans demander de clarification."""
        return self.confidence >= 0.6

    @property
    def needs_retrieval_any(self) -> bool:
        return len(self.needs_retrieval) > 0


# ─────────────────────────────────────────────────────────────────
# PROMPT DU CLASSIFIER (few-shot)
# ─────────────────────────────────────────────────────────────────

CLASSIFIER_SYSTEM_PROMPT = """Tu es un classificateur d'intention pour EduBot, un assistant éducatif du Sénégal.

Ton rôle : analyser le message de l'utilisateur et retourner UN SEUL objet JSON strict, sans aucun texte autour.

Tu dois classer le message dans UN des 10 intents suivants :

- "greeting"          : salutation pure (Bonjour, Salut, Hello, Bonsoir...)
- "smalltalk"         : conversation sans demande spécifique (Ça va ?, Merci, Au revoir...)
- "factual_question"  : question avec réponse factuelle (Quel est le programme du CM2 ?)
- "explain"           : demande d'EXPLICATION pédagogique (Comment expliquer X ?, Aide-moi à comprendre Y)
- "exercise_request"  : demande EXPLICITE d'exercices (Donne 3 exercices de maths CM2)
- "fiche_request"     : demande de fiche/préparation/leçon
- "planete_help"      : aide sur la plateforme PLANETE (gestion école, absence, notes...)
- "guidance"          : conseil parental ou pédagogique (Comment aider mon enfant ?)
- "complaint_emotion" : émotion ou plainte (Je suis découragé, c'est trop dur, je n'y arrive pas)
- "unclear"           : intent ambigu ou flou (Aide-moi tout court, J'ai besoin)

RÈGLES CRITIQUES :
1. Ne JAMAIS classer en "exercise_request" si l'utilisateur ne demande pas d'exercices EXPLICITEMENT (mots clés : "exercice", "exo", "devoir", "entraînement", "remédiation", "donne-moi", "je veux", "fais-moi").
2. "Comment expliquer X" → "explain", JAMAIS "exercise_request".
3. "Comment aider mon enfant" → "guidance", JAMAIS "exercise_request".
4. "Bonjour CM2" reste "greeting" (mention de niveau ne suffit pas).
5. Une question pure ("Quel est..." / "Qu'est-ce que...") → "factual_question" ou "explain".

Tu dois aussi extraire les entities (champ optionnel, mets null si absent) :
- niveau : CI, CP, CE1, CE2, CM1, CM2, 6ème, 5ème, 4ème, 3ème, 2nde, 1ère, Terminale, ou null
- matiere : mathématiques, français, anglais, arabe, sciences, histoire-géo, EPS, philosophie, physique-chimie, SVT, ou null
- sujet : sujet précis si mentionné (ex: "fractions", "photosynthèse", "PLANETE 3"...)
- emotion_user : "decourage", "frustre", "perplexe", "enthousiaste", ou null
- ton_souhaite : "pedagogique", "rapide", "rassurant", "professionnel", ou null

Retourne UNIQUEMENT un JSON STRICT avec cette structure exacte :
{
  "primary_intent": "...",
  "confidence": 0.95,
  "secondary_intent": null ou "...",
  "entities": {
    "niveau": null ou "CM2",
    "matiere": null ou "mathématiques",
    "sujet": null ou "fractions",
    "emotion_user": null ou "...",
    "ton_souhaite": null ou "..."
  },
  "is_followup": false,
  "needs_retrieval": ["faq" et/ou "curriculum" et/ou "knowledge"] (vide [] si aucun),
  "language": "fr",
  "summary": "1 phrase qui resume ce que l'utilisateur veut"
}

EXEMPLES (apprends ces patterns) :

USER: "Bonjour"
{"primary_intent":"greeting","confidence":0.99,"secondary_intent":null,"entities":{"niveau":null,"matiere":null,"sujet":null,"emotion_user":null,"ton_souhaite":null},"is_followup":false,"needs_retrieval":[],"language":"fr","summary":"Salutation simple."}

USER: "Salut, comment ça va ?"
{"primary_intent":"greeting","confidence":0.95,"secondary_intent":"smalltalk","entities":{"niveau":null,"matiere":null,"sujet":null,"emotion_user":null,"ton_souhaite":null},"is_followup":false,"needs_retrieval":[],"language":"fr","summary":"Salutation suivie d'une question de courtoisie."}

USER: "Donne-moi 3 exercices de maths pour le CM2"
{"primary_intent":"exercise_request","confidence":0.98,"secondary_intent":null,"entities":{"niveau":"CM2","matiere":"mathématiques","sujet":null,"emotion_user":null,"ton_souhaite":null},"is_followup":false,"needs_retrieval":["curriculum"],"language":"fr","summary":"Demande de 3 exercices de mathématiques pour le CM2."}

USER: "Comment expliquer la photosynthèse à un CM2 ?"
{"primary_intent":"explain","confidence":0.95,"secondary_intent":null,"entities":{"niveau":"CM2","matiere":"sciences","sujet":"photosynthèse","emotion_user":null,"ton_souhaite":"pedagogique"},"is_followup":false,"needs_retrieval":["curriculum","knowledge"],"language":"fr","summary":"Demande d'aide pour expliquer la photosynthèse à un élève de CM2."}

USER: "Quel est le programme de français en CE1 ?"
{"primary_intent":"factual_question","confidence":0.97,"secondary_intent":null,"entities":{"niveau":"CE1","matiere":"français","sujet":null,"emotion_user":null,"ton_souhaite":null},"is_followup":false,"needs_retrieval":["curriculum"],"language":"fr","summary":"Question sur le programme officiel de français en CE1."}

USER: "Mes élèves ne comprennent pas la division, je suis découragée"
{"primary_intent":"complaint_emotion","confidence":0.93,"secondary_intent":"guidance","entities":{"niveau":null,"matiere":"mathématiques","sujet":"division","emotion_user":"decourage","ton_souhaite":"rassurant"},"is_followup":false,"needs_retrieval":["knowledge"],"language":"fr","summary":"Enseignante découragée car ses élèves ne comprennent pas la division."}

USER: "Comment justifier une absence sur PLANETE ?"
{"primary_intent":"planete_help","confidence":0.97,"secondary_intent":null,"entities":{"niveau":null,"matiere":null,"sujet":"absence","emotion_user":null,"ton_souhaite":null},"is_followup":false,"needs_retrieval":["faq"],"language":"fr","summary":"Question sur la procédure de justification d'absence dans PLANETE."}

USER: "Comment aider mon enfant en lecture ?"
{"primary_intent":"guidance","confidence":0.94,"secondary_intent":null,"entities":{"niveau":null,"matiere":"français","sujet":"lecture","emotion_user":null,"ton_souhaite":"rassurant"},"is_followup":false,"needs_retrieval":["knowledge"],"language":"fr","summary":"Parent qui cherche des conseils pour aider son enfant en lecture."}

USER: "Aide-moi"
{"primary_intent":"unclear","confidence":0.95,"secondary_intent":null,"entities":{"niveau":null,"matiere":null,"sujet":null,"emotion_user":null,"ton_souhaite":null},"is_followup":false,"needs_retrieval":[],"language":"fr","summary":"Demande d'aide trop vague, clarification nécessaire."}

USER: "Merci beaucoup !"
{"primary_intent":"smalltalk","confidence":0.99,"secondary_intent":null,"entities":{"niveau":null,"matiere":null,"sujet":null,"emotion_user":"enthousiaste","ton_souhaite":null},"is_followup":false,"needs_retrieval":[],"language":"fr","summary":"Remerciement de l'utilisateur."}

USER: "Fiche pédagogique de mathématiques pour le CE2"
{"primary_intent":"fiche_request","confidence":0.97,"secondary_intent":null,"entities":{"niveau":"CE2","matiere":"mathématiques","sujet":null,"emotion_user":null,"ton_souhaite":null},"is_followup":false,"needs_retrieval":["curriculum"],"language":"fr","summary":"Demande de fiche pédagogique de mathématiques pour le CE2."}

USER: "et en français ?"
{"primary_intent":"factual_question","confidence":0.85,"secondary_intent":null,"entities":{"niveau":null,"matiere":"français","sujet":null,"emotion_user":null,"ton_souhaite":null},"is_followup":true,"needs_retrieval":["curriculum"],"language":"fr","summary":"Suivi de conversation : matière français à la place de la précédente."}

Maintenant, classe le message suivant. Réponds UNIQUEMENT avec le JSON, RIEN d'autre."""


# ─────────────────────────────────────────────────────────────────
# SERVICE
# ─────────────────────────────────────────────────────────────────

class IntentClassifier:
    """Classifier d'intention LLM-based avec fallback heuristique."""

    def __init__(self):
        self._groq_client = None
        self._lock = asyncio.Lock()

    async def _ensure_client(self):
        if self._groq_client is not None:
            return self._groq_client
        async with self._lock:
            if self._groq_client is not None:
                return self._groq_client
            try:
                from groq import AsyncGroq
                self._groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            except Exception as exc:
                logger.error("Echec init Groq pour classifier", error=str(exc))
                raise
        return self._groq_client

    async def classify(
        self,
        message: str,
        conversation_history: Optional[list] = None,
        user_context: Optional[dict] = None,
    ) -> IntentResult:
        """Classifie un message utilisateur en intent + entities.

        Args:
            message: texte de l'utilisateur
            conversation_history: liste optionnelle des derniers echanges
                [{role: user|assistant, content: ...}, ...]
            user_context: profil utilisateur connecte (profile_type, level...)

        Returns:
            IntentResult — toujours retourne quelque chose, jamais None.
        """
        if not message or not message.strip():
            return IntentResult(
                primary_intent="unclear",
                confidence=0.5,
                summary="Message vide.",
            )

        # 1. Tentative LLM (rapide)
        try:
            result = await self._classify_with_llm(message, conversation_history, user_context)
            if result is not None:
                return result
        except Exception as exc:
            logger.warning("Classifier LLM echoue", error=str(exc))

        # 2. Fallback heuristique (jamais None)
        return self._classify_heuristic(message, user_context)

    async def _classify_with_llm(
        self,
        message: str,
        history: Optional[list],
        user_context: Optional[dict],
    ) -> Optional[IntentResult]:
        """Classification via Groq Haiku (modele rapide)."""
        client = await self._ensure_client()

        # Construire les messages pour le LLM
        chat_messages = [{"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT}]

        # Contexte conversation court (uniquement les 2 derniers tours pour
        # detecter les follow-ups type "et en francais ?")
        if history:
            recent = history[-4:]  # 2 echanges max
            ctx_summary = "Contexte de la conversation precedente :\n"
            for h in recent:
                role = h.get("role", "user")
                content = (h.get("content", "") or "")[:200]
                if role and content:
                    ctx_summary += f"- {role}: {content}\n"
            chat_messages.append({"role": "system", "content": ctx_summary})

        if user_context:
            profile = user_context.get("profile_type")
            level = user_context.get("level")
            if profile or level:
                chat_messages.append({
                    "role": "system",
                    "content": (
                        f"Utilisateur : profil={profile or 'inconnu'}, "
                        f"niveau={level or 'inconnu'}"
                    ),
                })

        chat_messages.append({"role": "user", "content": f"USER: {message}"})

        # Appel Groq avec modele rapide
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.LLM_FAST_MODEL,  # llama-3.1-8b-instant
                    messages=chat_messages,
                    max_tokens=400,
                    temperature=0.1,  # Quasi-deterministe pour la classif
                    response_format={"type": "json_object"},
                ),
                timeout=8.0,
            )
            raw = response.choices[0].message.content.strip()
        except asyncio.TimeoutError:
            logger.warning("Classifier LLM timeout")
            return None
        except Exception as exc:
            logger.warning("Classifier LLM exception", error=str(exc))
            return None

        # Parser le JSON
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Tenter d'extraire le JSON s'il y a du texte autour
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    logger.warning("Classifier JSON non parsable", raw=raw[:200])
                    return None
            else:
                logger.warning("Classifier ne retourne pas de JSON", raw=raw[:200])
                return None

        # Valider et construire IntentResult
        primary = parsed.get("primary_intent", "unclear")
        if primary not in VALID_INTENTS:
            logger.warning("Intent invalide retourne par le LLM", intent=primary)
            primary = "unclear"

        try:
            confidence = float(parsed.get("confidence", 0.7))
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.7

        secondary = parsed.get("secondary_intent")
        if secondary and secondary not in VALID_INTENTS:
            secondary = None

        entities = parsed.get("entities") or {}
        if not isinstance(entities, dict):
            entities = {}

        needs_retrieval = parsed.get("needs_retrieval") or []
        if not isinstance(needs_retrieval, list):
            needs_retrieval = []
        # Filtrer les valeurs valides
        needs_retrieval = [
            r for r in needs_retrieval
            if r in ("faq", "curriculum", "knowledge")
        ]

        result = IntentResult(
            primary_intent=primary,
            confidence=confidence,
            secondary_intent=secondary,
            entities=entities,
            is_followup=bool(parsed.get("is_followup", False)),
            needs_retrieval=needs_retrieval,
            language=parsed.get("language", "fr"),
            summary=parsed.get("summary", "")[:200],
        )
        logger.info(
            "Intent classifie (LLM)",
            intent=result.primary_intent,
            confidence=round(result.confidence, 2),
            entities_count=len(result.entities),
        )
        return result

    def _classify_heuristic(
        self,
        message: str,
        user_context: Optional[dict],
    ) -> IntentResult:
        """Fallback heuristique si le LLM est indisponible.
        Conservatif : ne classe en exercise_request que si tres explicite."""
        msg = message.lower().strip()

        # Greeting strict (court + mot-cle precis)
        word_count = len(msg.split())
        GREETING_KW = {"bonjour", "bonsoir", "salut", "hello", "hi", "coucou",
                       "salam", "assalamu", "nanga def"}
        if word_count <= 4 and any(kw in msg for kw in GREETING_KW):
            return IntentResult(
                primary_intent="greeting", confidence=0.9,
                summary="Salutation (heuristique).",
            )

        SMALLTALK_KW = {"merci", "thanks", "au revoir", "bonne journée", "ça va",
                        "comment ça va", "comment ca va"}
        if word_count <= 6 and any(kw in msg for kw in SMALLTALK_KW):
            return IntentResult(
                primary_intent="smalltalk", confidence=0.85,
                summary="Conversation courtoise (heuristique).",
            )

        # Exercice EXPLICITE uniquement (le mot doit etre present)
        # Couvrir avec et sans accents
        if re.search(r"\b(exercice|exercices|exo|exos|devoir|devoirs|entrainement|entraînement|remediation|remédiation)\b", msg):
            # Tentative d'extraction niveau/matiere basique
            entities = {}
            niveau_match = re.search(r"\b(CI|CP|CE1|CE2|CM1|CM2|6ème|6eme|5ème|5eme|4ème|4eme|3ème|3eme|2nde|seconde|1ère|1ere|première|terminale)\b", message, re.IGNORECASE)
            if niveau_match:
                entities["niveau"] = niveau_match.group(0).upper()
            return IntentResult(
                primary_intent="exercise_request", confidence=0.8,
                entities=entities,
                needs_retrieval=["curriculum"],
                summary="Demande d'exercices (heuristique).",
            )

        # Fiche pedagogique
        if re.search(r"\b(fiche|préparation|preparation|plan de leçon|plan de cours|séance pédagogique)\b", msg):
            return IntentResult(
                primary_intent="fiche_request", confidence=0.8,
                needs_retrieval=["curriculum"],
                summary="Demande de fiche pédagogique (heuristique).",
            )

        # PLANETE explicite
        if re.search(r"\b(planete|planète|planete3|planète3|simen|@education\.sn)\b", msg):
            return IntentResult(
                primary_intent="planete_help", confidence=0.85,
                needs_retrieval=["faq"],
                summary="Question PLANETE (heuristique).",
            )

        # Demande d'explication (peut commencer par "aide-moi a expliquer..."
        # ou ne pas commencer par un mot interrogatif)
        if re.search(r"\bexpliquer\b|\bexplique\b|\bcomprendre\b|\bcomprends pas\b", msg):
            return IntentResult(
                primary_intent="explain", confidence=0.75,
                needs_retrieval=["curriculum", "knowledge"],
                summary="Demande d'explication (heuristique).",
            )

        # Question commencant par "comment", "quel", "pourquoi"
        if re.match(r"^(comment|quel|quelle|quels|quelles|pourquoi|qu'est-ce|qu est ce|quand|où|ou|c'est quoi)", msg):
            return IntentResult(
                primary_intent="factual_question", confidence=0.7,
                needs_retrieval=["faq", "curriculum"],
                summary="Question factuelle (heuristique).",
            )

        # Default : unclear
        return IntentResult(
            primary_intent="unclear", confidence=0.5,
            summary="Intent indetermine (heuristique).",
        )
