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
