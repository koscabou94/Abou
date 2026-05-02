"""
Service principal d'orchestration du chatbot.
Coordonne la détection de langue, la traduction, la classification d'intention,
la recherche FAQ et la génération de réponses LLM.
"""

import time
import uuid
import hashlib
from collections import OrderedDict
from datetime import datetime
from typing import Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.language_service import LanguageService
from app.services.translation_service import TranslationService
from app.services.nlp_service import NLPService
from app.services.faq_service import FAQService
from app.services.knowledge_service import KnowledgeService
from app.services.planete_faq_service import (
    PlaneteFAQService,
    is_planete_question,
)
from app.services.curriculum_service import (
    CurriculumService,
    detect_niveau,
    detect_matiere,
)

logger = structlog.get_logger(__name__)


# ============================================================
# Cache LRU des réponses du LLM
# ============================================================
# Cache simple en mémoire pour économiser le quota Groq sur les questions
# fréquentes. Clé = hash(message normalisé + intent). TTL implicite : tant
# que le process tourne (Render free dort après 15min d'inactivité, ce qui
# vide naturellement le cache).
class _LRUCache:
    def __init__(self, max_size: int = 200) -> None:
        self._store: OrderedDict[str, str] = OrderedDict()
        self._max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[str]:
        if key in self._store:
            self._store.move_to_end(key)
            self.hits += 1
            return self._store[key]
        self.misses += 1
        return None

    def put(self, key: str, value: str) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = value
        if len(self._store) > self._max_size:
            self._store.popitem(last=False)


class ChatService:
    """
    Orchestrateur principal du chatbot éducatif.
    Implémente le pipeline complet de traitement des messages :
    détection langue → traduction → classification → FAQ → LLM → traduction retour.
    """

    def __init__(
        self,
        language_service: LanguageService,
        translation_service: TranslationService,
        nlp_service: NLPService,
        faq_service: FAQService,
        knowledge_service: Optional["KnowledgeService"] = None,
        planete_faq_service: Optional["PlaneteFAQService"] = None,
        curriculum_service: Optional["CurriculumService"] = None,
        intent_classifier: Optional[object] = None,
    ) -> None:
        """
        Initialise le service de chat avec ses dépendances.

        Args:
            language_service: Service de détection de langue
            translation_service: Service de traduction NLLB-200
            nlp_service: Service LLM pour la génération de réponses
            faq_service: Service de recherche dans les FAQ
            knowledge_service: Service de recherche dans la base de connaissances
            planete_faq_service: Service FAQ dédié PLANETE (FAQ_PLANETE3.json)
            curriculum_service: Service Curriculum CEB (programme officiel sénégalais)
        """
        self.language_service = language_service
        self.translation_service = translation_service
        self.nlp_service = nlp_service
        self.faq_service = faq_service
        self.knowledge_service = knowledge_service
        self.planete_faq_service = planete_faq_service
        self.curriculum_service = curriculum_service
        # Sprint 1 : nouveau classifier d'intent LLM-based (optionnel)
        self.intent_classifier = intent_classifier

        # Cache LRU des réponses LLM (200 entrées max)
        self._llm_cache = _LRUCache(max_size=200)

        # Mémoire conversationnelle légère par session : dernière intention,
        # dernier sujet PLANETE, dernier niveau/matière. Utilisée pour
        # désambiguïser les références implicites ("et une salle ?").
        self._session_state: dict[str, dict] = {}

        # Sprint 2 : memoire des derniers exercices generes par session.
        # Permet a _handle_correction de retrouver les exos meme si la BD
        # est down (Render ephemere). Cache simple dict, pas de LRU.
        self._session_exercises: dict[str, str] = {}

        logger.info(
            "Service de chat initialisé avec succès",
            knowledge_available=knowledge_service is not None,
            planete_available=planete_faq_service is not None,
        )

    # ---------------------------------------------------------
    # MÉMOIRE DE SESSION
    # ---------------------------------------------------------
    def _get_session_state(self, session_id: str) -> dict:
        """Récupère ou crée l'état conversationnel d'une session."""
        if session_id not in self._session_state:
            self._session_state[session_id] = {
                "last_intent": None,           # exercice / programme / planete / ...
                "last_planete_topic": None,    # categorie PLANETE traitee
                "last_niveau": None,           # CI / CP / CE1 / .../ Terminale
                "last_matiere": None,          # mathematiques / francais / anglais / ...
                "last_response_type": None,    # curriculum / exercice / fiche / planete_faq
                "last_question": None,         # texte de la derniere question utilisateur
                "last_assistant_excerpt": None,  # debut de la derniere reponse (pour "la suite")
            }
        return self._session_state[session_id]

    def _update_session_state(
        self,
        session_id: str,
        intent: Optional[str] = None,
        planete_topic: Optional[str] = None,
        niveau: Optional[str] = None,
        matiere: Optional[str] = None,
        response_type: Optional[str] = None,
        question: Optional[str] = None,
        assistant_excerpt: Optional[str] = None,
    ) -> None:
        """Met à jour l'état d'une session — sans écraser avec None."""
        state = self._get_session_state(session_id)
        if intent:
            state["last_intent"] = intent
        if planete_topic:
            state["last_planete_topic"] = planete_topic
        if niveau:
            state["last_niveau"] = niveau
        if matiere:
            state["last_matiere"] = matiere
        if response_type:
            state["last_response_type"] = response_type
        if question:
            state["last_question"] = question
        if assistant_excerpt:
            state["last_assistant_excerpt"] = assistant_excerpt[:300]

    # ---------------------------------------------------------
    # CACHE LLM
    # ---------------------------------------------------------
    @staticmethod
    def _cache_key(
        message: str,
        intent: str,
        niveau: Optional[str] = None,
        matiere: Optional[str] = None,
    ) -> str:
        """Construit la clé du cache LRU.

        Inclut le niveau et la matière du contexte courant pour éviter
        qu'une question de follow-up courte ("donne plus de détails",
        "continue") serve la même réponse à deux sessions au contexte
        différent (ex : un utilisateur sur le programme CM2, un autre
        sur le programme CE1).
        """
        norm = message.lower().strip()
        ctx = f"{(niveau or '').lower()}|{(matiere or '').lower()}"
        return hashlib.md5(f"{intent}|{ctx}|{norm}".encode("utf-8")).hexdigest()

    # ---------------------------------------------------------
    # SUGGESTIONS DE RELANCE CONTEXTUELLES
    # ---------------------------------------------------------
    def _build_suggestions(
        self,
        intent: str,
        niveau: Optional[str],
        matiere: Optional[str],
        source: str,
    ) -> list[str]:
        """Génère 2-3 suggestions de questions de relance pertinentes
        selon l'intent et le contexte. Affichées comme boutons sous la
        réponse dans le frontend. Aide les utilisateurs à explorer le bot."""

        # Aprés une question PLANETE FAQ : proposer les sujets connexes
        if source == "planete_faq":
            return [
                "Comment configurer un bâtiment ?",
                "Comment importer le personnel ?",
                "Comment justifier une absence ?",
            ]

        # Après une question programme : proposer matière ou exercices
        if intent == "programme" and niveau:
            if matiere:
                return [
                    f"Donne-moi 3 exercices de {matiere} pour le {niveau}",
                    f"Fiche pédagogique de {matiere} pour le {niveau}",
                    f"Quels sont les paliers en {niveau} ?",
                ]
            return [
                f"En français",
                f"En mathématiques",
                f"Donne-moi des exercices pour le {niveau}",
            ]

        # Après une demande d'exercices : proposer corrigés ou variations
        if intent == "exercice" and niveau:
            base = [f"Donne-moi les corrigés"]
            if matiere:
                base.append(f"D'autres exercices de {matiere} pour le {niveau}")
                base.append(f"Fiche pédagogique de {matiere} pour le {niveau}")
            else:
                base.append(f"D'autres exercices pour le {niveau}")
            return base[:3]

        # Après une fiche : proposer exercices
        if intent == "fiche" and niveau and matiere:
            return [
                f"Donne-moi 3 exercices de {matiere} pour le {niveau}",
                f"Quel est le programme de {matiere} en {niveau} ?",
                f"Évaluation de {matiere} {niveau}",
            ]

        # Suggestions générales par défaut
        if intent in ("salutation", "general", "error"):
            return [
                "Quel est le programme de maths en CM2 ?",
                "Comment se connecter à PLANETE ?",
                "Donne-moi 3 exercices pour le CE1",
            ]

        return []

    # ---------------------------------------------------------
    # RESOLUTION DES FOLLOW-UPS (mémoire conversationnelle)
    # ---------------------------------------------------------
    def _resolve_followup(
        self, message: str, session_id: str
    ) -> tuple[str, Optional[str]]:
        """Résout un message court en utilisant le contexte de la session.

        Exemples gérés :
          1. "en français" après "programme CM2" → "programme de français en CM2"
          2. "et en maths" après "programme CE1" → "programme de mathématiques en CE1"
          3. "la suite" / "continue" → "continue ce que tu disais"
          4. "donne moi des exercices" après curriculum CM2 → ajoute le niveau
          5. "et le palier 4" après description curriculum → reformule

        Args:
            message: message utilisateur brut
            session_id: identifiant de session

        Returns:
            (message_reformulé, intent_forcé) — intent_forcé peut être None
        """
        state = self._get_session_state(session_id)
        last_intent = state.get("last_intent")
        last_niveau = state.get("last_niveau")
        last_matiere = state.get("last_matiere")
        last_resp_type = state.get("last_response_type")

        # Pas d'historique → pas de résolution possible
        if not last_intent:
            return message, None

        msg_lower = message.lower().strip()
        word_count = len(msg_lower.split())

        # ── GARDE-FOUS : ne PAS reformuler si le message est ──
        # ─────────────────────────────────────────────────────
        # 1. Une réponse à une clarification (contient " — " injecté par
        #    le frontend quand l'utilisateur clique sur un bouton)
        if " — " in message or " - " in message:
            logger.debug("Skip résolveur : réponse à clarification (contient — )")
            return message, None

        # 2. La dernière réponse était une clarification (boutons)
        #    Le message actuel est une RÉPONSE, pas un follow-up à reformuler
        if last_resp_type == "clarification":
            logger.debug("Skip résolveur : dernière réponse était une clarification")
            return message, None

        # 3. Une demande complète qui commence par un verbe d'action explicite
        #    (avec >3 mots → c'est clairement une nouvelle question, pas un
        #    follow-up court)
        NEW_REQUEST_STARTERS = [
            "donne moi", "donne-moi", "donnez moi", "donnez-moi",
            "fais moi", "fais-moi", "faites moi", "faites-moi",
            "génère", "genere", "produis", "propose moi", "propose-moi",
            "fournis moi", "fournis-moi", "envoie moi", "envoie-moi",
            "j'aimerais", "je voudrais", "je veux",
            "peux-tu", "peux tu", "pouvez-vous", "pouvez vous",
        ]
        is_new_request = any(msg_lower.startswith(s) for s in NEW_REQUEST_STARTERS)
        if is_new_request and word_count > 3:
            logger.debug(
                "Skip résolveur : nouvelle demande complète",
                msg=message[:60],
            )
            return message, None

        # Trop long pour être un follow-up court (probablement nouvelle question)
        if word_count > 7:
            return message, None

        # ── Pattern 1 : matière seule après une question programme ──
        # Ex: "en français", "francais", "et les maths", "maths", "anglais"
        SUBJECT_TRIGGERS = {
            "francais": "français", "français": "français",
            "math": "mathématiques", "maths": "mathématiques",
            "mathematiques": "mathématiques", "mathématiques": "mathématiques",
            "anglais": "anglais", "english": "anglais",
            "arabe": "arabe",
            "histoire": "histoire-géographie",
            "geographie": "histoire-géographie", "géographie": "histoire-géographie",
            "histoire-geo": "histoire-géographie", "histoire-géo": "histoire-géographie",
            "sciences": "sciences", "science": "sciences",
            "physique": "physique-chimie", "chimie": "physique-chimie",
            "physique-chimie": "physique-chimie",
            "svt": "SVT", "biologie": "SVT",
            "philosophie": "philosophie", "philo": "philosophie",
            "lecture": "lecture", "écriture": "écriture", "ecriture": "écriture",
            "grammaire": "grammaire", "conjugaison": "conjugaison",
            "orthographe": "orthographe", "vocabulaire": "vocabulaire",
            "calcul": "calcul", "géométrie": "géométrie", "geometrie": "géométrie",
            "algèbre": "algèbre", "algebre": "algèbre",
            "eps": "EPS", "education physique": "EPS",
            "arts": "arts", "musique": "musique",
            "communication orale": "communication orale",
            "production écrite": "production écrite",
            "production ecrite": "production écrite",
            "vivre ensemble": "vivre ensemble",
            "découverte du monde": "découverte du monde",
            "decouverte du monde": "découverte du monde",
        }

        # Détecter une matière dans le message court
        detected_subject = None
        for trigger, canonical in SUBJECT_TRIGGERS.items():
            # Pour les multi-mots, recherche substring
            if " " in trigger and trigger in msg_lower:
                detected_subject = canonical
                break
            # Pour les mots simples, limites de mots
            elif " " not in trigger:
                import re as _re
                if _re.search(rf"\b{_re.escape(trigger)}\b", msg_lower):
                    detected_subject = canonical
                    break

        # Cas : matière détectée + dernière question était sur le programme
        # → on précise la matière dans la même question
        if (
            detected_subject
            and last_intent == "programme"
            and last_niveau
        ):
            reformulated = (
                f"Quel est le programme de {detected_subject} en {last_niveau} ?"
            )
            logger.info(
                "Follow-up résolu (programme + matière)",
                original=message,
                reformulated=reformulated,
            )
            return reformulated, "programme"

        # Cas : matière détectée + dernière question était sur des exercices
        # → on réutilise le niveau et change la matière
        if (
            detected_subject
            and last_intent == "exercice"
            and last_niveau
        ):
            reformulated = (
                f"Donne-moi 3 exercices de {detected_subject} pour le {last_niveau}"
            )
            logger.info(
                "Follow-up résolu (exercices + nouvelle matière)",
                original=message,
                reformulated=reformulated,
            )
            return reformulated, "exercice"

        # ── Pattern 2 : "la suite", "continue", "et après", "ensuite" ──
        CONTINUATION_MARKERS = [
            "la suite", "et la suite", "donne la suite", "donne-moi la suite",
            "continue", "continuez", "poursuis",
            "ensuite", "et ensuite", "et après", "et apres",
            "encore", "plus", "donne plus", "plus de détails", "plus de details",
            "developpe", "développe", "approfondis",
        ]
        if any(c in msg_lower for c in CONTINUATION_MARKERS) and word_count <= 5:
            if last_intent == "programme" and last_niveau:
                mat_part = f" en {last_matiere}" if last_matiere else ""
                reformulated = (
                    f"Continue la description du programme {last_niveau}{mat_part}. "
                    f"Donne plus de détails sur les paliers et les objectifs."
                )
                logger.info(
                    "Follow-up résolu (continuation programme)",
                    reformulated=reformulated,
                )
                return reformulated, "programme"
            if last_intent == "planete":
                # "et après" pour PLANETE est déjà géré ailleurs
                return message, None
            # Continuation générale
            reformulated = f"Continue ta dernière réponse, donne plus de détails."
            return reformulated, last_intent

        # ── Pattern 3 : demande d'exercices après une question programme ──
        EXERCISE_REQUEST_SHORT = [
            "donne moi des exercices", "donne-moi des exercices",
            "des exercices", "exercices", "fais des exercices",
            "je veux des exercices", "fais moi des exercices",
            "génère des exercices", "genere des exercices",
            "propose des exercices", "donne des exercices",
            "oui des exercices", "oui exercices", "oui je veux des exercices",
        ]
        if (
            last_intent == "programme"
            and any(e in msg_lower for e in EXERCISE_REQUEST_SHORT)
            and word_count <= 10
        ):
            # Cherche aussi une matière dans le message ("oui des exercices en maths")
            from app.services.curriculum_service import detect_matiere as _dmat
            mat_in_msg = _dmat(msg_lower)
            target_mat = mat_in_msg or last_matiere

            if last_niveau:
                # On a niveau + matière (ou niveau seul) → reformulation directe
                mat_part = f" de {target_mat}" if target_mat else ""
                reformulated = (
                    f"Donne-moi 3 exercices{mat_part} pour le {last_niveau}"
                )
                logger.info(
                    "Follow-up résolu (exercices après programme)",
                    reformulated=reformulated,
                )
                return reformulated, "exercice"
            else:
                # Pas de niveau précis → forcer la clarification niveau
                # (le pipeline déclenchera _check_needs_clarification)
                mat_part = f" de {target_mat}" if target_mat else ""
                reformulated = f"Donne-moi 3 exercices{mat_part}"
                logger.info(
                    "Follow-up sans niveau → reformule pour déclencher clarification",
                    reformulated=reformulated,
                )
                return reformulated, "exercice"

        # ── Pattern 4 : "et avec corrigé" après exercices ──
        if last_intent == "exercice" and "corrig" in msg_lower and word_count <= 5:
            # Le LLM gère déjà cela via l'historique de conversation
            return message, "exercice"

        # ── Pattern 4-bis : "celui du X" / "celle de X" / "et pour le X" ──
        # L'utilisateur veut hériter de l'intent précédent en changeant juste
        # le niveau ou la matière. Détecte un niveau dans le message court.
        from app.services.curriculum_service import detect_niveau as _det_niv
        from app.services.curriculum_service import detect_matiere as _det_mat
        ELLIPSIS_MARKERS = [
            "celui du", "celui de", "celle du", "celle de",
            "celui pour", "celle pour", "et pour", "et le", "et la",
            "pareil pour", "même chose pour", "et celui",
        ]
        has_ellipsis = any(m in msg_lower for m in ELLIPSIS_MARKERS)
        new_niveau_in_msg = _det_niv(msg_lower)

        if (has_ellipsis or new_niveau_in_msg) and word_count <= 8:
            # Hériter de l'intent précédent et utiliser le nouveau niveau/matière
            target_niveau = new_niveau_in_msg or last_niveau
            target_matiere = _det_mat(msg_lower) or last_matiere
            if last_intent == "programme" and target_niveau:
                mat_part = f" en {target_matiere}" if target_matiere else ""
                reformulated = (
                    f"Quel est le programme{mat_part} pour le {target_niveau} ?"
                )
                logger.info(
                    "Follow-up résolu (ellipse 'celui du X' programme)",
                    reformulated=reformulated,
                )
                return reformulated, "programme"
            if last_intent == "exercice" and target_niveau:
                mat_part = f" de {target_matiere}" if target_matiere else ""
                reformulated = (
                    f"Donne-moi 3 exercices{mat_part} pour le {target_niveau}"
                )
                logger.info(
                    "Follow-up résolu (ellipse 'celui du X' exercice)",
                    reformulated=reformulated,
                )
                return reformulated, "exercice"

        # ── Pattern 5 : niveau seul après matière seule ──
        # Ex: utilisateur a dit "exercices français" → bot a demandé niveau →
        # utilisateur dit "CM2" → on combine
        # (cas géré par la clarification existante, on laisse passer)

        # Pas de follow-up détecté
        return message, None

    async def process_message(
        self,
        user_message: str,
        session_id: str,
        db: AsyncSession,
        language_override: Optional[str] = None,
        user: Optional[object] = None,
    ) -> dict:
        """
        Traite un message utilisateur et génère une réponse.

        Pipeline de traitement :
        1. Détection de la langue
        2. Traduction vers le français (langue pivot)
        3. Classification de l'intention
        4. Recherche dans les FAQ (chemin rapide)
        5. Génération LLM si la FAQ ne suffit pas
        6. Traduction de la réponse vers la langue de l'utilisateur
        7. Sauvegarde en base de données

        Args:
            user_message: Message brut de l'utilisateur
            session_id: Identifiant de session UUID
            db: Session de base de données
            language_override: Forcer une langue spécifique (ignore la détection auto)

        Returns:
            Dictionnaire contenant la réponse et les métadonnées
        """
        start_time = time.time()

        # Validation du message
        if not user_message or not user_message.strip():
            return self._build_error_response(
                session_id,
                "Message vide reçu",
                "fr"
            )

        message_clean = user_message.strip()[:1000]  # Limiter à 1000 caractères

        # ─────────────────────────────────────────────────────────
        # PERSONNALISATION (utilisateur authentifié)
        # ─────────────────────────────────────────────────────────
        # Si l'utilisateur est connecté avec un niveau connu (élève / parent),
        # on l'injecte dans le message si absent. Cela évite la clarification
        # niveau pour ces utilisateurs et oriente directement la génération.
        user_profile = None
        user_level_default = None
        if user is not None:
            user_profile = getattr(user, "profile_type", None)
            user_level_default = getattr(user, "level", None)
            if user_level_default:
                # Vérifier si un niveau est déjà mentionné dans le message
                try:
                    if not detect_niveau(message_clean):
                        message_clean = f"{message_clean} (niveau {user_level_default})"
                        logger.debug(
                            "Niveau utilisateur injecté",
                            level=user_level_default,
                            profile=user_profile,
                        )
                except Exception:
                    pass

        # Normaliser les niveaux scolaires écrits avec espaces ("CE 1" → "CE1",
        # "CM 2" → "CM2", "C E 1" → "CE1", "C I" → "CI", "C P" → "CP")
        # pour que la détection les attrape correctement.
        import re as _re_lvl
        # CE1, CE2, CM1, CM2 (lettre + chiffre)
        message_clean = _re_lvl.sub(
            r"\b([Cc])\s*([EeMm])\s*([12])\b",
            lambda m: m.group(1).upper() + m.group(2).upper() + m.group(3),
            message_clean,
        )
        # CI, CP (lettres seules)
        message_clean = _re_lvl.sub(
            r"\b([Cc])\s+([IiPp])\b",
            lambda m: m.group(1).upper() + m.group(2).upper(),
            message_clean,
        )

        logger.info(
            "Traitement d'un nouveau message",
            session_id=session_id,
            message_length=len(message_clean)
        )

        try:
            # === ÉTAPE 1 : Détection de la langue ===
            if language_override and self.language_service.is_supported(language_override):
                detected_lang = language_override
                logger.debug("Langue forcée par l'utilisateur", lang=detected_lang)
            else:
                detected_lang = self.language_service.detect_language(message_clean)
                logger.debug("Langue détectée automatiquement", lang=detected_lang)

            # === ÉTAPE 2 : Traduction vers le français (pivot) ===
            if detected_lang != settings.PIVOT_LANGUAGE:
                logger.debug("Traduction vers le pivot", source=detected_lang)
                fr_message = await self.translation_service.translate_to_pivot(
                    message_clean, detected_lang
                )
            else:
                fr_message = message_clean

            logger.debug("Message en français", fr_message=fr_message[:100])

            # === ÉTAPE 2-bis : Résolution des follow-ups conversationnels ===
            # Si le message est court et que le contexte de session le permet,
            # on reformule la question pour intégrer le niveau/matière déjà
            # connus. Ex : "en français" après "programme CM2" devient
            # "Quel est le programme de français en CM2 ?".
            forced_intent: Optional[str] = None
            original_fr_message = fr_message
            fr_message_resolved, forced_intent = self._resolve_followup(
                fr_message, session_id
            )
            if fr_message_resolved != fr_message:
                fr_message = fr_message_resolved
                logger.info(
                    "Message reformulé via mémoire conversationnelle",
                    original=original_fr_message[:100],
                    resolved=fr_message[:120],
                    forced_intent=forced_intent,
                )

            # === ÉTAPE 3 : Classification de l'intention ===
            intent, confidence = self.nlp_service.classify_intent(fr_message)
            if forced_intent:
                # Le résolveur de follow-up impose l'intent (priorité absolue)
                intent = forced_intent
            logger.debug("Intention classifiée", intent=intent, confidence=confidence)

            # === ÉTAPE 3-bis : Override intent → "programme" si curriculum-query ===
            # Sans cet override, "programme de maths CM2" est classé "exercice"
            # car "maths" + "CM2" pèsent plus fort que "programme".
            # Mais l'utilisateur veut une DESCRIPTION du programme, pas des
            # exercices. On force donc l'intent quand c'est clairement une
            # question sur le curriculum officiel.
            _curriculum_markers = [
                "programme", "curriculum", "ceb",
                "objectifs", "objectif", "objectif spécifique",
                "compétences", "competences", "competence",
                "que doit savoir", "qu'est-ce que doit savoir",
                "ce que l'élève doit", "ce que l eleve doit",
                "ce qu'il faut savoir", "ce qu'il faut connaitre",
                "palier", "paliers",
                "quel est le programme", "quel est le curriculum",
                "quels sont les objectifs", "quelles sont les compétences",
                "à quoi correspond", "que contient le programme",
                "officiel sénégalais", "officiel senegalais",
                "ministère de l'éducation", "ministere de l education",
            ]
            # Mot "exercice"/"exercices" présent → vraie demande d'exercices
            _has_exercice_word = any(
                w in fr_message.lower()
                for w in ["exercice", "exercices", "exo", "exos", "devoir", "devoirs"]
            )
            _msg_lower = fr_message.lower()
            _has_curriculum_marker = any(m in _msg_lower for m in _curriculum_markers)

            # RÈGLE :
            # - "donne moi le curriculum / programme / objectifs" → programme
            #   (même avec "donne moi", car le mot 'curriculum' DOMINE)
            # - "donne moi des exercices basés sur le programme" → exercices
            #   (présence explicite du mot exercice → vraie demande d'exos)
            # → curriculum_marker l'emporte SAUF si "exercice" est explicitement mentionné
            if _has_curriculum_marker and not _has_exercice_word:
                if intent != "programme":
                    logger.info(
                        "Intent forcé à 'programme' (curriculum-query détecté)",
                        old_intent=intent,
                        message=fr_message[:80],
                    )
                intent = "programme"

            # === ÉTAPE 3a : Clarification EXERCICE (priorité absolue) ===
            # Si l'utilisateur demande des exercices SANS niveau ni matière,
            # on lui demande la précision AVANT toute autre logique. Ainsi,
            # peu importe ce que la détection PLANETE ferait, on ne saute
            # jamais cette demande de précision pour un exercice.
            if intent == "exercice":
                clarification = self._check_needs_clarification(fr_message, intent)
                if clarification:
                    # Tracker que la dernière réponse était une clarification
                    # → le résolveur de follow-up saura que le PROCHAIN message
                    # est une RÉPONSE, pas un follow-up à reformuler
                    self._update_session_state(
                        session_id,
                        intent=intent,
                        response_type="clarification",
                    )
                    response_time_ms = int((time.time() - start_time) * 1000)
                    return {
                        "response": clarification["message"],
                        "clarification": {
                            "options": clarification["options"],
                        },
                        "session_id": session_id,
                        "language": detected_lang,
                        "intent": intent,
                        "confidence": confidence,
                        "source": "clarification",
                        "response_time_ms": response_time_ms,
                        "timestamp": datetime.utcnow().isoformat(),
                    }

            # === Détection PLANETE renforcée (lexique métier) ===
            # Même si la classification d'intention n'a pas attribué "planete",
            # on inspecte le lexique pour repérer les questions implicitement
            # PLANETE ("comment configurer l'environnement physique" → planete).
            is_planete_implicit, planete_kw_count = is_planete_question(fr_message)

            # On considère la question comme PLANETE si :
            # - l'intent est explicitement "planete", OU
            # - le lexique STRONG/WEAK déclenche la détection
            # MAIS jamais quand intent est "exercice" ou "fiche" (actions
            # de génération qui ne sont pas des questions PLANETE).
            is_planete_q = (
                (intent == "planete") or is_planete_implicit
            ) and intent not in ("exercice",)

            # Réutiliser le contexte de la conversation : si la dernière
            # question était PLANETE et que le message actuel est court
            # (< 8 mots, possible suivi du type "et une salle ?"), on
            # propage l'intention PLANETE — sauf pour les exercices.
            session_state = self._get_session_state(session_id)
            if (
                not is_planete_q
                and intent != "exercice"
                and session_state.get("last_intent") == "planete"
                and len(fr_message.split()) <= 7
                and intent in ("general", "salutation")
            ):
                # Mots-clés "suite logique"
                _continuation_markers = [
                    "et", "ensuite", "puis", "après", "apres", "de même",
                    "pareil", "aussi", "et pour", "et une", "et un",
                ]
                if any(fr_message.lower().startswith(m) or m in fr_message.lower()
                       for m in _continuation_markers):
                    is_planete_q = True
                    intent = "planete"
                    logger.debug("Intent PLANETE propagé depuis l'historique")

            if is_planete_q and intent != "planete":
                # Forcer l'intention pour les downstream consumers
                intent = "planete"

            # === CHEMIN PRIORITAIRE : FAQ PLANETE (FAQ_PLANETE3.json) ===
            if (
                is_planete_q
                and self.planete_faq_service
                and self.planete_faq_service.is_available
            ):
                planete_match = await self.planete_faq_service.find_best_match(
                    fr_message
                )
                if planete_match:
                    fr_response = planete_match["answer"]
                    self._update_session_state(
                        session_id,
                        intent="planete",
                        planete_topic=planete_match.get("category"),
                    )

                    # Pas besoin de traduction (français uniquement)
                    final_response = fr_response

                    # Sauvegarde + retour
                    await self._save_message(
                        session_id=session_id,
                        user_message=message_clean,
                        assistant_response=fr_response,
                        detected_lang=detected_lang,
                        intent="planete",
                        confidence=confidence,
                        source="planete_faq",
                        db=db,
                    )

                    response_time_ms = int((time.time() - start_time) * 1000)
                    logger.info(
                        "Réponse PLANETE FAQ servie",
                        session_id=session_id,
                        score=round(planete_match["score"], 3),
                        response_time_ms=response_time_ms,
                    )
                    # Suggestions PLANETE basees sur la categorie
                    suggestions = self._build_suggestions(
                        intent="planete", niveau=None, matiere=None,
                        source="planete_faq",
                    )
                    return {
                        "response": final_response,
                        "session_id": session_id,
                        "language": detected_lang,
                        "intent": "planete",
                        "confidence": confidence,
                        "source": "planete_faq",
                        "response_time_ms": response_time_ms,
                        "timestamp": datetime.utcnow().isoformat(),
                        "planete_category": planete_match.get("category"),
                        "suggestions": suggestions,
                    }
                else:
                    logger.debug(
                        "Pas de match PLANETE FAQ, fallback vers le pipeline standard"
                    )

            # === CHEMIN RAPIDE : Clarification exercice ===
            clarification = self._check_needs_clarification(fr_message, intent)
            if clarification:
                # Tracker que la dernière réponse était une clarification
                self._update_session_state(
                    session_id,
                    intent=intent,
                    response_type="clarification",
                )
                response_time_ms = int((time.time() - start_time) * 1000)
                return {
                    "response": clarification["message"],
                    "clarification": {
                        "options": clarification["options"],
                    },
                    "session_id": session_id,
                    "language": detected_lang,
                    "intent": intent,
                    "confidence": confidence,
                    "source": "clarification",
                    "response_time_ms": response_time_ms,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            # === CHEMIN ULTRA-RAPIDE : Salutations ===
            # Intercepter les salutations AVANT la recherche FAQ et le LLM
            # Seulement si le message est court (vrais salutations, pas des questions)
            is_pure_greeting = (
                intent == "salutation"
                and len(fr_message.split()) <= 6
            )
            if is_pure_greeting:
                fr_response = self._get_greeting_response(fr_message)
                source = "greeting"

                # Pas de traduction nécessaire pour les salutations courtes
                final_response = fr_response

                # Sauvegarde en base
                await self._save_message(
                    session_id=session_id,
                    user_message=message_clean,
                    assistant_response=fr_response,
                    detected_lang=detected_lang,
                    intent=intent,
                    confidence=confidence,
                    source=source,
                    db=db
                )

                response_time_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "Salutation traitée (chemin rapide)",
                    session_id=session_id,
                    response_time_ms=response_time_ms
                )

                return {
                    "response": final_response,
                    "session_id": session_id,
                    "language": detected_lang,
                    "intent": intent,
                    "confidence": confidence,
                    "source": source,
                    "response_time_ms": response_time_ms,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            # === REFORMULATION EXERCICE (cascade ET message direct complet) ===
            # Reformule uniquement les EXERCICES (pas les fiches pédagogiques).
            # Quand le message contient niveau + matière, on envoie une instruction claire au LLM.
            FICHE_KW = ["fiche", "préparation", "preparation", "plan de leçon", "plan de cours",
                        "séance", "seance", "fiche pédagogique", "fiche pedagogique",
                        "fiche de cours", "fiche de leçon", "fiche d'enseignant",
                        "objectifs pédagogiques", "déroulement", "deroulement"]
            msg_lower_fiche_check = fr_message.lower()
            is_fiche_request = any(kw in msg_lower_fiche_check for kw in FICHE_KW)

            if intent == "exercice" and not is_fiche_request:
                import re as _re
                LEVEL_KW = ["ci","cp","ce1","ce2","cm1","cm2","primaire","élémentaire","elementaire",
                            "6ème","6eme","5ème","5eme",
                            "4ème","4eme","3ème","3eme","seconde","2nde","première","premiere",
                            "1ère","1ere","terminale","lycée","lycee","college","collège"]
                # Matières enrichies avec variantes courantes
                SUBJECT_KW = [
                    "mathématiques","mathematiques","maths","math",
                    "français","francais","lecture","expression écrite","expression ecrite",
                    "anglais","english","espagnol","arabe",
                    "sciences physiques","science physique","physique-chimie","physique chimie",
                    "physique","chimie",
                    "svt","sciences de la vie","biologie",
                    "sciences","science",
                    "histoire-géographie","histoire geographie","histoire-geo","histoire",
                    "géographie","geographie",
                    "philosophie","philo",
                    "calcul","arithmétique","arithmetique",
                    "géométrie","geometrie","algèbre","algebre",
                    "informatique","technologie",
                    "éducation civique","education civique","instruction civique",
                ]
                msg_lower_ex = fr_message.lower()

                # ─────────────────────────────────────────────────────
                # CRITIQUE : utiliser des word-boundaries pour eviter
                # les faux positifs comme "ci" dans "exerCIces" qui
                # faisait detecter le niveau CI a tort sur n'importe
                # quelle requete d'exercices.
                # ─────────────────────────────────────────────────────
                def _kw_match(kw: str, text: str) -> bool:
                    """Match un mot-cle avec word-boundary si c'est un mot
                    simple (pas d'espace ni de caractere special), sinon
                    fait un substring match classique."""
                    # Si le mot-cle contient deja un espace/tiret, on garde
                    # le substring (ex: "histoire-géographie", "expression écrite")
                    if any(c in kw for c in " -'"):
                        return kw in text
                    # Mot simple : utiliser \b mais en mode UNICODE pour
                    # gerer les accents (ème, première...)
                    pattern = rf"(?<![a-zA-Z0-9àâäéèêëïîôöùûüÿñç]){_re.escape(kw)}(?![a-zA-Z0-9àâäéèêëïîôöùûüÿñç])"
                    return bool(_re.search(pattern, text))

                found_level = next((kw for kw in LEVEL_KW if _kw_match(kw, msg_lower_ex)), None)
                # Chercher toutes les matières mentionnées (pas seulement la première)
                found_subjects = [kw for kw in SUBJECT_KW if _kw_match(kw, msg_lower_ex)]
                found_subject = found_subjects[0] if found_subjects else None
                multi_subject = len(found_subjects) > 1

                # Sous-matières français : grammaire, conjugaison, etc.
                FRENCH_SUBTOPICS_LIST = [
                    "grammaire", "conjugaison", "orthographe", "dictée", "dictee",
                    "lecture", "écriture", "ecriture", "expression écrite", "expression ecrite",
                    "vocabulaire", "rédaction", "redaction", "compréhension", "comprehension",
                    "production écrite", "production ecrite",
                    "syntaxe", "phrase", "phrases", "verbe", "verbes",
                    "synonyme", "synonymes", "antonyme", "antonymes",
                    "homonyme", "homonymes", "préfixe", "prefixe", "suffixe",
                    "lettres", "alphabet", "résumé", "resume",
                ]
                # Si une sous-matière français est détectée, l'ajouter à found_subjects
                french_subtopic = next((kw for kw in FRENCH_SUBTOPICS_LIST if _kw_match(kw, msg_lower_ex)), None)
                if french_subtopic and not found_subject:
                    found_subject = french_subtopic
                    found_subjects = [french_subtopic]

                # Détection "avec corrigé"
                CORRIGE_KW = [
                    "avec corrigé", "avec corrige", "avec les corrections", "avec correction",
                    "et corrigé", "et les corrections", "corrigés inclus", "corriges inclus",
                    "avec les corrigés", "et les corrigés"
                ]
                wants_corrige = any(kw in msg_lower_ex for kw in CORRIGE_KW)

                if found_level and found_subject:
                    level_display = found_level.upper()

                    # Extraire la quantité demandée (ex: "3 exercices", "5 questions")
                    qty_match = _re.search(r'\b(\d+)\s*(exercice|devoir|question|problème|probleme)', msg_lower_ex)
                    quantity = qty_match.group(1) if qty_match else "3"

                    corrige_instruction = (
                        " Inclus le corrigé complet après tous les exercices, dans une section ### Corrigés."
                        if wants_corrige else
                        " Ne mets PAS le corrigé, seulement les exercices."
                    )

                    # Instruction spéciale pour les matières-langues (anglais, espagnol...)
                    LANG_SUBJECTS = ["anglais","english","espagnol","arabe"]
                    is_lang_subject = any(ls in msg_lower_ex for ls in LANG_SUBJECTS)

                    if multi_subject:
                        # Plusieurs matières → garder le message original enrichi
                        fr_message = (
                            f"{fr_message}\n\n"
                            f"[INSTRUCTION] Respecte EXACTEMENT la demande : génère les exercices "
                            f"pour chaque matière demandée avec les quantités exactes mentionnées. "
                            f"Niveau : {level_display}.{corrige_instruction} N'utilise PAS de gras."
                        )
                    elif is_lang_subject:
                        # Matière langue → les exercices doivent être dans cette langue
                        lang_display = found_subject.capitalize()
                        fr_message = (
                            f"Génère {quantity} exercices de {lang_display} pour le niveau {level_display}. "
                            f"IMPORTANT : les exercices doivent être rédigés EN {lang_display.upper()} "
                            f"(textes, questions et réponses en {lang_display}). "
                            f"Adapte au niveau {level_display} du programme sénégalais. "
                            f"N'utilise PAS de gras. Séparateurs --- entre chaque exercice.{corrige_instruction}"
                        )
                    elif french_subtopic:
                        # Sous-matière français (grammaire, conjugaison, etc.)
                        subtopic_display = french_subtopic.capitalize()
                        fr_message = (
                            f"Génère {quantity} exercices de {subtopic_display} (Français) "
                            f"pour le niveau {level_display}. "
                            f"Adapte au programme officiel sénégalais de Français niveau {level_display}. "
                            f"N'utilise PAS de gras. Séparateurs --- entre chaque exercice.{corrige_instruction}"
                        )
                    else:
                        # Matière standard → instruction claire
                        subject_display = found_subject.capitalize()
                        fr_message = (
                            f"Génère {quantity} exercices complets de {subject_display} "
                            f"pour le niveau {level_display}. "
                            f"Utilise des contextes sénégalais dans les énoncés. "
                            f"N'utilise PAS de gras. Séparateurs --- entre chaque exercice.{corrige_instruction}"
                        )
                    logger.debug("Exercice reformulé", level=level_display,
                                 subject=found_subject, multi=multi_subject, qty=quantity,
                                 corrige=wants_corrige)

            # === ÉTAPE 4 : Recherche dans les FAQ (chemin rapide) ===
            # Détecter les questions de culture générale (géographie, histoire...)
            # qui ne doivent PAS être répondues par la FAQ éducative
            _general_knowledge_markers = [
                "capitale", "président", "president", "population", "superficie",
                "monnaie", "langue officielle", "drapeau", "hymne", "histoire de",
                "qui a fondé", "quand a été", "combien d'habitants", "situé",
                "quelle est la religion", "quel pays", "continent",
            ]
            _msg_lower_check = fr_message.lower()
            _is_general_knowledge = (
                intent == "general"
                and any(m in _msg_lower_check for m in _general_knowledge_markers)
            )

            # Pour l'intent "exercice", bypass total de la FAQ → aller directement au LLM
            # (sinon les FAQs sur les programmes/curricula court-circuitent la génération d'exercices)
            _skip_faq = _is_general_knowledge or (intent == "exercice")
            faq_match = None if _skip_faq else await self.faq_service.find_best_match(fr_message, "fr")
            source = "llm"
            fr_response = None

            # === CACHE LRU : éviter de regénérer une réponse identique ===
            # Pour les questions hors-FAQ (LLM), on regarde si la même
            # question a déjà été répondue. Économise quota Groq + latence.
            # Le cache est désactivé pour les exercices (réponses doivent
            # rester variées) et la culture générale.
            # On inclut le niveau et la matière courants pour éviter qu'un
            # follow-up court ("continue", "plus de détails") d'une session
            # serve la réponse d'une autre session avec un contexte différent.
            try:
                _cache_niveau = detect_niveau(fr_message) or session_state.get("last_niveau")
                _cache_matiere = detect_matiere(fr_message) or session_state.get("last_matiere")
            except Exception:
                _cache_niveau = None
                _cache_matiere = None
            cache_key = self._cache_key(
                fr_message,
                intent or "general",
                niveau=_cache_niveau,
                matiere=_cache_matiere,
            )
            if intent != "exercice" and not _is_general_knowledge:
                cached = self._llm_cache.get(cache_key)
                if cached:
                    logger.info(
                        "Réponse servie depuis le cache",
                        cache_hits=self._llm_cache.hits,
                        cache_misses=self._llm_cache.misses,
                    )
                    fr_response = cached
                    source = "cache"

            if fr_response and source == "cache":
                # Réponse récupérée du cache, on saute la suite
                pass
            elif faq_match and faq_match.get("score", 0) >= settings.FAQ_HIGH_CONFIDENCE_THRESHOLD:
                # Haute confiance : utiliser directement la réponse FAQ
                fr_response = faq_match["answer"]
                source = "faq"
                logger.info(
                    "Réponse FAQ trouvée avec haute confiance",
                    score=faq_match["score"],
                    faq_id=faq_match.get("id"),
                    category=faq_match.get("category")
                )

                # Incrémenter le compteur de vues de la FAQ
                await self._increment_faq_view(faq_match.get("id"), db)

            else:
                # === ÉTAPE 5 : Récupération de l'historique de conversation ===
                conversation_history = await self._get_conversation_history(session_id, db)

                # === GARDE-FOU FINAL : exercice sans niveau → forcer clarification ===
                # Au cas où le résolveur de follow-up et _check_needs_clarification
                # auraient laissé passer une demande d'exercice sans niveau
                # (cela arrive quand le LLM générerait pour CI par défaut),
                # on intercepte ici une dernière fois.
                if intent == "exercice":
                    niv_in_msg = detect_niveau(fr_message)
                    # Verifier aussi dans l'historique recent (3 derniers messages)
                    niv_in_history = None
                    for h in (conversation_history or [])[-6:]:
                        if h.get("role") == "user":
                            niv_in_history = detect_niveau(h.get("content", ""))
                            if niv_in_history:
                                break
                    if not niv_in_msg and not niv_in_history:
                        logger.info(
                            "Garde-fou exercice : aucun niveau détecté → clarification forcée",
                            message=fr_message[:60],
                        )
                        self._update_session_state(
                            session_id,
                            intent=intent,
                            response_type="clarification",
                        )
                        response_time_ms = int((time.time() - start_time) * 1000)
                        return {
                            "response": (
                                "Pour vous proposer des exercices parfaitement adaptés, "
                                "j'ai besoin de connaître le niveau scolaire. Quel est le niveau ?"
                            ),
                            "clarification": {
                                "options": [
                                    "CI", "CP", "CE1", "CE2", "CM1", "CM2",
                                    "6ème", "5ème", "4ème", "3ème",
                                    "2nde", "1ère", "Terminale",
                                ],
                            },
                            "session_id": session_id,
                            "language": detected_lang,
                            "intent": intent,
                            "confidence": confidence,
                            "source": "clarification",
                            "response_time_ms": response_time_ms,
                            "timestamp": datetime.utcnow().isoformat(),
                        }

                # === ÉTAPE 5b : Recherche dans la base de connaissances ===
                # Pour l'intent "exercice", on bypasse aussi le KB :
                # les documents KB sont souvent des fiches curriculum qui
                # parasitent le contexte LLM et font répondre sur les programmes
                # au lieu de générer des exercices.
                kb_context = ""
                if self.knowledge_service and self.knowledge_service.is_available and intent != "exercice":
                    try:
                        kb_docs = await self.knowledge_service.search(
                            fr_message, limit=3, category=None
                        )
                        if kb_docs:
                            kb_context = self.knowledge_service.get_context_for_llm(kb_docs)
                            source = "knowledge"
                            logger.debug(
                                "Contexte KB trouvé",
                                documents=len(kb_docs),
                                best_score=kb_docs[0].get("score", 0)
                            )
                    except Exception as exc:
                        logger.warning("Erreur recherche KB", error=str(exc))

                # === ÉTAPE 5c : Enrichir le contexte avec le Curriculum CEB ===
                # Pour la génération d'exercices ET les questions sur le programme,
                # injecter les paliers/objectifs officiels du curriculum sénégalais
                # dans le contexte LLM. Garantit que les exercices respectent les
                # objectifs officiels (paliers, OS) du Ministère.
                if (
                    self.curriculum_service
                    and self.curriculum_service.is_available
                    and intent in ("exercice", "programme", "general")
                ):
                    try:
                        niveau = detect_niveau(fr_message)
                        matiere = detect_matiere(fr_message)
                        if niveau or intent == "programme":
                            # Pour exercices : extraits ciblés (limité)
                            entries = await self.curriculum_service.get_for_level_and_subject(
                                niveau or "",
                                matiere=matiere,
                                limit=3,
                            )
                            if not entries:
                                # Fallback : recherche libre sur la requête
                                entries = await self.curriculum_service.search(
                                    fr_message,
                                    niveau=niveau,
                                    matiere=matiere,
                                    limit=3,
                                )
                            if entries:
                                curr_context = self.curriculum_service.get_curriculum_context(
                                    entries, max_chars=1200
                                )
                                if curr_context:
                                    kb_context = (
                                        f"{kb_context}\n\n{curr_context}"
                                        if kb_context else curr_context
                                    )
                                    logger.info(
                                        "Curriculum CEB injecté dans le contexte LLM",
                                        niveau=niveau, matiere=matiere,
                                        extracts=len(entries),
                                    )
                    except Exception as exc:
                        logger.warning("Erreur injection curriculum", error=str(exc))

                # === ÉTAPE 6 : Génération de réponse par le LLM ===
                # Construire le contexte utilisateur pour personnaliser la réponse
                user_ctx = None
                if user is not None:
                    user_ctx = {
                        "profile_type": user_profile,
                        "level": user_level_default,
                        "full_name": getattr(user, "full_name", None),
                        "school": getattr(user, "school", None),
                    }
                logger.debug("Génération de réponse LLM", intent=intent,
                             with_kb=bool(kb_context),
                             user_profile=user_profile)
                fr_response = await self.nlp_service.generate_response(
                    fr_message,
                    conversation_history,
                    intent,
                    knowledge_context=kb_context,
                    user_context=user_ctx,
                )
                if source != "knowledge":
                    source = "llm"

                if faq_match and faq_match.get("score", 0) >= settings.FAQ_MATCH_THRESHOLD:
                    # Correspondance FAQ moyenne : enrichir la réponse LLM avec la FAQ
                    logger.debug(
                        "Correspondance FAQ partielle trouvée",
                        score=faq_match["score"]
                    )

                # Mémoriser la réponse LLM dans le cache LRU pour les
                # prochaines questions identiques (sauf exercices et
                # culture générale, déjà filtrés en amont).
                if (
                    fr_response
                    and intent != "exercice"
                    and not _is_general_knowledge
                    and source in ("llm", "knowledge")
                ):
                    self._llm_cache.put(cache_key, fr_response)

            # === ÉTAPE 7 : Traduction de la réponse vers la langue de l'utilisateur ===
            if detected_lang != settings.PIVOT_LANGUAGE:
                logger.debug("Traduction de la réponse", target=detected_lang)
                final_response = await self.translation_service.translate_from_pivot(
                    fr_response, detected_lang
                )
            else:
                final_response = fr_response

            # === ÉTAPE 8 : Sauvegarde en base de données ===
            await self._save_message(
                session_id=session_id,
                user_message=message_clean,
                assistant_response=fr_response,
                detected_lang=detected_lang,
                intent=intent,
                confidence=confidence,
                source=source,
                db=db
            )

            # Mémoire de session : tracker l'intention + niveau + matière
            # détectés dans le message, pour résoudre les follow-ups suivants
            # (ex : "en français" après "programme CM2").
            try:
                detected_niv_save = detect_niveau(original_fr_message) or detect_niveau(fr_message)
                detected_mat_save = detect_matiere(original_fr_message) or detect_matiere(fr_message)
            except Exception:
                detected_niv_save = None
                detected_mat_save = None

            self._update_session_state(
                session_id,
                intent=intent,
                niveau=detected_niv_save,
                matiere=detected_mat_save,
                response_type=(
                    "curriculum" if intent == "programme"
                    else "exercice" if intent == "exercice"
                    else "general"
                ),
                question=original_fr_message,
                assistant_excerpt=fr_response[:300] if fr_response else None,
            )

            # Calcul du temps de réponse
            response_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Message traité avec succès",
                session_id=session_id,
                detected_lang=detected_lang,
                intent=intent,
                source=source,
                response_time_ms=response_time_ms
            )

            # Suggestions de relance contextuelles (2-3 questions)
            suggestions = self._build_suggestions(
                intent=intent,
                niveau=detected_niv_save,
                matiere=detected_mat_save,
                source=source,
            )

            return {
                "response": final_response,
                "session_id": session_id,
                "language": detected_lang,
                "intent": intent,
                "confidence": confidence,
                "source": source,
                "response_time_ms": response_time_ms,
                "timestamp": datetime.utcnow().isoformat(),
                "suggestions": suggestions,
            }

        except Exception as exc:
            logger.error(
                "Erreur lors du traitement du message",
                session_id=session_id,
                error=str(exc),
                exc_info=True
            )
            return self._build_error_response(session_id, str(exc), detected_lang if 'detected_lang' in locals() else "fr")

    async def _get_conversation_history(
        self,
        session_id: str,
        db: AsyncSession,
        limit: int = None
    ) -> list[dict]:
        """
        Récupère l'historique de conversation pour une session.

        Args:
            session_id: Identifiant de session
            db: Session de base de données
            limit: Nombre maximum de messages à récupérer

        Returns:
            Liste de messages sous forme de dicts {role, content}
        """
        if limit is None:
            limit = settings.CONTEXT_WINDOW * 2

        try:
            from sqlalchemy import select, desc
            from app.database.models import User, Conversation, Message

            # Trouver l'utilisateur par session_id
            user_stmt = select(User).where(User.session_id == session_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if not user:
                return []

            # Trouver la conversation active la plus récente
            conv_stmt = (
                select(Conversation)
                .where(
                    Conversation.user_id == user.id,
                    Conversation.is_active == True
                )
                .order_by(desc(Conversation.updated_at))
                .limit(1)
            )
            conv_result = await db.execute(conv_stmt)
            conversation = conv_result.scalar_one_or_none()

            if not conversation:
                return []

            # Récupérer les derniers messages
            msg_stmt = (
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(desc(Message.timestamp))
                .limit(limit)
            )
            msg_result = await db.execute(msg_stmt)
            messages = msg_result.scalars().all()

            # Inverser pour avoir l'ordre chronologique et formatter
            history = []
            for msg in reversed(messages):
                history.append({
                    "role": msg.role,
                    # Utiliser la version française pour le contexte LLM
                    "content": msg.translated_content or msg.content
                })

            return history

        except Exception as exc:
            logger.error("Erreur récupération historique", error=str(exc))
            return []

    async def _save_message(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        detected_lang: str,
        intent: str,
        confidence: float,
        source: str,
        db: AsyncSession,
    ) -> None:
        """
        Sauvegarde les messages utilisateur et assistant en base de données.
        Crée l'utilisateur et la conversation si nécessaire.

        Args:
            session_id: Identifiant de session
            user_message: Message original de l'utilisateur
            assistant_response: Réponse en français de l'assistant
            detected_lang: Langue détectée
            intent: Intention classifiée
            confidence: Score de confiance
            source: Source de la réponse (faq/llm)
            db: Session de base de données
        """
        try:
            from sqlalchemy import select
            from app.database.models import User, Conversation, Message

            # Créer ou récupérer l'utilisateur
            user_stmt = select(User).where(User.session_id == session_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if not user:
                user = User(
                    session_id=session_id,
                    language_preference=detected_lang
                )
                db.add(user)
                await db.flush()
                logger.debug("Nouvel utilisateur créé", session_id=session_id)

            # Mettre à jour la préférence de langue et le compteur
            user.language_preference = detected_lang
            user.total_messages = (user.total_messages or 0) + 1

            # Créer ou récupérer la conversation active
            from sqlalchemy import desc
            conv_stmt = (
                select(Conversation)
                .where(
                    Conversation.user_id == user.id,
                    Conversation.is_active == True
                )
                .order_by(desc(Conversation.updated_at))
                .limit(1)
            )
            conv_result = await db.execute(conv_stmt)
            conversation = conv_result.scalar_one_or_none()

            if not conversation:
                # Générer un titre automatique basé sur l'intention
                title = self._generate_conversation_title(user_message, intent)
                conversation = Conversation(
                    user_id=user.id,
                    language=detected_lang,
                    title=title,
                    is_active=True
                )
                db.add(conversation)
                await db.flush()
                logger.debug("Nouvelle conversation créée", conv_id=conversation.id)

            # Sauvegarder le message utilisateur
            user_msg = Message(
                conversation_id=conversation.id,
                role="user",
                content=user_message,
                language=detected_lang,
                intent=intent,
                confidence=confidence,
                source=source,
            )

            # Si la langue n'est pas le français, stocker aussi la version traduite
            if detected_lang != "fr":
                # La traduction a déjà été faite, on stocke fr_message si disponible
                pass

            db.add(user_msg)

            # Sauvegarder la réponse assistant (toujours en français pour le stockage)
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_response,
                language="fr",
                intent=intent,
                source=source,
            )
            db.add(assistant_msg)

            await db.flush()
            logger.debug(
                "Messages sauvegardés",
                user_msg_id=user_msg.id,
                assistant_msg_id=assistant_msg.id
            )

        except Exception as exc:
            logger.error(
                "Erreur sauvegarde des messages",
                session_id=session_id,
                error=str(exc),
                exc_info=True
            )

    async def _increment_faq_view(self, faq_id: Optional[int], db: AsyncSession) -> None:
        """Incrémente le compteur de vues d'une FAQ."""
        if not faq_id:
            return
        try:
            from sqlalchemy import select
            from app.database.models import FAQ

            stmt = select(FAQ).where(FAQ.id == faq_id)
            result = await db.execute(stmt)
            faq = result.scalar_one_or_none()
            if faq:
                faq.view_count = (faq.view_count or 0) + 1
        except Exception as exc:
            logger.warning("Erreur incrément vue FAQ", error=str(exc))

    def _generate_conversation_title(self, message: str, intent: str) -> str:
        """
        Génère un titre automatique pour une conversation.

        Args:
            message: Premier message de la conversation
            intent: Intention classifiée

        Returns:
            Titre de la conversation (50 caractères max)
        """
        intent_titles = {
            "inscription": "Inscription scolaire",
            "calendrier": "Calendrier scolaire",
            "examen": "Examens et résultats",
            "orientation": "Orientation scolaire",
            "bourse": "Bourses et aides",
            "programme": "Programmes scolaires",
            "administratif": "Démarches administratives",
            "enseignant": "Questions enseignants",
            "general": "Assistance éducative",
        }

        if intent in intent_titles:
            return intent_titles[intent]

        # Tronquer le message si nécessaire
        if len(message) > 50:
            return message[:47] + "..."
        return message

    async def get_session_history(
        self,
        session_id: str,
        db: AsyncSession,
        limit: int = 20
    ) -> list[dict]:
        """
        Récupère l'historique complet d'une session pour l'affichage.

        Args:
            session_id: Identifiant de session
            db: Session de base de données
            limit: Nombre maximum de messages

        Returns:
            Liste des messages avec métadonnées
        """
        try:
            from sqlalchemy import select, desc
            from app.database.models import User, Conversation, Message

            user_stmt = select(User).where(User.session_id == session_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if not user:
                return []

            conv_stmt = (
                select(Conversation)
                .where(
                    Conversation.user_id == user.id,
                    Conversation.is_active == True
                )
                .order_by(desc(Conversation.updated_at))
                .limit(1)
            )
            conv_result = await db.execute(conv_stmt)
            conversation = conv_result.scalar_one_or_none()

            if not conversation:
                return []

            msg_stmt = (
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(desc(Message.timestamp))
                .limit(limit)
            )
            msg_result = await db.execute(msg_stmt)
            messages = msg_result.scalars().all()

            history = []
            for msg in reversed(messages):
                history.append({
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "language": msg.language,
                    "intent": msg.intent,
                    "source": msg.source,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                })

            return history

        except Exception as exc:
            logger.error("Erreur récupération historique session", error=str(exc))
            return []

    async def clear_session(self, session_id: str, db: AsyncSession) -> bool:
        """
        Efface l'historique d'une session (désactive les conversations).

        Args:
            session_id: Identifiant de session
            db: Session de base de données

        Returns:
            True si l'effacement a réussi
        """
        try:
            from sqlalchemy import select, update
            from app.database.models import User, Conversation

            user_stmt = select(User).where(User.session_id == session_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if not user:
                return True

            update_stmt = (
                update(Conversation)
                .where(
                    Conversation.user_id == user.id,
                    Conversation.is_active == True
                )
                .values(is_active=False)
            )
            await db.execute(update_stmt)
            await db.flush()

            logger.info("Historique de session effacé", session_id=session_id)
            return True

        except Exception as exc:
            logger.error("Erreur effacement session", session_id=session_id, error=str(exc))
            return False

    def _check_needs_clarification(self, message: str, intent: str) -> Optional[dict]:
        """
        Vérifie si le message exercice manque d'informations essentielles
        et retourne une question de clarification avec des choix si nécessaire.
        """
        if intent != "exercice":
            return None

        import re as _re

        msg_lower = message.lower()

        # Ne pas déclencher si c'est une réponse courte à une clarification précédente
        # (ex: l'utilisateur dit juste "CM2" ou "Mathématiques")
        word_count = len(msg_lower.split())

        # ─────────────────────────────────────────────────────
        # Helper word-boundary : evite les faux positifs comme
        # "ci" dans "exerCIces" ou "math" dans "informatique".
        # ─────────────────────────────────────────────────────
        def _kw_match_strict(kw: str, text: str) -> bool:
            if any(c in kw for c in " -'"):
                return kw in text
            pattern = rf"(?<![a-zA-Z0-9àâäéèêëïîôöùûüÿñç]){_re.escape(kw)}(?![a-zA-Z0-9àâäéèêëïîôöùûüÿñç])"
            return bool(_re.search(pattern, text))

        # Mots-clés de niveau scolaire
        LEVEL_KEYWORDS = [
            "ci", "cp", "ce1", "ce2", "cm1", "cm2", "primaire", "élémentaire", "elementaire",
            "6ème", "6eme", "5ème", "5eme", "4ème", "4eme", "3ème", "3eme",
            "seconde", "2nde", "première", "premiere", "1ère", "1ere",
            "terminale", "lycée", "lycee", "college", "collège",
            "petite section", "moyenne section", "grande section", "maternelle",
            "préscolaire", "prescolaire"
        ]

        # Mots-clés de matière (alignés avec la reformulation)
        SUBJECT_KEYWORDS = [
            "mathématiques", "mathematiques", "maths", "math",
            "français", "francais", "lecture", "dictée", "dictee",
            "anglais", "english", "espagnol", "arabe",
            "sciences physiques", "science physique", "physique-chimie",
            "physique", "chimie", "svt", "biologie",
            "sciences", "science",
            "histoire-géographie", "histoire-geo", "histoire", "géographie", "geographie",
            "philosophie", "philo",
            "calcul", "géométrie", "geometrie", "algèbre", "algebre",
            "informatique", "technologie",
            "éducation civique", "education civique",
            "écriture", "ecriture",
        ]

        # Mots indiquant qu'on parle d'un enfant
        CHILD_KEYWORDS = [
            "mon fils", "ma fille", "mon enfant", "mon élève", "mon eleve",
            "mes enfants", "mes élèves", "mon petit", "ma petite"
        ]

        has_level = any(_kw_match_strict(kw, msg_lower) for kw in LEVEL_KEYWORDS)
        has_subject = any(_kw_match_strict(kw, msg_lower) for kw in SUBJECT_KEYWORDS)

        # Sous-matières du français : grammaire, conjugaison, etc. = Français
        FRENCH_SUBTOPICS = [
            "grammaire", "conjugaison", "orthographe", "dictée", "dictee",
            "lecture", "écriture", "ecriture", "expression écrite", "expression ecrite",
            "vocabulaire", "rédaction", "redaction", "compréhension", "comprehension",
            "production écrite", "production ecrite"
        ]
        if any(_kw_match_strict(kw, msg_lower) for kw in FRENCH_SUBTOPICS):
            has_subject = True  # c'est du Français

        # Demande de corrections/corrigés d'exercices déjà donnés → ne pas déclencher la clarification
        CORRECTION_FOLLOWUP = [
            "la correction", "les corrections", "le corrigé", "les corrigés",
            "les corriges", "le corrige", "les corriges",
            "donne moi les corrections", "donne les corrections",
            "donne moi le corrigé", "donne moi la correction",
            "donne la correction", "correction de ces", "correction des exercices",
            "corrigé des exercices", "corrigé de ces", "corriger ces",
            "les réponses", "les reponses", "les solutions",
        ]
        # Cas plus générique : "correction" dans le message sans demande de NOUVEAUX exercices
        WANTS_NEW = ["donne moi des exercices", "génère des exercices", "je veux des exercices",
                     "nouveaux exercices", "d'autres exercices", "autres exercices"]
        has_correction_word = any(kw in msg_lower for kw in ["correction", "corrigé", "corrige", "corriger"])
        is_new_exercise_request = any(kw in msg_lower for kw in WANTS_NEW)
        if (any(kw in msg_lower for kw in CORRECTION_FOLLOWUP)
                or (has_correction_word and not is_new_exercise_request and word_count <= 12)):
            return None  # Le LLM a le contexte — il génère les corrections

        has_fiche = any(w in msg_lower for w in [
            "fiche", "préparation", "preparation", "plan de leçon", "plan de cours",
            "séance", "seance", "fiche pédagogique", "fiche pedagogique",
            "fiche de cours", "fiche de leçon", "objectifs pédagogiques", "déroulement"
        ])

        # === Détection du cycle ===
        ELEMENTAIRE_KW = ["élémentaire", "elementaire", "primaire"]
        MOYEN_KW = ["moyen", "collège", "college"]
        LYCEE_KW = ["lycée", "lycee", "secondaire", "second cycle"]

        is_elementaire = any(kw in msg_lower for kw in ELEMENTAIRE_KW)
        is_moyen = any(kw in msg_lower for kw in MOYEN_KW)
        is_lycee = any(kw in msg_lower for kw in LYCEE_KW)

        # Inférer le cycle à partir du niveau détecté
        level_found = next((kw for kw in LEVEL_KEYWORDS if _kw_match_strict(kw, msg_lower)), "")
        if level_found in ["ci","cp","ce1","ce2","cm1","cm2","primaire","élémentaire","elementaire"]:
            is_elementaire = True
        elif level_found in ["6ème","6eme","5ème","5eme","4ème","4eme","3ème","3eme","college","collège"]:
            is_moyen = True
        elif level_found in ["seconde","2nde","première","premiere","1ère","1ere","terminale","lycée","lycee"]:
            is_lycee = True

        # Options de niveau par cycle
        # NB : au Sénégal, l'élémentaire commence par CI (Cours d'Initiation),
        # puis CP, CE1, CE2, CM1, CM2.
        if is_elementaire:
            LEVEL_OPTIONS = ["CI", "CP", "CE1", "CE2", "CM1", "CM2"]
        elif is_moyen:
            LEVEL_OPTIONS = ["6ème", "5ème", "4ème", "3ème"]
        elif is_lycee:
            LEVEL_OPTIONS = ["2nde", "1ère", "Terminale"]
        else:
            LEVEL_OPTIONS = ["CI", "CP", "CE1", "CE2", "CM1", "CM2", "6ème", "5ème", "4ème", "3ème", "2nde", "1ère", "Terminale"]

        # Options de matière par cycle
        if is_elementaire:
            SUBJECT_OPTIONS = ["Mathématiques", "Français", "Sciences", "Histoire-Géographie", "Anglais", "Éducation Civique"]
        elif is_moyen:
            SUBJECT_OPTIONS = ["Mathématiques", "Français", "Sciences Physiques", "SVT", "Histoire-Géographie", "Anglais"]
        elif is_lycee:
            SUBJECT_OPTIONS = ["Mathématiques", "Français", "Physique-Chimie", "SVT", "Histoire-Géographie", "Anglais", "Philosophie"]
        else:
            # Cycle inconnu : options neutres sans matières inexistantes au primaire
            SUBJECT_OPTIONS = ["Mathématiques", "Français", "Sciences", "Histoire-Géographie", "Anglais", "Sciences Physiques"]

        # === FICHES PÉDAGOGIQUES : clarification avec boutons ===
        if has_fiche:
            if not has_level:
                return {
                    "message": "Pour quelle classe souhaitez-vous cette fiche pédagogique ?",
                    "options": LEVEL_OPTIONS
                }
            if has_level and not has_subject:
                return {
                    "message": f"Parfait ! Dans quelle matière pour le {level_found.upper()} ?",
                    "options": SUBJECT_OPTIONS
                }
            # Niveau + matière présents → laisser le LLM générer la fiche
            return None

        # === EXERCICES : clarification avec boutons ===
        # Cas spécial : message très court (1-2 mots)
        if word_count <= 2:
            if has_level and not has_subject:
                level_display = message.strip().upper()
                return {
                    "message": f"Parfait pour le {level_display} ! Dans quelle matière souhaitez-vous des exercices ?",
                    "options": SUBJECT_OPTIONS + ["Toutes les matières"]
                }
            if has_subject and not has_level:
                return {
                    "message": "Quel est le niveau scolaire pour ces exercices ?",
                    "options": LEVEL_OPTIONS
                }
            if not has_level:
                return {
                    "message": "Pour vous proposer des exercices adaptés, j'ai besoin de connaître le niveau scolaire. Quel est le niveau ?",
                    "options": LEVEL_OPTIONS
                }
            return None

        if not has_level and not (is_elementaire or is_moyen or is_lycee):
            return {
                "message": "Pour vous proposer des exercices parfaitement adaptés, j'ai besoin de connaître le niveau scolaire. Quel est le niveau ?",
                "options": LEVEL_OPTIONS
            }

        if not has_level and (is_elementaire or is_moyen or is_lycee):
            cycle_name = "l'élémentaire" if is_elementaire else ("le moyen" if is_moyen else "le lycée")
            return {
                "message": f"Quelle classe exactement pour {cycle_name} ?",
                "options": LEVEL_OPTIONS
            }

        if has_level and not has_subject:
            return {
                "message": "Super ! Dans quelle matière souhaitez-vous des exercices ?",
                "options": SUBJECT_OPTIONS + ["Toutes les matières"]
            }

        return None

    # ═════════════════════════════════════════════════════════
    # PIPELINE V2 — refonte coeur (Sprint 1)
    # ═════════════════════════════════════════════════════════
    # Nouveau pipeline base sur :
    #   1. Classifier d'intent LLM-based (10 intents propres)
    #   2. Router par intent vers handler dedie
    #   3. SYSTEM_PROMPT modulaire (court, focalise sur la tache)
    #   4. PAS DE REFORMULATION DESTRUCTRICE du message
    # ═════════════════════════════════════════════════════════

    async def process_message_v2(
        self,
        user_message: str,
        session_id: str,
        db: AsyncSession,
        language_override: Optional[str] = None,
        user: Optional[object] = None,
    ) -> dict:
        """Pipeline V2 : classifier -> router -> handler dedie.

        Avantages sur process_message (V1) :
        - "Bonjour" reste une salutation, ne declenche plus d'exercices
        - Le message original n'est JAMAIS reecrit
        - SYSTEM_PROMPT reduit a 60-80 lignes (vs 240) selon l'intent
        - Routing modele (Haiku pour intents simples, 70B pour complexes)
        """
        start_time = time.time()

        if not user_message or not user_message.strip():
            return self._build_error_response(session_id, "Message vide", "fr")

        # Si pas de classifier dispo (init partiel), fallback sur V1
        if self.intent_classifier is None:
            logger.warning("V2 : pas de classifier, fallback V1")
            return await self.process_message(
                user_message, session_id, db, language_override, user
            )

        message_clean = user_message.strip()[:1000]
        detected_lang = "fr"  # Multi-langue traite plus tard si besoin

        try:
            # ─── Phase 1 : recuperer le contexte de session ───
            session_state = self._get_session_state(session_id)
            history = await self._get_conversation_history(session_id, db)

            user_ctx = None
            if user is not None:
                user_ctx = {
                    "profile_type": getattr(user, "profile_type", None),
                    "level": getattr(user, "level", None),
                    "full_name": getattr(user, "full_name", None),
                    "school": getattr(user, "school", None),
                }

            # ─── Phase 2 : classifier l'intent (LLM Haiku) ───
            intent_result = await self.intent_classifier.classify(
                message=message_clean,
                conversation_history=history,
                user_context=user_ctx,
            )
            intent = intent_result.primary_intent
            entities = intent_result.entities or {}
            logger.info(
                "V2 intent classifie",
                intent=intent,
                confidence=round(intent_result.confidence, 2),
                entities=entities,
            )

            # ─── Phase 3 : routing par intent ───
            response_data = await self._route_intent(
                intent_result=intent_result,
                message=message_clean,
                history=history,
                user_ctx=user_ctx,
                user=user,
                session_id=session_id,
                db=db,
            )

            response_data["session_id"] = session_id
            response_data["language"] = detected_lang
            response_data["intent"] = intent
            response_data["confidence"] = intent_result.confidence
            response_data["response_time_ms"] = int((time.time() - start_time) * 1000)
            response_data["timestamp"] = datetime.utcnow().isoformat()

            # ─── Phase 4 : sauvegarde + memoire de session ───
            await self._save_message(
                session_id=session_id,
                user_message=message_clean,
                assistant_response=response_data["response"],
                detected_lang=detected_lang,
                intent=intent,
                confidence=intent_result.confidence,
                source=response_data.get("source", "llm"),
                db=db,
            )

            self._update_session_state(
                session_id,
                intent=intent,
                niveau=entities.get("niveau"),
                matiere=entities.get("matiere"),
                response_type=intent,
                question=message_clean,
                assistant_excerpt=response_data["response"][:300],
            )

            return response_data

        except Exception as exc:
            logger.error("V2 pipeline echec, fallback V1", error=str(exc), exc_info=True)
            return await self.process_message(
                user_message, session_id, db, language_override, user
            )

    async def _route_intent(
        self,
        intent_result,
        message: str,
        history: list,
        user_ctx: Optional[dict],
        user: Optional[object],
        session_id: str,
        db: AsyncSession,
    ) -> dict:
        """Route un message vers le handler approprie selon l'intent."""
        intent = intent_result.primary_intent
        entities = intent_result.entities or {}

        # Confiance trop basse + intent = unclear -> demander clarification
        if intent == "unclear" or intent_result.confidence < 0.5:
            return await self._handle_unclear(message, history, user_ctx)

        # Salutations : reponse rapide statique (pas d'appel LLM)
        if intent == "greeting":
            return self._handle_greeting_static(user_ctx)

        # Aide PLANETE : FAQ_PLANETE3 prioritaire
        if intent == "planete_help":
            return await self._handle_planete(message, entities, user_ctx, history)

        # Demande d'exercices : delegue a la generation specialisee
        if intent == "exercise_request":
            return await self._handle_exercise(
                message, entities, user_ctx, history, session_id
            )

        # Demande de corriges : prend les exos precedents et genere leurs corrigés
        if intent == "correction_request":
            return await self._handle_correction(message, history, user_ctx, session_id=session_id)

        # Demande de fiche pedagogique : reservee aux enseignants
        if intent == "fiche_request":
            return await self._handle_fiche(message, entities, user_ctx, history)

        # Pour tous les autres intents : retrieval conditionnel + LLM modulaire
        kb_context = await self._build_kb_context(message, intent_result)
        use_fast = intent in ("smalltalk",)

        # Sprint 2 : cache LRU pour les intents stables (questions repetitives)
        # Pas de cache pour : exercise_request (variete), correction_request
        # (depend du contexte session), greeting (deja statique)
        cacheable = intent in ("factual_question", "explain", "planete_help",
                               "guidance", "smalltalk", "complaint_emotion")
        cache_key = None
        if cacheable:
            niveau = entities.get("niveau") if entities else None
            matiere = entities.get("matiere") if entities else None
            cache_key = self._cache_key(message, intent, niveau=niveau, matiere=matiere)
            cached = self._llm_cache.get(cache_key)
            if cached:
                logger.info("Cache hit V2", intent=intent,
                            hits=self._llm_cache.hits, misses=self._llm_cache.misses)
                return {
                    "response": cached,
                    "source": "cache",
                    "suggestions": self._build_suggestions(
                        intent="programme" if intent == "factual_question"
                        else intent,
                        niveau=niveau, matiere=matiere, source="cache",
                    ),
                }

        response_text = await self.nlp_service.generate_response_v2(
            message=message,
            intent=intent,
            conversation_history=history,
            user_context=user_ctx,
            knowledge_context=kb_context,
            use_fast_model=use_fast,
        )

        # Memoriser dans le cache pour les prochaines questions identiques
        if cacheable and cache_key and response_text:
            self._llm_cache.put(cache_key, response_text)
        suggestions = self._build_suggestions(
            intent="programme" if intent == "factual_question" else
                   "exercice" if intent == "exercise_request" else
                   "fiche" if intent == "fiche_request" else
                   intent,
            niveau=entities.get("niveau"),
            matiere=entities.get("matiere"),
            source="llm",
        )
        return {
            "response": response_text,
            "source": "llm" if not kb_context else "knowledge",
            "suggestions": suggestions,
        }

    def _handle_greeting_static(self, user_ctx: Optional[dict]) -> dict:
        """Salutation : reponse instantanee sans LLM."""
        first_name = None
        if user_ctx and user_ctx.get("full_name"):
            first_name = user_ctx["full_name"].split(" ")[0]
        if first_name:
            response = (
                f"Bonjour {first_name} ! 👋 Je suis EduBot, votre assistant éducatif. "
                "Comment puis-je vous aider aujourd'hui ?"
            )
        else:
            response = (
                "Bonjour ! 👋 Je suis EduBot, l'assistant éducatif "
                "du Ministère de l'Éducation Nationale du Sénégal. "
                "Comment puis-je vous aider aujourd'hui ?"
            )
        # Suggestions adaptees au profil
        profile = user_ctx.get("profile_type") if user_ctx else None
        level = user_ctx.get("level") if user_ctx else None
        if profile == "enseignant":
            suggestions = [
                "Fiche pédagogique de mathématiques pour le CM2",
                "Comment importer le personnel sur PLANETE ?",
                "Évaluation de français CE1",
            ]
        elif profile == "eleve" and level:
            suggestions = [
                f"3 exercices de maths pour le {level}",
                f"Programme de français en {level}",
                f"Comment réviser pour mon prochain examen ?",
            ]
        elif profile == "parent" and level:
            suggestions = [
                f"Que doit savoir mon enfant en {level} ?",
                f"Comment aider mon enfant en lecture ?",
                "Quel est le calendrier scolaire ?",
            ]
        else:
            suggestions = [
                "Quel est le programme de maths en CM2 ?",
                "Comment se connecter à PLANETE ?",
                "Donne-moi 3 exercices pour le CE1",
            ]
        return {"response": response, "source": "greeting", "suggestions": suggestions}

    async def _handle_unclear(
        self, message: str, history: list, user_ctx: Optional[dict]
    ) -> dict:
        """Demande de clarification structuree."""
        response = (
            "Je veux m'assurer de bien vous aider. Que souhaitez-vous faire ?"
        )
        return {
            "response": response,
            "source": "clarification",
            "clarification": {
                "options": [
                    "Une explication d'un concept",
                    "Des exercices",
                    "Une fiche pédagogique",
                    "Aide PLANETE",
                    "Conseil parental",
                    "Autre",
                ],
            },
            "suggestions": [],
        }

    async def _handle_planete(
        self, message: str, entities: dict, user_ctx: Optional[dict], history: list
    ) -> dict:
        """Recherche dans FAQ_PLANETE3, fallback LLM si pas de match."""
        if self.planete_faq_service and self.planete_faq_service.is_available:
            match = await self.planete_faq_service.find_best_match(message)
            if match:
                return {
                    "response": match["answer"],
                    "source": "planete_faq",
                    "planete_category": match.get("category"),
                    "suggestions": self._build_suggestions(
                        intent="planete", niveau=None, matiere=None, source="planete_faq"
                    ),
                }
        # Fallback LLM avec module planete_help
        text = await self.nlp_service.generate_response_v2(
            message=message,
            intent="planete_help",
            conversation_history=history,
            user_context=user_ctx,
        )
        return {
            "response": text,
            "source": "llm",
            "suggestions": self._build_suggestions(
                intent="planete", niveau=None, matiere=None, source="planete_faq"
            ),
        }

    async def _handle_exercise(
        self,
        message: str,
        entities: dict,
        user_ctx: Optional[dict],
        history: list,
        session_id: str,
    ) -> dict:
        """Genere des exercices APRES avoir verifie qu'on a tout :
        niveau (peut etre herite du profil) + matiere + quantite.

        Ordre de clarification : niveau -> matiere -> quantite -> generation.
        Le niveau peut etre herite du profil utilisateur, mais matiere et
        quantite doivent toujours etre confirmes par l'utilisateur."""
        import re as _re

        niveau = entities.get("niveau")
        matiere = entities.get("matiere")
        quantity = entities.get("quantity")

        # ─── Etape 0 : extraction depuis le message brut ───
        # Le LLM classifier extrait deja niveau/matiere, mais on tente
        # une recuperation supplementaire au cas ou (ex: "donne 5 exercices"
        # -> quantity=5 meme si le LLM ne l'a pas extrait).
        if not niveau:
            niveau = detect_niveau(message)
        if not matiere:
            mat = detect_matiere(message)
            if mat:
                matiere = mat
        if not quantity:
            qm = _re.search(r"\b(\d+)\s*(?:exercice|exo|devoir|probleme|problème|question)", message.lower())
            if qm:
                try:
                    quantity = int(qm.group(1))
                except ValueError:
                    pass

        # ─── Etape 1 : NIVEAU (avec heritage profil) ───
        if not niveau and user_ctx:
            niveau = user_ctx.get("level")

        if not niveau:
            return {
                "response": (
                    "Pour vous proposer des exercices parfaitement adaptés, "
                    "j'ai besoin de connaître le niveau scolaire. Quel niveau ?"
                ),
                "source": "clarification",
                "clarification": {
                    "options": [
                        "CI", "CP", "CE1", "CE2", "CM1", "CM2",
                        "6ème", "5ème", "4ème", "3ème",
                        "2nde", "1ère", "Terminale",
                    ],
                },
                "suggestions": [],
            }

        # ─── Etape 2 : MATIERE (toujours confirmee) ───
        if not matiere:
            # Matieres selon le programme officiel CEB du Senegal
            # https://www.education.sn (Curriculum de l'Education de Base)
            options = self._get_subjects_for_level(niveau)
            return {
                "response": (
                    f"Parfait, des exercices pour le {niveau} ! "
                    f"Dans quelle matière ?"
                ),
                "source": "clarification",
                "clarification": {"options": options},
                "suggestions": [],
            }

        # ─── Etape 3 : QUANTITE (toujours confirmee si non specifiee) ───
        if not quantity:
            return {
                "response": (
                    f"Très bien, des exercices de {matiere} pour le {niveau}. "
                    f"Combien d'exercices voulez-vous ?"
                ),
                "source": "clarification",
                "clarification": {
                    "options": ["1 exercice", "3 exercices", "5 exercices",
                                "10 exercices"],
                },
                "suggestions": [],
            }

        # ─── Etape 4 : on a tout -> generation ───
        # Recuperer le contexte CEB pour le niveau/matiere
        kb_context = ""
        if self.curriculum_service and self.curriculum_service.is_available:
            try:
                entries = await self.curriculum_service.get_for_level_and_subject(
                    niveau, matiere=matiere, limit=3,
                )
                if not entries:
                    entries = await self.curriculum_service.search(
                        message, niveau=niveau, matiere=matiere, limit=3,
                    )
                if entries:
                    kb_context = self.curriculum_service.get_curriculum_context(
                        entries, max_chars=1200
                    )
            except Exception:
                pass

        # Enrichir le message avec quantite/niveau/matiere pour que le LLM
        # genere exactement ce qui est demande (sans reformuler le message
        # original — on l'augmente uniquement avec une instruction explicite)
        enriched_message = (
            f"{message}\n\n"
            f"[INSTRUCTION] Génère exactement {quantity} exercice"
            f"{'s' if quantity > 1 else ''} de {matiere} pour le niveau {niveau}. "
            f"Format strict : ### Exercice 1 — [type], puis énoncé, puis ---, "
            f"puis ### Exercice 2 — [type], etc. "
            f"N'utilise aucun gras nulle part."
        )

        text = await self.nlp_service.generate_response_v2(
            message=enriched_message,
            intent="exercise_request",
            conversation_history=history,
            user_context=user_ctx,
            knowledge_context=kb_context,
        )

        # Memoriser les exercices pour que _handle_correction puisse les
        # retrouver meme si la BD est down (fallback SQLite ephemere)
        self._session_exercises[session_id] = text

        return {
            "response": text,
            "source": "llm",
            "suggestions": self._build_suggestions(
                intent="exercice", niveau=niveau, matiere=matiere, source="llm"
            ),
        }

    async def _handle_fiche(
        self,
        message: str,
        entities: dict,
        user_ctx: Optional[dict],
        history: list,
    ) -> dict:
        """Genere une fiche pedagogique. Reserve aux ENSEIGNANTS et autres
        professionnels — pas pour les eleves.

        Workflow :
          1. Si user=eleve : refuser poliment et rediriger vers une explication
          2. Si niveau absent : demander avec boutons
          3. Si matiere absente : demander avec boutons CEB selon niveau
          4. Generer la fiche avec contexte CEB officiel injecte
        """
        # ─── 1. Restriction profil : un eleve ne demande pas une fiche prof ───
        if user_ctx and user_ctx.get("profile_type") == "eleve":
            return {
                "response": (
                    "La fiche pédagogique est un outil destiné aux enseignants "
                    "pour préparer leurs séances de classe. En tant qu'élève, "
                    "tu n'en as pas vraiment besoin !\n\n"
                    "Mais je peux t'aider autrement — qu'est-ce qui t'intéresse ?"
                ),
                "source": "clarification",
                "clarification": {
                    "options": [
                        "Une explication d'un concept",
                        "Des exercices à faire",
                        "Réviser un sujet",
                        "Comprendre un cours",
                    ],
                },
                "suggestions": [],
            }

        niveau = entities.get("niveau")
        matiere = entities.get("matiere")
        sujet = entities.get("sujet")

        # Detection robuste depuis le message brut
        if not niveau:
            niveau = detect_niveau(message)
        if not matiere:
            mat = detect_matiere(message)
            if mat:
                matiere = mat

        # Heritage : enseignant connecte avec un niveau associe (non standard,
        # mais possible si on enrichit le profil enseignant plus tard)
        if not niveau and user_ctx and user_ctx.get("level"):
            niveau = user_ctx.get("level")

        # ─── 2. NIVEAU ───
        if not niveau:
            return {
                "response": (
                    "Pour préparer la fiche pédagogique, j'ai besoin de "
                    "connaître le niveau scolaire. Pour quelle classe ?"
                ),
                "source": "clarification",
                "clarification": {
                    "options": [
                        "CI", "CP", "CE1", "CE2", "CM1", "CM2",
                        "6ème", "5ème", "4ème", "3ème",
                        "2nde", "1ère", "Terminale",
                    ],
                },
                "suggestions": [],
            }

        # ─── 3. MATIERE (avec suggestions issues du curriculum officiel) ───
        if not matiere:
            options = self._get_subjects_for_level(niveau)
            return {
                "response": (
                    f"Très bien, une fiche pour le {niveau}. "
                    f"Dans quelle matière ?"
                ),
                "source": "clarification",
                "clarification": {"options": options},
                "suggestions": [],
            }

        # ─── 4. GENERATION avec contexte CEB ───
        kb_context = ""
        suggestions_topics: list[str] = []
        if self.curriculum_service and self.curriculum_service.is_available:
            try:
                entries = await self.curriculum_service.get_for_level_and_subject(
                    niveau, matiere=matiere, limit=4,
                )
                if not entries:
                    entries = await self.curriculum_service.search(
                        message, niveau=niveau, matiere=matiere, limit=4,
                    )
                if entries:
                    kb_context = self.curriculum_service.get_curriculum_context(
                        entries, max_chars=1500
                    )
                    # Construire 2-3 suggestions de sujets a partir des paliers
                    for e in entries[:3]:
                        title = (e.get("title") or "").strip()
                        if title:
                            # Garder un titre court "Palier X — sujet"
                            short = title.split(" - ")[0] if " - " in title else title
                            suggestions_topics.append(short[:80])
            except Exception:
                pass

        # Si l'utilisateur n'a pas precise un sujet et qu'on a des suggestions,
        # on peut lui en proposer (mais on genere quand meme une fiche generale)
        enriched_message = (
            f"{message}\n\n"
            f"[INSTRUCTION] Génère une fiche pédagogique complète pour "
            f"{matiere} en {niveau}, format strict (Discipline, Niveau, "
            f"Durée, Compétence, Objectifs, Contenu, Déroulement en tableau, "
            f"Évaluation). N'utilise aucun gras."
        )
        if sujet:
            enriched_message += f" Sujet précis : {sujet}."

        text = await self.nlp_service.generate_response_v2(
            message=enriched_message,
            intent="fiche_request",
            conversation_history=history,
            user_context=user_ctx,
            knowledge_context=kb_context,
        )

        # Suggestions de relance contextuelles
        relance = []
        if suggestions_topics:
            relance.append(
                f"Une fiche sur un autre palier de {matiere} {niveau}"
            )
        relance.append(f"Des exercices de {matiere} pour le {niveau}")
        relance.append(f"Évaluation de {matiere} pour le {niveau}")

        return {
            "response": text,
            "source": "llm",
            "suggestions": relance[:3],
        }

    @staticmethod
    def _get_subjects_for_level(niveau: str) -> list[str]:
        """Retourne les matières du programme officiel CEB selon le niveau.

        Source : Curriculum de l'Éducation de Base (CEB), Ministère de
        l'Éducation Nationale du Sénégal. Chaque niveau a ses matières
        propres (l'élémentaire combine plus de domaines, le lycée se
        spécialise par série).
        """
        # ÉLÉMENTAIRE — Étape 1 (CI/CP) : intégration forte
        if niveau in ("CI", "CP"):
            return [
                "Langue et Communication (Français)",
                "Mathématiques",
                "Découverte du Monde",
                "Éducation Physique et Sportive",
                "Vivre Ensemble",
                "Arts (Plastiques et Musique)",
            ]
        # ÉLÉMENTAIRE — Étape 2 (CE1/CE2) : amorce de l'anglais
        if niveau in ("CE1", "CE2"):
            return [
                "Mathématiques",
                "Français (Lecture, Écriture, Grammaire)",
                "Découverte du Monde (Sciences, Histoire, Géographie)",
                "Éducation Physique et Sportive",
                "Vivre Ensemble",
                "Arts",
                "Anglais (initiation)",
            ]
        # ÉLÉMENTAIRE — Étape 3 (CM1/CM2) : préparation au CFEE
        if niveau in ("CM1", "CM2"):
            return [
                "Mathématiques",
                "Français (Lecture, Production écrite, Grammaire)",
                "Sciences et Vie",
                "Histoire-Géographie",
                "Anglais",
                "Éducation Civique et Morale",
                "Éducation Physique et Sportive",
                "Arts",
            ]
        # PRÉSCOLAIRE
        if niveau == "Préscolaire":
            return [
                "Langage et Communication",
                "Découverte du Monde",
                "Activités d'éveil",
                "Anglais (initiation)",
            ]
        # COLLÈGE (6e à 3e)
        if niveau in ("6ème", "5ème", "4ème", "3ème"):
            options = [
                "Mathématiques",
                "Français",
                "Histoire-Géographie",
                "Sciences de la Vie et de la Terre (SVT)",
                "Sciences Physiques",
                "Anglais",
                "Éducation Civique et Morale",
                "Éducation Physique et Sportive",
            ]
            # LV2 à partir de la 4e
            if niveau in ("4ème", "3ème"):
                options.insert(6, "Espagnol (LV2)")
                options.insert(7, "Arabe (LV2)")
            return options
        # LYCÉE — matières communes (les séries spécialiseront ensuite)
        if niveau in ("2nde", "1ère", "Terminale"):
            return [
                "Mathématiques",
                "Français",
                "Philosophie",
                "Histoire-Géographie",
                "Sciences de la Vie et de la Terre (SVT)",
                "Physique-Chimie",
                "Anglais",
                "Espagnol",
                "Arabe",
                "Éducation Physique et Sportive",
            ]
        # Fallback : matières standard
        return [
            "Mathématiques", "Français", "Sciences",
            "Histoire-Géographie", "Anglais",
        ]

    async def _handle_correction(
        self,
        message: str,
        history: list,
        user_ctx: Optional[dict],
        session_id: Optional[str] = None,
    ) -> dict:
        """Genere les corriges des exercices presents dans l'historique recent.

        Strategie de recherche, dans l'ordre :
          1. Cache session memoire (_session_exercises) — fiable meme si BD down
          2. Historique BD (passe en parametre par process_message_v2)
        """
        last_exercises_block = None

        # 1. Cache memoire (Sprint 2)
        if session_id and session_id in self._session_exercises:
            last_exercises_block = self._session_exercises[session_id]

        # 2. Fallback sur l'historique BD
        if not last_exercises_block:
            for msg in reversed(history or []):
                if msg.get("role") != "assistant":
                    continue
                content = msg.get("content", "") or ""
                if "Exercice 1" in content or "exercice 1" in content.lower():
                    last_exercises_block = content
                    break

        # 2. Si pas d'exercices trouves, repondre honnetement
        if not last_exercises_block:
            return {
                "response": (
                    "Je ne trouve pas d'exercices à corriger dans notre conversation. "
                    "Voulez-vous que je génère des exercices, puis je vous donnerai "
                    "les corrigés tout de suite après ?"
                ),
                "source": "clarification",
                "clarification": {
                    "options": [
                        "Oui, génère 3 exercices",
                        "Oui, génère 5 exercices",
                        "Non merci",
                    ],
                },
                "suggestions": [],
            }

        # 3. Construire un message enrichi pour le LLM avec les exercices a corriger
        enriched_message = (
            f"Voici les exercices a corriger (extraits de notre conversation precedente) :\n\n"
            f"{last_exercises_block[:2500]}\n\n"
            f"--- FIN DES EXERCICES ---\n\n"
            f"Donne-moi maintenant les CORRIGÉS COMPLETS de tous ces exercices, "
            f"dans l'ordre, avec le raisonnement pas-à-pas. Format : "
            f"### Corrigés des exercices, puis ### Exercice 1, énoncé court, "
            f"Solution :, Réponse :, etc."
        )

        text = await self.nlp_service.generate_response_v2(
            message=enriched_message,
            intent="correction_request",
            conversation_history=history,
            user_context=user_ctx,
        )

        return {
            "response": text,
            "source": "llm",
            "suggestions": [
                "D'autres exercices",
                "Une fiche pédagogique",
                "Expliquer un concept",
            ],
        }

    async def _build_kb_context(self, message: str, intent_result) -> str:
        """Construit le contexte de recherche selon les besoins de l'intent."""
        needs = intent_result.needs_retrieval or []
        parts = []

        # Curriculum si demande
        if "curriculum" in needs and self.curriculum_service and self.curriculum_service.is_available:
            try:
                niveau = intent_result.entities.get("niveau") if intent_result.entities else None
                matiere = intent_result.entities.get("matiere") if intent_result.entities else None
                entries = await self.curriculum_service.search(
                    message, niveau=niveau, matiere=matiere, limit=3,
                )
                if entries:
                    ctx = self.curriculum_service.get_curriculum_context(entries, max_chars=1000)
                    if ctx:
                        parts.append(ctx)
            except Exception:
                pass

        # Knowledge base si demande
        if "knowledge" in needs and self.knowledge_service and self.knowledge_service.is_available:
            try:
                docs = await self.knowledge_service.search(message, limit=2, category=None)
                if docs:
                    parts.append(self.knowledge_service.get_context_for_llm(docs))
            except Exception:
                pass

        return "\n\n".join(parts) if parts else ""

    # ═════════════════════════════════════════════════════════
    # FIN PIPELINE V2
    # ═════════════════════════════════════════════════════════

    def _get_greeting_response(self, message: str) -> str:
        """Délègue à NLPService pour avoir une seule source de vérité.
        Évite la dérive entre les deux implémentations historiques."""
        return self.nlp_service._get_greeting_response(message)

    def _build_error_response(
        self,
        session_id: str,
        error: str,
        language: str
    ) -> dict:
        """
        Construit une réponse d'erreur formatée.

        Args:
            session_id: Identifiant de session
            error: Message d'erreur
            language: Langue de la réponse

        Returns:
            Dictionnaire de réponse d'erreur
        """
        error_messages = {
            "fr": "Je suis désolé, une erreur technique s'est produite. Veuillez réessayer.",
            "wo": "Baal ma, dafa dëkk ay xeex teknik. Jëfandikool ak yeneen.",
            "ff": "Yaafo, goɗɗi faandu teknik. Cooto kadi.",
            "ar": "أعتذر، حدث خطأ تقني. يرجى المحاولة مرة أخرى.",
        }

        return {
            "response": error_messages.get(language, error_messages["fr"]),
            "session_id": session_id,
            "language": language,
            "intent": "error",
            "confidence": 0.0,
            "source": "error",
            "response_time_ms": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "error": error,
        }
