"""
Package des routes API de l'application.
"""

from .chat import router as chat_router
from .faq import router as faq_router
from .admin import router as admin_router

__all__ = ["chat_router", "faq_router", "admin_router"]
