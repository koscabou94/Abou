"""
Service principal d'orchestration du chatbot.
Coordonne la détection de langue, la traduction, la classification d'intention,
la recherche FAQ et la génération de réponses LLM.
"""

import time
import uuid
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

logger = structlog.get_logger(__name__)


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
    ) -> None:
        """
        Initialise le service de chat avec ses dépendances.

        Args:
            language_service: Service de détection de langue
            translation_service: Service de traduction NLLB-200
            nlp_service: Service LLM pour la génération de réponses
            faq_service: Service de recherche dans les FAQ
            knowledge_service: Service de recherche dans la base de connaissances
        """
        self.language_service = language_service
        self.translation_service = translation_service
        self.nlp_service = nlp_service
        self.faq_service = faq_service
        self.knowledge_service = knowledge_service
        logger.info(
            "Service de chat initialisé avec succès",
            knowledge_available=knowledge_service is not None
        )

    async def process_message(
        self,
        user_message: str,
        session_id: str,
        db: AsyncSession,
        language_override: Optional[str] = None,
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

            # === ÉTAPE 3 : Classification de l'intention ===
            intent, confidence = self.nlp_service.classify_intent(fr_message)
            logger.debug("Intention classifiée", intent=intent, confidence=confidence)

            # === CHEMIN RAPIDE : Clarification exercice ===
            clarification = self._check_needs_clarification(fr_message, intent)
            if clarification:
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
                LEVEL_KW = ["cp","ce1","ce2","cm1","cm2","primaire","6ème","6eme","5ème","5eme",
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
                found_level = next((kw for kw in LEVEL_KW if kw in msg_lower_ex), None)
                # Chercher toutes les matières mentionnées (pas seulement la première)
                found_subjects = [kw for kw in SUBJECT_KW if kw in msg_lower_ex]
                found_subject = found_subjects[0] if found_subjects else None
                multi_subject = len(found_subjects) > 1

                if found_level and found_subject:
                    level_display = found_level.upper()

                    # Extraire la quantité demandée (ex: "3 exercices", "5 questions")
                    qty_match = _re.search(r'\b(\d+)\s*(exercice|devoir|question|problème|probleme)', msg_lower_ex)
                    quantity = qty_match.group(1) if qty_match else "3"

                    # Instruction spéciale pour les matières-langues (anglais, espagnol...)
                    LANG_SUBJECTS = ["anglais","english","espagnol","arabe"]
                    is_lang_subject = any(ls in msg_lower_ex for ls in LANG_SUBJECTS)

                    if multi_subject:
                        # Plusieurs matières → garder le message original enrichi
                        fr_message = (
                            f"{fr_message}\n\n"
                            f"[INSTRUCTION] Respecte EXACTEMENT la demande : génère les exercices "
                            f"pour chaque matière demandée avec les quantités exactes mentionnées. "
                            f"Niveau : {level_display}. N'utilise PAS de gras."
                        )
                    elif is_lang_subject:
                        # Matière langue → les exercices doivent être dans cette langue
                        lang_display = found_subject.capitalize()
                        fr_message = (
                            f"Génère {quantity} exercices de {lang_display} pour le niveau {level_display}. "
                            f"IMPORTANT : les exercices doivent être rédigés EN {lang_display.upper()} "
                            f"(textes, questions et réponses en {lang_display}). "
                            f"Adapte au niveau {level_display} du programme sénégalais. "
                            f"N'utilise PAS de gras. Séparateurs --- entre chaque exercice."
                        )
                    else:
                        # Matière standard → instruction claire
                        subject_display = found_subject.capitalize()
                        fr_message = (
                            f"Génère {quantity} exercices complets de {subject_display} "
                            f"pour le niveau {level_display}. "
                            f"Utilise des contextes sénégalais dans les énoncés. "
                            f"N'utilise PAS de gras. Séparateurs --- entre chaque exercice."
                        )
                    logger.debug("Exercice reformulé", level=level_display,
                                 subject=found_subject, multi=multi_subject, qty=quantity)

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

            if faq_match and faq_match.get("score", 0) >= settings.FAQ_HIGH_CONFIDENCE_THRESHOLD:
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

                # === ÉTAPE 5b : Recherche dans la base de connaissances ===
                # Pour l'intent "exercice", on bypasse aussi le KB :
                # les documents KB sont souvent des fiches curriculum qui
                # parasitent le contexte LLM et font répondre sur les programmes
                # au lieu de générer des exercices.
                kb_context = ""
                if self.knowledge_service and self.knowledge_service.is_available and intent != "exercice":
                    try:
                        kb_docs = await self.knowledge_service.search(
                            fr_message, limit=1, category=None
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

                # === ÉTAPE 6 : Génération de réponse par le LLM ===
                logger.debug("Génération de réponse LLM", intent=intent, with_kb=bool(kb_context))
                fr_response = await self.nlp_service.generate_response(
                    fr_message,
                    conversation_history,
                    intent,
                    knowledge_context=kb_context
                )
                if source != "knowledge":
                    source = "llm"

                if faq_match and faq_match.get("score", 0) >= settings.FAQ_MATCH_THRESHOLD:
                    # Correspondance FAQ moyenne : enrichir la réponse LLM avec la FAQ
                    logger.debug(
                        "Correspondance FAQ partielle trouvée",
                        score=faq_match["score"]
                    )

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

        msg_lower = message.lower()

        # Ne pas déclencher si c'est une réponse courte à une clarification précédente
        # (ex: l'utilisateur dit juste "CM2" ou "Mathématiques")
        word_count = len(msg_lower.split())

        # Mots-clés de niveau scolaire
        LEVEL_KEYWORDS = [
            "cp", "ce1", "ce2", "cm1", "cm2", "primaire",
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

        has_level = any(kw in msg_lower for kw in LEVEL_KEYWORDS)
        has_subject = any(kw in msg_lower for kw in SUBJECT_KEYWORDS)
        has_fiche = any(w in msg_lower for w in [
            "fiche", "préparation", "preparation", "plan de leçon", "plan de cours",
            "séance", "seance", "fiche pédagogique", "fiche pedagogique",
            "fiche de cours", "fiche de leçon", "objectifs pédagogiques", "déroulement"
        ])

        LEVEL_OPTIONS = ["CP", "CE1", "CE2", "CM1", "CM2", "6ème", "5ème", "4ème", "3ème", "2nde", "1ère", "Terminale"]
        SUBJECT_OPTIONS = ["Mathématiques", "Français", "Sciences", "Histoire-Géographie", "Anglais", "Physique-Chimie"]

        # === FICHES PÉDAGOGIQUES : clarification avec boutons ===
        if has_fiche:
            if not has_level:
                return {
                    "message": "Pour quelle classe souhaitez-vous cette fiche pédagogique ?",
                    "options": LEVEL_OPTIONS
                }
            if has_level and not has_subject:
                level_found = next((kw for kw in LEVEL_KEYWORDS if kw in msg_lower), "")
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

        if not has_level:
            return {
                "message": "Pour vous proposer des exercices parfaitement adaptés, j'ai besoin de connaître le niveau scolaire. Quel est le niveau ?",
                "options": LEVEL_OPTIONS
            }

        if has_level and not has_subject:
            return {
                "message": "Super ! Dans quelle matière souhaitez-vous des exercices ?",
                "options": SUBJECT_OPTIONS + ["Toutes les matières"]
            }

        return None

    def _get_greeting_response(self, message: str) -> str:
        """
        Retourne une réponse de salutation instantanée.
        Correspond exactement aux réponses demandées par l'utilisateur.

        Args:
            message: Message en français de l'utilisateur

        Returns:
            Réponse de salutation
        """
        msg_lower = message.lower().strip()

        # Détection de remerciements
        if any(w in msg_lower for w in ["merci", "thanks"]):
            return "Avec plaisir ! N'hésitez pas si vous avez d'autres questions. 😊"

        # Détection d'au revoir
        if any(w in msg_lower for w in ["au revoir", "bonne journée", "bonne soirée", "bye"]):
            return "Au revoir et bonne continuation ! 👋"

        # Détection "comment ça va"
        if any(w in msg_lower for w in ["comment ça va", "comment ca va", "ça va", "ca va"]):
            return "Je vais bien, merci ! Comment puis-je vous aider ? 😊"

        # Bonsoir
        if "bonsoir" in msg_lower:
            return "Bonsoir ! 👋 Je suis votre assistant éducatif. Que puis-je faire pour vous ?"

        # Salut
        if "salut" in msg_lower:
            return "Salut ! 👋 Je suis votre assistant éducatif. Que puis-je faire pour vous ?"

        # Bonjour (et tout le reste)
        return "Bonjour ! 👋 Je suis votre assistant éducatif. Que puis-je faire pour vous ?"

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
