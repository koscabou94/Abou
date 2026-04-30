"""
Endpoints d'authentification multi-méthodes.

Flux supportés :
  - POST /api/auth/login         : connexion (IEN + password OU email/tél + OTP)
  - POST /api/auth/request-otp   : demande d'OTP pour email ou téléphone
  - POST /api/auth/register      : finalisation du profil (premier login)
  - GET  /api/auth/me            : profil utilisateur courant (avec JWT)
  - POST /api/auth/logout        : invalidation côté client (le JWT n'a pas de blacklist)
"""

from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.models import User
from app.middleware.rate_limit import limiter
from app.services.auth_service import (
    VALID_PROFILES,
    create_access_token,
    decode_access_token,
    find_ien_in_whitelist,
    generate_otp,
    get_default_password,
    hash_password,
    normalize_identifier,
    validate_identifier,
    validate_level,
    validate_profile_type,
    verify_otp,
    verify_password,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentification"])


# ─────────────────────────────────────────────────────────────────
# MODÈLES Pydantic
# ─────────────────────────────────────────────────────────────────

class OTPRequest(BaseModel):
    method: str = Field(..., description="email ou phone")
    identifier: str = Field(..., min_length=3, max_length=120)

    @field_validator("method")
    @classmethod
    def _check_method(cls, v: str) -> str:
        if v not in ("email", "phone"):
            raise ValueError("method doit être 'email' ou 'phone'")
        return v


class LoginRequest(BaseModel):
    method: str = Field(..., description="ien | email | phone")
    identifier: str = Field(..., min_length=3, max_length=120)
    password: Optional[str] = Field(None, min_length=4, max_length=200,
                                    description="Mot de passe (méthode IEN uniquement)")
    otp: Optional[str] = Field(None, min_length=4, max_length=8,
                               description="Code OTP (méthode email/phone)")
    session_id: Optional[str] = Field(None, description="UUID session courante (optionnel, pour fusion)")

    @field_validator("method")
    @classmethod
    def _check_method(cls, v: str) -> str:
        if v not in ("ien", "email", "phone"):
            raise ValueError("method doit être 'ien', 'email' ou 'phone'")
        return v


class RegisterProfileRequest(BaseModel):
    """Finalisation du profil (premier login d'un utilisateur)."""
    profile_type: str = Field(..., description="enseignant | eleve | parent | autre")
    full_name: str = Field(..., min_length=2, max_length=100)
    school: Optional[str] = Field(None, max_length=150)
    level: Optional[str] = Field(None, max_length=20,
                                 description="Niveau scolaire (CI..Terminale) — utile pour élève/parent")

    @field_validator("profile_type")
    @classmethod
    def _check_profile(cls, v: str) -> str:
        if v not in VALID_PROFILES:
            raise ValueError(f"profile_type doit être l'un de : {sorted(VALID_PROFILES)}")
        return v

    @field_validator("level")
    @classmethod
    def _check_level(cls, v: Optional[str]) -> Optional[str]:
        if not validate_level(v):
            raise ValueError("Niveau scolaire invalide")
        return v


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    user: dict
    profile_complete: bool


# ─────────────────────────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────────────────────────

async def _find_user_by_identifier(db: AsyncSession, method: str, identifier: str) -> Optional[User]:
    if method == "ien":
        stmt = select(User).where(User.ien == identifier)
    elif method == "email":
        stmt = select(User).where(User.email == identifier)
    elif method == "phone":
        stmt = select(User).where(User.phone == identifier)
    else:
        return None
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _create_or_update_user_from_login(
    db: AsyncSession,
    method: str,
    identifier: str,
    session_id: Optional[str],
    whitelist_entry: Optional[dict] = None,
) -> User:
    """Crée ou met à jour un User à partir d'une connexion réussie."""
    import uuid

    user = await _find_user_by_identifier(db, method, identifier)

    if user is None:
        # Tenter de récupérer l'utilisateur invité existant (par session_id)
        # pour fusionner son historique avec le compte authentifié
        if session_id:
            from app.middleware.auth import validate_session_id
            if validate_session_id(session_id):
                stmt = select(User).where(User.session_id == session_id)
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()
                # On ne fusionne que si cet utilisateur invité n'a pas déjà
                # un autre compte authentifié (sécurité)
                if existing and not existing.profile_type:
                    user = existing

        if user is None:
            user = User(session_id=str(uuid.uuid4()))
            db.add(user)

    # Renseigner les champs d'auth
    user.auth_method = method
    if method == "ien":
        user.ien = identifier
    elif method == "email":
        user.email = identifier
    elif method == "phone":
        user.phone = identifier

    # Si la whitelist nous donne un profil pré-établi (IEN test), on le pré-remplit
    if whitelist_entry:
        user.profile_type = whitelist_entry.get("profile_type")
        user.full_name = whitelist_entry.get("full_name")
        user.school = whitelist_entry.get("school")
        user.level = whitelist_entry.get("level")

    user.last_login_at = datetime.utcnow()
    await db.flush()
    return user


def _bearer_token_from_request(request: Request) -> Optional[str]:
    """Extrait le JWT depuis le header Authorization: Bearer ..."""
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/request-otp",
    summary="Demander un code OTP",
    description="Envoie un code à 6 chiffres par email ou SMS (mocké en dev : 123456 fonctionne).",
)
@limiter.limit("5/minute")
async def request_otp(request: Request, payload: OTPRequest) -> dict:
    is_valid, msg = validate_identifier(payload.method, payload.identifier)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    identifier = normalize_identifier(payload.method, payload.identifier)
    code = generate_otp(identifier)
    return {
        "status": "sent",
        "method": payload.method,
        "destination_masked": _mask(identifier),
        "ttl_seconds": 300,
        # En prod : ne JAMAIS retourner le code. Ici on le retourne uniquement
        # pour faciliter les tests en mode MVP / mock.
        "dev_note": "En mode MVP, le code 123456 est toujours accepté.",
    }


def _mask(s: str) -> str:
    """Masque partiellement un email ou téléphone pour le retour API."""
    if "@" in s:
        user, _, dom = s.partition("@")
        if len(user) <= 2:
            return f"{user[0]}***@{dom}"
        return f"{user[:2]}***@{dom}"
    if len(s) <= 4:
        return "***"
    return s[:3] + "*" * (len(s) - 6) + s[-3:]


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Connexion par IEN+password ou email/tel+OTP",
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    # 1. Validation format
    is_valid, msg = validate_identifier(payload.method, payload.identifier)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    identifier = normalize_identifier(payload.method, payload.identifier)

    whitelist_entry = None

    # 2. Authentification selon la méthode
    if payload.method == "ien":
        if not payload.password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Le mot de passe est requis pour la connexion par IEN.")
        # Vérifier la whitelist (phase pilote)
        whitelist_entry = find_ien_in_whitelist(identifier)
        if not whitelist_entry:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="IEN inconnu. Contactez votre administrateur.")
        # Vérifier le mot de passe : soit user existant (hash en BD), soit défaut whitelist
        user = await _find_user_by_identifier(db, "ien", identifier)
        if user and user.password_hash:
            if not verify_password(payload.password, user.password_hash):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                    detail="Mot de passe incorrect.")
        else:
            if payload.password != get_default_password():
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                    detail="Mot de passe incorrect.")

    elif payload.method in ("email", "phone"):
        if not payload.otp:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Le code OTP est requis.")
        if not verify_otp(identifier, payload.otp):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Code OTP invalide ou expiré.")

    # 3. Créer ou mettre à jour l'utilisateur
    user = await _create_or_update_user_from_login(
        db, payload.method, identifier, payload.session_id, whitelist_entry
    )

    # 4. Si IEN, hash + persister le mot de passe pour les futures connexions
    if payload.method == "ien" and not user.password_hash:
        user.password_hash = hash_password(payload.password)

    await db.flush()

    # 5. Émettre le JWT
    token = create_access_token(user.id, user.profile_type)
    profile_complete = bool(user.profile_type and user.full_name)

    logger.info("Connexion réussie",
                method=payload.method, user_id=user.id,
                profile_complete=profile_complete)

    return AuthResponse(
        access_token=token,
        user=user.public_dict(),
        profile_complete=profile_complete,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    summary="Finaliser le profil (premier login)",
    description="Si profile_complete=False après le login, l'utilisateur doit compléter son profil.",
)
@limiter.limit("10/minute")
async def register_profile(
    request: Request,
    payload: RegisterProfileRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    # 1. Récupérer l'utilisateur depuis le JWT
    token = _bearer_token_from_request(request)
    user_id = decode_access_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Connexion requise.")
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Utilisateur introuvable.")

    # 2. Mettre à jour le profil
    user.profile_type = payload.profile_type
    user.full_name = payload.full_name.strip()
    user.school = (payload.school or "").strip() or None
    user.level = payload.level or None
    await db.flush()

    new_token = create_access_token(user.id, user.profile_type)
    return AuthResponse(
        access_token=new_token,
        user=user.public_dict(),
        profile_complete=True,
    )


@router.get(
    "/me",
    summary="Profil utilisateur courant",
)
async def get_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    token = _bearer_token_from_request(request)
    user_id = decode_access_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token invalide ou expiré.")
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Utilisateur introuvable.")
    return {
        "user": user.public_dict(),
        "profile_complete": bool(user.profile_type and user.full_name),
    }


@router.post(
    "/logout",
    summary="Déconnexion (côté client uniquement)",
    description=("Le JWT n'est pas blacklisté côté serveur (stateless) ; "
                 "le client doit simplement supprimer son token local."),
)
async def logout() -> dict:
    return {"status": "ok", "message": "Déconnexion effectuée"}


@router.get(
    "/profiles",
    summary="Liste des types de profil et niveaux disponibles",
)
async def list_profiles() -> dict:
    return {
        "profile_types": [
            {"value": "enseignant", "label": "Enseignant", "icon": "graduation-cap"},
            {"value": "eleve",      "label": "Élève",      "icon": "user"},
            {"value": "parent",     "label": "Parent",     "icon": "users"},
            {"value": "autre",      "label": "Autre",      "icon": "user-cog"},
        ],
        "levels": [
            "Préscolaire",
            "CI", "CP", "CE1", "CE2", "CM1", "CM2",
            "6ème", "5ème", "4ème", "3ème",
            "2nde", "1ère", "Terminale",
        ],
    }
