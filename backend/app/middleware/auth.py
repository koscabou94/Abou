"""
Middleware d'authentification pour les endpoints d'administration.
Gestion des tokens de session UUID pour les utilisateurs basiques.
"""

import uuid
from typing import Optional
from fastapi import HTTPException, Header, Security, status
from fastapi.security import APIKeyHeader
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Schéma de sécurité pour la clé API admin
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header)
) -> str:
    """
    Vérifie la clé API pour les endpoints d'administration.
    La clé doit être passée dans le header X-API-Key.

    Args:
        api_key: Clé API extraite du header de la requête

    Returns:
        La clé API si elle est valide

    Raises:
        HTTPException 401: Si la clé API est manquante
        HTTPException 403: Si la clé API est invalide
    """
    if not api_key:
        logger.warning("Tentative d'accès admin sans clé API")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API requise pour accéder aux endpoints d'administration",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key != settings.API_KEY:
        logger.warning("Tentative d'accès admin avec une clé API invalide")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clé API invalide",
        )

    logger.debug("Accès admin autorisé")
    return api_key


def create_session_token() -> str:
    """
    Génère un token de session UUID unique pour un utilisateur.
    Aucun mot de passe n'est requis, les sessions sont anonymes.

    Returns:
        UUID v4 sous forme de chaîne
    """
    token = str(uuid.uuid4())
    logger.debug("Nouveau token de session créé", token_prefix=token[:8])
    return token


def get_session_id(
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID")
) -> Optional[str]:
    """
    Extrait l'identifiant de session depuis le header de la requête.
    Cette dépendance est optionnelle et ne lève pas d'erreur si manquante.

    Args:
        x_session_id: Identifiant de session dans le header X-Session-ID

    Returns:
        L'identifiant de session ou None si absent
    """
    if x_session_id:
        logger.debug("Session ID reçu", session_prefix=x_session_id[:8])
    return x_session_id


def validate_session_id(session_id: str) -> bool:
    """
    Valide qu'un session_id est bien un UUID valide.

    Args:
        session_id: L'identifiant de session à valider

    Returns:
        True si c'est un UUID valide, False sinon
    """
    try:
        uuid.UUID(session_id)
        return True
    except (ValueError, AttributeError):
        return False


async def get_current_user_optional(request, db) -> Optional["User"]:  # type: ignore[name-defined]
    """Dépendance optionnelle : décode le JWT s'il est présent et retourne
    l'utilisateur authentifié. Retourne None pour les utilisateurs invités.

    Le mode invité reste fonctionnel : l'absence de token ne lève PAS d'erreur.
    """
    from sqlalchemy import select
    from app.database.models import User
    from app.services.auth_service import decode_access_token

    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    user_id = decode_access_token(token)
    if not user_id:
        return None
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except Exception:
        return None
