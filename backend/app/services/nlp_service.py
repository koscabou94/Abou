"""
Service NLP principal gérant le LLM (Groq API - llama-3.3-70b-versatile).
Inclut la classification d'intention et la génération de réponses contextuelles.
"""

import re
import asyncio
from typing import Optional
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class NLPService:
    """
    Service NLP qui gère le modèle de langage via Groq API.
    """

    SYSTEM_PROMPT = """Tu es l'assistant éducatif du Ministère de l'Éducation Nationale du Sénégal.

RÈGLE ABSOLUE : Réponds UNIQUEMENT et STRICTEMENT à la question posée par l'utilisateur. INTERDIT d'ajouter des informations sur d'autres sujets.

RÈGLES DE FORMAT :
- Maximum 5 phrases pour une réponse simple, 8 phrases pour une procédure.
- Sois chaleureux et naturel, comme un collègue qui aide.
- Va droit au but : la première phrase doit répondre à la question.
- NE COPIE PAS le contexte documentaire. Reformule avec tes propres mots.
- UNE SEULE réponse cohérente. Pas de sections multiples, pas de titres multiples.
- Termine par une courte phrase d'invitation ("N'hésitez pas si vous avez d'autres questions.").

Si une question sort du cadre éducation/SIMEN, dis poliment que tu es spécialisé dans l'éducation au Sénégal."""

    INTENT_RULES: dict = {
        "salutation": [
            "bonjour", "bonsoir", "salut", "hello", "hi", "hey", "coucou",
            "salam", "assalamu", "nanga def", "na nga def", "jam", "mbaa",
            "merci", "au revoir", "bonne journée", "bonne soirée",
            "comment ça va", "comment ca va", "ça va", "ca va",
            "quoi de neuf", "comment vas-tu", "comment allez"
        ],
        "inscription": [
            "inscri", "enregistr", "dossier", "formulaire", "nouveau", "première fois",
            "comment s'inscrire", "inscription", "inscrire", "matricule"
        ],
        "calendrier": [
            "date", "quand", "calendrier", "rentrée", "vacances", "congé", "trimestre",
            "semestre", "emploi du temps", "horaire", "planning", "fermeture", "ouverture"
        ],
        "examen": [
            "examen", "bfem", "bac", "cfee", "concours", "résultat", "note", "correction",
            "épreuve", "composition", "évaluation", "contrôle", "certificat", "diplôme"
        ],
        "orientation": [
            "orientation", "filière", "lycée", "université", "après le bfem", "après le bac",
            "choisir", "que faire", "quelle filière", "option", "section", "parcours"
        ],
        "bourse": [
            "bourse", "aide", "financement", "allocation", "subvention", "frais",
            "payer", "gratuit", "payant", "argent", "cantine", "transport"
        ],
        "programme": [
            "programme", "matière", "cours", "curriculum", "contenu", "manuel",
            "livre", "enseignement", "apprentissage", "leçon", "chapitre"
        ],
        "administratif": [
            "attestation", "certificat de scolarité", "relevé", "document",
            "administration", "directeur", "proviseur", "inspecteur",
            "académie", "cachet", "signature", "légalisation", "ief"
        ],
        "enseignant": [
            "professeur", "enseignant", "maître", "maîtresse", "prof", "instituteur",
            "formation", "recrutement", "concours enseignant", "FASTEF", "CRFPE"
        ],
        "planete": [
            "planete", "planète", "gestion scolaire", "cahier de texte", "bulletin",
            "nomade", "polarisation", "bst", "salle", "bâtiment",
            "établissement", "fiche établissement", "cycle"
        ],
        "mirador": [
            "mirador", "carrière", "mutation", "mouvement", "affectation",
            "solde", "fiche de paie", "mise à disposition"
        ],
        "identifiant": [
            "ien", "matricule", "identifiant", "code", "trouver ien"
        ],
        "pedagogique": [
            "saisie", "absence", "appel", "pédagogique",
            "discipline", "coefficient", "crédit"
        ],
        "connexion": [
            "connecter", "mot de passe", "email", "professionnel", "compte",
            "accès", "oublié"
        ],
    }

    _SHORT_KEYWORDS = {"hi", "he", "hey", "la", "ko", "mi", "an", "on",
                        "mo", "a", "no", "o", "di", "bi", "gi", "yi",
                        "si", "bu", "su", "ku", "nu", "mu", "te", "ci",
                        "ak", "os"}

    def __init__(self) -> None:
        self._groq_client = None
        self._client_lock = asyncio.Lock()
        logger.info("Service NLP initialisé (Groq)", model=settings.LLM_MODEL)

    async def _ensure_client(self):
        if self._groq_client is not None:
            return self._groq_client
        async with self._client_lock:
            if self._groq_client is not None:
                return self._groq_client
            try:
                from groq import AsyncGroq
                self._groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
                logger.info("Client Groq initialisé")
            except Exception as exc:
                logger.error("Échec init Groq", error=str(exc))
                raise
        return self._groq_client

    def classify_intent(self, text: str) -> tuple:
        if not text:
            return ("general", 0.5)
        text_lower = text.lower()
        text_words = set(re.findall(r'\b\w+\b', text_lower))
        scores = {}
        for intent, keywords in self.INTENT_RULES.items():
            score = 0
            for keyword in keywords:
                if keyword in self._SHORT_KEYWORDS or len(keyword) <= 3:
                    if keyword in text_words:
                        score += 1
                elif " " in keyword:
                    if keyword in text_lower:
                        score += 1
                else:
                    if re.search(r'\b' + re.escape(keyword), text_lower):
                        score += 1
            if score > 0:
                scores[intent] = score
        if not scores:
            return ("general", 0.5)
        best_intent = max(scores, key=scores.__getitem__)
        best_score = scores[best_intent]
        max_possible = len(self.INTENT_RULES[best_intent])
        confidence = min(best_score / max_possible + 0.5, 1.0)
        return (best_intent, confidence)

    @staticmethod
    def _clean_llm_response(text: str) -> str:
        for tag in ["<<SYS>>", "<</SYS>>", "[INST]", "[/INST]", "</s>", "<s>"]:
            text = text.replace(tag, "")
        lines = [l for l in text.split("\n") if l.strip()]
        text = "\n".join(lines).strip()
        paragraphs = text.split("\n\n")
        seen = set()
        unique = []
        for p in paragraphs:
            normalized = p.strip().lower()[:100]
            if normalized not in seen:
                seen.add(normalized)
                unique.append(p)
        return "\n\n".join(unique).strip()

    async def generate_response(
        self,
        message: str,
        context: list,
        intent: Optional[str] = None,
        knowledge_context: Optional[str] = None
    ) -> str:
        if intent == "salutation":
            return self._get_greeting_response(message)

        chat_messages = self._build_chat_messages(message, context, intent, knowledge_context)

        try:
            client = await self._ensure_client()
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=chat_messages,
                    max_tokens=settings.MAX_TOKENS,
                    temperature=settings.TEMPERATURE,
                ),
                timeout=30.0
            )
            text = response.choices[0].message.content.strip()
            if text:
                return self._clean_llm_response(text)
        except asyncio.TimeoutError:
            logger.warning("Groq timeout, fallback")
        except Exception as exc:
            logger.warning("Groq indisponible", error=str(exc))

        if knowledge_context:
            return self._build_lightweight_response(message, knowledge_context, intent)
        return self._get_fallback_response(intent)

    def _build_chat_messages(self, message, context, intent=None, knowledge_context=None):
        system_content = self.SYSTEM_PROMPT
        if intent and intent != "general":
            intent_labels = {
                "inscription": "sur les procédures d'inscription scolaire",
                "calendrier": "sur le calendrier scolaire",
                "bourse": "sur les bourses et aides financières",
                "programme": "sur les programmes scolaires",
                "administratif": "sur les démarches administratives",
                "enseignant": "sur le corps enseignant et la formation",
                "planete": "sur l'utilisation de la plateforme PLANETE 3.0",
                "mirador": "sur la plateforme de gestion RH MIRADOR",
                "identifiant": "sur les identifiants professionnels (IEN/Matricule)",
                "pedagogique": "sur les aspects pédagogiques (notes, absences, cours)",
                "connexion": "sur les problèmes d'accès et de connexion",
            }
            if intent in intent_labels:
                system_content += f"\nL'utilisateur pose une question {intent_labels[intent]}."
        if knowledge_context:
            system_content += f"\n\n{knowledge_context}"

        messages = [{"role": "system", "content": system_content}]
        recent_context = context[-(settings.CONTEXT_WINDOW * 2):]
        for msg in recent_context:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": f"{message}\n\n(Réponds SEULEMENT à cette question, en 5 phrases maximum.)"})
        return messages

    def _build_lightweight_response(self, message, knowledge_context, intent=None):
        stop = {'comment', 'est', 'ce', 'que', 'quoi', 'le', 'la', 'les', 'un', 'une',
                'des', 'du', 'de', 'au', 'aux', 'pour', 'dans', 'sur', 'mon', 'ma',
                'je', 'vous', 'nous', 'a', 'et', 'ou', 'se', 'en', 'qui', 'il', 'elle'}
        lines = knowledge_context.strip().split("\n\n")
        content_blocks = [l.strip() for l in lines if l.strip()
                          and not l.startswith("Contexte de référence")
                          and not l.startswith("Voici des informations")
                          and not l.startswith("Utilise ces informations")]
        if not content_blocks:
            return self._get_fallback_response(intent)
        msg_words = set(message.lower().split())
        scored = sorted([(len(msg_words & set(b.lower().split())), b) for b in content_blocks], reverse=True)
        result = scored[0][1] if scored else ""
        result = "\n".join([l.strip() for l in result.split("\n") if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("Figure")])
        if len(result) > 400:
            cut = result[:400]
            last_period = max(cut.rfind('.'), cut.rfind('\n'))
            result = cut[:last_period + 1] if last_period > 150 else cut + "..."
        return (result + "\n\nN'hésitez pas si vous avez d'autres questions !") if result.strip() else self._get_fallback_response(intent)

    def _get_greeting_response(self, message: str) -> str:
        msg_lower = message.lower().strip()
        if any(w in msg_lower for w in ["merci", "thanks", "jërëjëf"]):
            return "Avec plaisir ! N'hésitez pas si vous avez d'autres questions. 😊"
        if any(w in msg_lower for w in ["au revoir", "bonne journée", "bonne soirée", "bye"]):
            return "Au revoir et bonne continuation ! 👋"
        if any(w in msg_lower for w in ["comment ça va", "comment ca va", "ça va", "ca va", "quoi de neuf", "comment vas", "comment allez"]):
            return "Je vais bien, merci ! Comment puis-je vous aider ? 😊"
        if "bonsoir" in msg_lower:
            return "Bonsoir ! 👋 Je suis votre assistant éducatif. Que puis-je faire pour vous ?"
        if "salut" in msg_lower:
            return "Salut ! 👋 Je suis votre assistant éducatif. Que puis-je faire pour vous ?"
        return "Bonjour ! 👋 Je suis votre assistant éducatif. Que puis-je faire pour vous ?"

    def _get_fallback_response(self, intent: Optional[str]) -> str:
        fallbacks = {
            "inscription": "Pour les inscriptions, contactez directement l'Inspection d'Académie de votre région.",
            "examen": "Pour les examens (CFEE, BFEM, BAC), consultez le site officiel du Ministère de l'Éducation.",
            "bourse": "Pour les bourses et aides financières, rapprochez-vous du service des bourses de votre académie.",
            "calendrier": "Le calendrier scolaire est fixé par le Ministère de l'Éducation. La rentrée a lieu en octobre.",
            "orientation": "Pour l'orientation, consultez le conseiller de votre établissement ou l'Inspection d'Académie.",
            "administratif": "Pour les démarches administratives, adressez-vous au secrétariat de votre établissement.",
            "planete": "Connectez-vous sur https://planete3.education.sn avec votre e-mail professionnel (prenom.nom@education.sn).",
            "mirador": "Pour MIRADOR, contactez le service RH de votre Inspection d'Académie.",
            "connexion": "Utilisez votre e-mail professionnel (prenom.nom@education.sn). En cas d'oubli, contactez votre administrateur local.",
            "general": "Je suis votre assistant éducatif. Posez-moi votre question et je ferai de mon mieux pour vous aider !",
        }
        return fallbacks.get(intent, fallbacks["general"])
