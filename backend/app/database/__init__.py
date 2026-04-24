"""
Package de base de données - connexion et modèles SQLAlchemy.
"""

from .connection import get_db, create_tables, engine
from .models import Base, User, Conversation, Message, FAQ, KnowledgeEntry

__all__ = [
    "get_db",
    "create_tables",
    "engine",
    "Base",
    "User",
    "Conversation",
    "Message",
    "FAQ",
    "KnowledgeEntry",
]
