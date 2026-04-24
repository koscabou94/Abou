"""
Configuration du rate limiting avec slowapi.
Limite les requêtes par adresse IP pour protéger l'API.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Créer le limiteur global basé sur l'adresse IP
limiter = Limiter(key_func=get_remote_address)


def chat_rate_limit():
    """
    Retourne le décorateur de rate limiting pour l'endpoint de chat.
    Limite par défaut : 20 requêtes par minute par IP.
    """
    return limiter.limit(settings.RATE_LIMIT_CHAT)


def faq_rate_limit():
    """
    Retourne le décorateur de rate limiting pour les endpoints FAQ.
    Limite par défaut : 100 requêtes par minute par IP.
    """
    return limiter.limit(settings.RATE_LIMIT_FAQ)


def admin_rate_limit():
    """
    Retourne le décorateur de rate limiting pour les endpoints admin.
    Limite par défaut : 10 requêtes par minute par IP.
    """
    return limiter.limit("10/minute")
