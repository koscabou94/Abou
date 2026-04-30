"""
Package des routes API de l'application.
"""

from .chat import router as chat_router
from .faq import router as faq_router
from .admin import router as admin_router
from .feedback import router as feedback_router
from .auth import router as auth_router

__all__ = ["chat_router", "faq_router", "admin_router", "feedback_router", "auth_router"]
