"""
Middleware d'authentification pour les endpoints d'administration.
Gestion des tokens de session UUID pour les utilisateurs basiques.
"""

import uuid
from typing import Optional
from fastapi import Depends, HTTPException, Header, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import settings
from app.database.connection import get_db

logger = structlog.get_logger(__name__)

# Schéma de sécurité pour la clé API admin
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header)
) -> str:
    """
    Vérifie la clé API pour les endpoints d'administration.
    La clé doit être passée dans le header X-API-Key.
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
    """Génère un token de session UUID unique pour un utilisateur."""
    token = str(uuid.uuid4())
    logger.debug("Nouveau token de session créé", token_prefix=token[:8])
    return token


def get_session_id(
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID")
) -> Optional[str]:
    """Extrait l'identifiant de session depuis le header de la requête."""
    if x_session_id:
        logger.debug("Session ID reçu", session_prefix=x_session_id[:8])
    return x_session_id


def validate_session_id(session_id: str) -> bool:
    """Valide qu'un session_id est bien un UUID valide."""
    try:
        uuid.UUID(session_id)
        return True
    except (ValueError, AttributeError):
        return False


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> "User":  # type: ignore[name-defined]
    """Dépendance FastAPI obligatoire : décode le JWT Bearer et retourne
    l'utilisateur authentifié. Lève 401 si le token est absent ou invalide.
    """
    from sqlalchemy import select
    from app.database.models import User
    from app.services.auth_service import decode_access_token

    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification manquant",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Format de token invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = parts[1]
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expiré ou invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utilisateur introuvable",
            )
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Erreur de vérification du token",
        )


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional["User"]:  # type: ignore[name-defined]
    """Dépendance optionnelle : retourne None si l'utilisateur n'est pas authentifié."""
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
