"""
Modèles SQLAlchemy pour la base de données du chatbot éducatif.
Définit les entités : Utilisateur, Conversation, Message, FAQ, KnowledgeEntry.
"""

import json
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, Float, Index, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Classe de base pour tous les modèles SQLAlchemy."""
    __allow_unmapped__ = True
    pass


class User(Base):
    """
    Représente un utilisateur du chatbot.

    Deux modes coexistent :
      1. INVITÉ : identifié par session_id (UUID), aucun champ d'auth rempli.
      2. AUTHENTIFIÉ : profile_type renseigné + au moins un identifiant
         (ien, email pro, telephone). Connexion via mot de passe ou OTP.
    """
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id: str = Column(String(36), unique=True, nullable=False, index=True,
                             comment="UUID de session généré côté client")
    language_preference: str = Column(String(5), nullable=False, default="fr",
                                      comment="Langue préférée de l'utilisateur (fr, wo, ff, ar)")
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now(),
                                  comment="Date de création du profil")
    last_active: datetime = Column(DateTime(timezone=True), server_default=func.now(),
                                   onupdate=func.now(),
                                   comment="Dernière activité de l'utilisateur")
    total_messages: int = Column(Integer, default=0,
                                 comment="Nombre total de messages envoyés")

    # ─────────────────────────────────────────────────────────
    # AUTHENTIFICATION (tous nullable pour préserver le mode invité)
    # ─────────────────────────────────────────────────────────
    auth_method: Optional[str] = Column(String(20), nullable=True,
                                        comment="Méthode utilisée : ien | email | phone | None (invité)")
    ien: Optional[str] = Column(String(20), unique=True, nullable=True, index=True,
                                comment="Identifiant Education Nationale")
    email: Optional[str] = Column(String(120), unique=True, nullable=True, index=True,
                                  comment="Adresse e-mail (pro ou perso)")
    phone: Optional[str] = Column(String(20), unique=True, nullable=True, index=True,
                                  comment="Numéro de téléphone international (+221...)")
    password_hash: Optional[str] = Column(String(200), nullable=True,
                                          comment="Hash bcrypt du mot de passe (mode IEN)")
    profile_type: Optional[str] = Column(String(20), nullable=True, index=True,
                                         comment="enseignant | eleve | parent | autre")
    full_name: Optional[str] = Column(String(100), nullable=True,
                                      comment="Nom complet de l'utilisateur")
    school: Optional[str] = Column(String(150), nullable=True,
                                   comment="Établissement scolaire")
    level: Optional[str] = Column(String(20), nullable=True,
                                  comment="Niveau scolaire (CI..Terminale) — utile pour élève/parent")
    is_active: bool = Column(Boolean, default=True, nullable=False,
                             comment="Compte actif (False = bloqué)")
    last_login_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True,
                                               comment="Dernière connexion authentifiée")

    # Relations
    conversations: List["Conversation"] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_authenticated(self) -> bool:
        """True si l'utilisateur est connecté (a un profil + au moins un identifiant)."""
        return bool(self.profile_type) and bool(self.ien or self.email or self.phone)

    def public_dict(self) -> dict:
        """Représentation publique du profil (pas de hash, pas de session)."""
        return {
            "id": self.id,
            "profile_type": self.profile_type,
            "full_name": self.full_name,
            "school": self.school,
            "level": self.level,
            "auth_method": self.auth_method,
            "is_authenticated": self.is_authenticated,
            "language_preference": self.language_preference,
        }

    def __repr__(self) -> str:
        return f"<User(id={self.id}, session_id={self.session_id}, profile={self.profile_type})>"


class Conversation(Base):
    """
    Représente une conversation entre un utilisateur et le chatbot.
    Permet de regrouper les messages par session de discussion.
    """
    __tablename__ = "conversations"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    title: str = Column(String(200), nullable=True,
                        comment="Titre automatique de la conversation")
    language: str = Column(String(5), nullable=False, default="fr",
                           comment="Langue principale de la conversation")
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: datetime = Column(DateTime(timezone=True), server_default=func.now(),
                                  onupdate=func.now())
    is_active: bool = Column(Boolean, default=True,
                             comment="Indique si la conversation est active")

    # Relations
    user: "User" = relationship("User", back_populates="conversations")
    messages: List["Message"] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.timestamp"
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, user_id={self.user_id}, lang={self.language})>"


class Message(Base):
    """
    Représente un message individuel dans une conversation.
    Stocke le contenu original et la traduction française (pivot).
    """
    __tablename__ = "messages"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id: int = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"),
                                  nullable=False, index=True)
    role: str = Column(String(20), nullable=False,
                       comment="Rôle de l'émetteur : 'user' ou 'assistant'")
    content: str = Column(Text, nullable=False,
                          comment="Contenu original du message dans la langue de l'utilisateur")
    language: str = Column(String(5), nullable=False, default="fr",
                           comment="Langue du message original")
    translated_content: Optional[str] = Column(Text, nullable=True,
                                               comment="Traduction française du message (si applicable)")
    timestamp: datetime = Column(DateTime(timezone=True), server_default=func.now(),
                                 index=True)
    intent: Optional[str] = Column(String(50), nullable=True,
                                   comment="Intention classifiée du message")
    confidence: Optional[float] = Column(Float, nullable=True,
                                         comment="Score de confiance de la classification")
    source: str = Column(String(20), nullable=True, default="llm",
                         comment="Source de la réponse : 'faq' ou 'llm'")
    response_time_ms: Optional[int] = Column(Integer, nullable=True,
                                             comment="Temps de réponse en millisecondes")

    # Relations
    conversation: "Conversation" = relationship("Conversation", back_populates="messages")

    # Index composé pour optimiser la récupération des historiques
    __table_args__ = (
        Index("ix_messages_conv_timestamp", "conversation_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role}, lang={self.language})>"


class FAQ(Base):
    """
    Représente une entrée de la Foire Aux Questions.
    Les embeddings vectoriels sont stockés en JSON pour la recherche sémantique.
    """
    __tablename__ = "faqs"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    question: str = Column(Text, nullable=False,
                           comment="Question en langue originale")
    answer: str = Column(Text, nullable=False,
                         comment="Réponse complète à la question")
    category: str = Column(String(50), nullable=False, index=True,
                           comment="Catégorie de la FAQ (inscription, examen, etc.)")
    language: str = Column(String(5), nullable=False, default="fr", index=True,
                           comment="Langue de la question/réponse")
    embedding: Optional[str] = Column(Text, nullable=True,
                                      comment="Embedding vectoriel sérialisé en JSON")
    tags: Optional[str] = Column(Text, nullable=True,
                                 comment="Tags JSON pour la recherche")
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: datetime = Column(DateTime(timezone=True), server_default=func.now(),
                                  onupdate=func.now())
    is_active: bool = Column(Boolean, default=True, index=True,
                             comment="Indique si la FAQ est active")
    view_count: int = Column(Integer, default=0,
                             comment="Nombre de fois que cette FAQ a été consultée")

    def get_embedding(self) -> Optional[List[float]]:
        """Désérialise l'embedding JSON."""
        if self.embedding:
            return json.loads(self.embedding)
        return None

    def set_embedding(self, embedding: List[float]) -> None:
        """Sérialise l'embedding en JSON."""
        self.embedding = json.dumps(embedding)

    def get_tags(self) -> List[str]:
        """Désérialise les tags JSON."""
        if self.tags:
            return json.loads(self.tags)
        return []

    def set_tags(self, tags: List[str]) -> None:
        """Sérialise les tags en JSON."""
        self.tags = json.dumps(tags)

    def __repr__(self) -> str:
        return f"<FAQ(id={self.id}, category={self.category}, lang={self.language})>"


class KnowledgeEntry(Base):
    """
    Représente une entrée de la base de connaissances sur le système éducatif sénégalais.
    """
    __tablename__ = "knowledge_entries"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title: str = Column(String(200), nullable=False,
                        comment="Titre de l'entrée")
    content: str = Column(Text, nullable=False,
                          comment="Contenu détaillé de l'entrée")
    category: str = Column(String(50), nullable=False, index=True,
                           comment="Catégorie (structure, examen, programme, etc.)")
    language: str = Column(String(5), nullable=False, default="fr",
                           comment="Langue de l'entrée")
    tags: Optional[str] = Column(Text, nullable=True,
                                 comment="Tags JSON pour la recherche")
    embedding: Optional[str] = Column(Text, nullable=True,
                                      comment="Embedding vectoriel sérialisé en JSON")
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: datetime = Column(DateTime(timezone=True), server_default=func.now(),
                                  onupdate=func.now())
    is_active: bool = Column(Boolean, default=True)

    def get_tags(self) -> List[str]:
        """Désérialise les tags JSON."""
        if self.tags:
            return json.loads(self.tags)
        return []

    def set_tags(self, tags: List[str]) -> None:
        """Sérialise les tags en JSON."""
        self.tags = json.dumps(tags)

    def __repr__(self) -> str:
        return f"<KnowledgeEntry(id={self.id}, title={self.title[:30]}, lang={self.language})>"


class UsageStats(Base):
    """
    Statistiques agrégées d'utilisation pour le tableau de bord administrateur.
    """
    __tablename__ = "usage_stats"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    date: datetime = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    total_messages: int = Column(Integer, default=0)
    faq_hits: int = Column(Integer, default=0)
    llm_calls: int = Column(Integer, default=0)
    language_fr: int = Column(Integer, default=0)
    language_wo: int = Column(Integer, default=0)
    language_ff: int = Column(Integer, default=0)
    language_ar: int = Column(Integer, default=0)
    avg_response_time_ms: float = Column(Float, default=0.0)
    unique_sessions: int = Column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<UsageStats(date={self.date}, messages={self.total_messages})>"


# ══════════════════════════════════════════════════════════════
#  SYSTÈME D'APPRENTISSAGE PROGRESSIF — EduBot Learning Platform
# ══════════════════════════════════════════════════════════════

class Lesson(Base):
    """
    Représente une leçon dans le parcours d'apprentissage.
    Les leçons se débloquent séquentiellement selon l'ordre défini.
    """
    __tablename__ = "lessons"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title: str = Column(String(200), nullable=False, comment="Titre de la leçon")
    subject: str = Column(String(50), nullable=False, index=True,
                          comment="Matière : mathematiques, francais, sciences, anglais, histoire-geo...")
    level: str = Column(String(20), nullable=False, index=True,
                        comment="Niveau scolaire : CI, CP, CE1, CE2, CM1, CM2, 6eme, 5eme...")
    order_in_subject: int = Column(Integer, nullable=False, default=1,
                                   comment="Ordre de la leçon dans la matière (1=première)")
    content: str = Column(Text, nullable=False, comment="Contenu pédagogique de la leçon (Markdown)")
    summary: str = Column(String(500), nullable=True, comment="Résumé court de la leçon")
    duration_minutes: int = Column(Integer, default=20, comment="Durée estimée en minutes")
    prerequisite_lesson_id: Optional[int] = Column(Integer, ForeignKey("lessons.id"), nullable=True,
                                                    comment="Leçon à compléter avant d'accéder à celle-ci")
    is_active: bool = Column(Boolean, default=True)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    exercises: List["Exercise"] = relationship("Exercise", back_populates="lesson",
                                                cascade="all, delete-orphan")
    progress_records: List["StudentProgress"] = relationship("StudentProgress",
                                                              back_populates="lesson",
                                                              cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_lessons_level_subject_order", "level", "subject", "order_in_subject"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "subject": self.subject,
            "level": self.level,
            "order": self.order_in_subject,
            "summary": self.summary,
            "duration_minutes": self.duration_minutes,
            "prerequisite_lesson_id": self.prerequisite_lesson_id,
        }

    def __repr__(self) -> str:
        return f"<Lesson(id={self.id}, level={self.level}, subject={self.subject}, order={self.order_in_subject})>"


class Exercise(Base):
    """
    Exercice ou question d'évaluation associé à une leçon.
    Types : qcm (choix multiple), vrai_faux, texte_libre, calcul.
    """
    __tablename__ = "exercises"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    lesson_id: int = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    question: str = Column(Text, nullable=False, comment="Énoncé de la question")
    exercise_type: str = Column(String(20), nullable=False, default="qcm",
                                comment="Type : qcm | vrai_faux | texte_libre | calcul")
    options: Optional[str] = Column(Text, nullable=True,
                                    comment="Options JSON pour QCM : [{'label':'A','text':'...'}]")
    correct_answer: str = Column(Text, nullable=False,
                                 comment="Réponse correcte (lettre pour QCM, texte sinon)")
    explanation: Optional[str] = Column(Text, nullable=True,
                                        comment="Explication de la bonne réponse affichée après correction")
    points: int = Column(Integer, default=1, comment="Points attribués si réponse correcte")
    order_in_lesson: int = Column(Integer, default=1)
    is_active: bool = Column(Boolean, default=True)

    # Relations
    lesson: "Lesson" = relationship("Lesson", back_populates="exercises")
    grades: List["Grade"] = relationship("Grade", back_populates="exercise",
                                          cascade="all, delete-orphan")

    def get_options(self) -> list:
        if self.options:
            return json.loads(self.options)
        return []

    def set_options(self, options: list) -> None:
        self.options = json.dumps(options, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "lesson_id": self.lesson_id,
            "question": self.question,
            "type": self.exercise_type,
            "options": self.get_options(),
            "points": self.points,
            "order": self.order_in_lesson,
        }

    def __repr__(self) -> str:
        return f"<Exercise(id={self.id}, type={self.exercise_type}, lesson_id={self.lesson_id})>"


class StudentProgress(Base):
    """
    Suivi de la progression d'un élève sur chaque leçon.
    Statuts : not_started → in_progress → completed.
    """
    __tablename__ = "student_progress"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    lesson_id: int = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    status: str = Column(String(20), nullable=False, default="not_started",
                         comment="not_started | in_progress | completed")
    score: Optional[float] = Column(Float, nullable=True,
                                    comment="Score obtenu sur les exercices (0-100)")
    attempts: int = Column(Integer, default=0, comment="Nombre de tentatives")
    started_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    completed_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    time_spent_minutes: int = Column(Integer, default=0, comment="Temps passé en minutes")
    unlocked: bool = Column(Boolean, default=False,
                            comment="True si la leçon est débloquée pour cet élève")

    # Relations
    user: "User" = relationship("User")
    lesson: "Lesson" = relationship("Lesson", back_populates="progress_records")

    __table_args__ = (
        Index("ix_progress_user_lesson", "user_id", "lesson_id", unique=True),
    )

    def to_dict(self) -> dict:
        return {
            "lesson_id": self.lesson_id,
            "status": self.status,
            "score": self.score,
            "attempts": self.attempts,
            "unlocked": self.unlocked,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def __repr__(self) -> str:
        return f"<StudentProgress(user={self.user_id}, lesson={self.lesson_id}, status={self.status})>"


class Grade(Base):
    """
    Note d'un élève sur un exercice spécifique.
    Permet de stocker l'historique des réponses et les notes obtenues.
    """
    __tablename__ = "grades"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    exercise_id: int = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    student_answer: str = Column(Text, nullable=False, comment="Réponse soumise par l'élève")
    is_correct: bool = Column(Boolean, nullable=False, comment="True si réponse correcte")
    points_earned: int = Column(Integer, default=0, comment="Points effectivement gagnés")
    submitted_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    attempt_number: int = Column(Integer, default=1)

    # Relations
    exercise: "Exercise" = relationship("Exercise", back_populates="grades")

    def to_dict(self) -> dict:
        return {
            "exercise_id": self.exercise_id,
            "student_answer": self.student_answer,
            "is_correct": self.is_correct,
            "points_earned": self.points_earned,
            "submitted_at": self.submitted_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<Grade(user={self.user_id}, exercise={self.exercise_id}, correct={self.is_correct})>"


class DiagnosticSession(Base):
    """
    Session de diagnostic initial menée par EduBot à la première connexion.
    EduBot pose des questions par matière pour déterminer le niveau réel de l'élève.
    """
    __tablename__ = "diagnostic_sessions"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                          nullable=False, index=True, unique=True,
                          comment="Un seul diagnostic par élève")
    declared_level: str = Column(String(20), nullable=False,
                                 comment="Niveau déclaré à l'inscription")
    evaluated_level: Optional[str] = Column(String(20), nullable=True,
                                             comment="Niveau évalué après le diagnostic")
    questions_asked: Optional[str] = Column(Text, nullable=True,
                                             comment="Questions posées (JSON)")
    answers_given: Optional[str] = Column(Text, nullable=True,
                                           comment="Réponses de l'élève (JSON)")
    scores_by_subject: Optional[str] = Column(Text, nullable=True,
                                               comment="Scores par matière (JSON) : {math: 75, fr: 60}")
    recommended_path: Optional[str] = Column(Text, nullable=True,
                                              comment="Parcours recommandé (JSON liste de lesson_ids)")
    status: str = Column(String(20), default="pending",
                         comment="pending | in_progress | completed")
    started_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    completed_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)

    def get_scores(self) -> dict:
        if self.scores_by_subject:
            return json.loads(self.scores_by_subject)
        return {}

    def set_scores(self, scores: dict) -> None:
        self.scores_by_subject = json.dumps(scores)

    def get_questions(self) -> list:
        if self.questions_asked:
            return json.loads(self.questions_asked)
        return []

    def get_answers(self) -> list:
        if self.answers_given:
            return json.loads(self.answers_given)
        return []

    def __repr__(self) -> str:
        return f"<DiagnosticSession(user={self.user_id}, status={self.status}, level={self.evaluated_level})>"


class TutorRequest(Base):
    """
    Demande d'aide d'un élève vers son tuteur assigné.
    L'élève peut aussi choisir de demander l'aide d'EduBot (IA).
    """
    __tablename__ = "tutor_requests"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    tutor_id: Optional[int] = Column(Integer, ForeignKey("users.id"), nullable=True,
                                      comment="NULL si aide demandée à l'IA")
    lesson_id: Optional[int] = Column(Integer, ForeignKey("lessons.id"), nullable=True,
                                       comment="Leçon concernée par la demande")
    exercise_id: Optional[int] = Column(Integer, ForeignKey("exercises.id"), nullable=True,
                                         comment="Exercice concerné (optionnel)")
    message: str = Column(Text, nullable=False, comment="Message de l'élève")
    request_type: str = Column(String(20), default="tutor",
                               comment="tutor | ai | both")
    status: str = Column(String(20), default="pending",
                         comment="pending | seen | answered | closed")
    response: Optional[str] = Column(Text, nullable=True,
                                      comment="Réponse du tuteur ou de l'IA")
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    responded_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)

    student: "User" = relationship("User", foreign_keys=[student_id])
    tutor: Optional["User"] = relationship("User", foreign_keys=[tutor_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "lesson_id": self.lesson_id,
            "message": self.message,
            "request_type": self.request_type,
            "status": self.status,
            "response": self.response,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<TutorRequest(student={self.student_id}, status={self.status}, type={self.request_type})>"


class VolunteerApplication(Base):
    """
    Candidature d'un volontaire souhaitant devenir tuteur.
    Les superviseurs/admins examinent les candidatures et les approuvent ou rejettent.
    """
    __tablename__ = "volunteer_applications"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    motivation: str = Column(Text, nullable=False, comment="Lettre de motivation")
    experience: str = Column(Text, nullable=False, comment="Expérience en enseignement")
    education: str = Column(String(100), nullable=False, comment="Niveau d'études")
    subjects: str = Column(Text, nullable=False, comment="Matières JSON: ['francais','maths']")
    levels: str = Column(Text, nullable=False, comment="Niveaux JSON: ['CI','CP','CE1']")
    availability: str = Column(String(50), nullable=False, default="both",
                               comment="weekdays | weekends | both")
    document_path: Optional[str] = Column(String(500), nullable=True,
                                          comment="Chemin du fichier CV/diplôme uploadé")
    document_name: Optional[str] = Column(String(255), nullable=True,
                                          comment="Nom original du fichier")
    status: str = Column(String(20), default="pending",
                         comment="pending | approved | rejected")
    reviewer_id: Optional[int] = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer_notes: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)

    applicant: "User" = relationship("User", foreign_keys=[user_id])
    reviewer: Optional["User"] = relationship("User", foreign_keys=[reviewer_id])

    def get_subjects(self) -> list:
        try:
            return json.loads(self.subjects)
        except Exception:
            return []

    def get_levels(self) -> list:
        try:
            return json.loads(self.levels)
        except Exception:
            return []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "motivation": self.motivation,
            "experience": self.experience,
            "education": self.education,
            "subjects": self.get_subjects(),
            "levels": self.get_levels(),
            "availability": self.availability,
            "document_name": self.document_name,
            "status": self.status,
            "reviewer_notes": self.reviewer_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }

    def __repr__(self) -> str:
        return f"<VolunteerApplication(user={self.user_id}, status={self.status})>"
