"""
Service d'authentification multi-méthodes :
  - IEN (Identifiant Éducation Nationale) + mot de passe
  - Email professionnel + OTP
  - Téléphone + OTP

Pour le MVP :
  - L'OTP est mocké : tout code "123456" est accepté en dev.
  - Les IEN valides sont chargés depuis data/ien_whitelist.json.
  - Les mots de passe sont hashés en bcrypt.
  - Le JWT est signé avec settings.SECRET_KEY (HS256, 7 jours).

Pour la prod réelle :
  - Brancher un envoi SMS (Orange/Twilio) et email (SMTP) à la place du mock.
  - Brancher la base PLANETE/SIMEN pour la vérification IEN officielle.
"""

import json
import os
import re
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

VALID_PROFILES = {"enseignant", "eleve", "parent", "autre"}
VALID_LEVELS = {
    "Préscolaire", "CI", "CP", "CE1", "CE2", "CM1", "CM2",
    "6ème", "5ème", "4ème", "3ème",
    "2nde", "1ère", "Terminale",
}

# OTP mock pour la phase MVP
MOCK_OTP_CODE = "123456"

# Format IEN : 5 à 12 chiffres (ajustable selon spec MEN)
IEN_REGEX = re.compile(r"^\d{5,12}$")
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_REGEX = re.compile(r"^\+?\d{8,15}$")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─────────────────────────────────────────────────────────────────
# WHITELIST IEN
# ─────────────────────────────────────────────────────────────────

_IEN_WHITELIST_CACHE: Optional[dict] = None


def _load_ien_whitelist() -> dict:
    """Charge data/ien_whitelist.json et le met en cache mémoire."""
    global _IEN_WHITELIST_CACHE
    if _IEN_WHITELIST_CACHE is not None:
        return _IEN_WHITELIST_CACHE

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project_root = os.path.dirname(base_dir)
    candidates = [
        os.path.join(project_root, "data", "ien_whitelist.json"),
        "/data/ien_whitelist.json",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    _IEN_WHITELIST_CACHE = json.load(f)
                logger.info("Whitelist IEN chargée", path=p,
                            count=len(_IEN_WHITELIST_CACHE.get("ien", [])))
                return _IEN_WHITELIST_CACHE
            except Exception as exc:
                logger.error("Erreur lecture whitelist IEN", error=str(exc))
                break

    logger.warning("Whitelist IEN introuvable — l'auth IEN sera bloquée")
    _IEN_WHITELIST_CACHE = {"ien": [], "default_password": None}
    return _IEN_WHITELIST_CACHE


def find_ien_in_whitelist(ien: str) -> Optional[dict]:
    """Retourne l'entrée whitelist pour un IEN, ou None si absent."""
    wl = _load_ien_whitelist()
    for entry in wl.get("ien", []):
        if entry.get("ien") == ien:
            return entry
    return None


def get_default_password() -> str:
    """Mot de passe par défaut pour les IEN whitelisted (MVP)."""
    wl = _load_ien_whitelist()
    return wl.get("default_password") or "edubot2026"


# ─────────────────────────────────────────────────────────────────
# VALIDATION DES IDENTIFIANTS
# ─────────────────────────────────────────────────────────────────

def validate_identifier(method: str, identifier: str) -> tuple[bool, str]:
    """Vérifie que l'identifiant est bien formé pour la méthode donnée.
    Retourne (is_valid, message_erreur)."""
    if not identifier or not isinstance(identifier, str):
        return False, "Identifiant manquant"
    identifier = identifier.strip()

    if method == "ien":
        if not IEN_REGEX.match(identifier):
            return False, "L'IEN doit contenir entre 5 et 12 chiffres."
        return True, ""

    if method == "email":
        if not EMAIL_REGEX.match(identifier):
            return False, "Adresse e-mail invalide."
        return True, ""

    if method == "phone":
        # Normaliser : retirer espaces, tirets, parenthèses
        cleaned = re.sub(r"[\s\-\(\)]", "", identifier)
        if not PHONE_REGEX.match(cleaned):
            return False, "Numéro de téléphone invalide. Format attendu : +221 XX XXX XX XX"
        return True, ""

    return False, f"Méthode d'authentification inconnue : {method}"


def normalize_identifier(method: str, identifier: str) -> str:
    """Normalise l'identifiant pour le stockage (lowercase email, trim, etc.)."""
    s = identifier.strip()
    if method == "email":
        return s.lower()
    if method == "phone":
        cleaned = re.sub(r"[\s\-\(\)]", "", s)
        # Forcer le préfixe + s'il n'est pas là
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        return cleaned
    return s


# ─────────────────────────────────────────────────────────────────
# MOTS DE PASSE
# ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash bcrypt d'un mot de passe."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Vérifie un mot de passe contre son hash."""
    if not plain or not hashed:
        return False
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────
# OTP (mock pour le MVP)
# ─────────────────────────────────────────────────────────────────

# Stockage en mémoire des OTP générés : { identifier: (code, expire_at) }
# Volatile : reset au redémarrage. OK pour le MVP.
_OTP_STORE: dict[str, tuple[str, datetime]] = {}
_OTP_TTL_SECONDS = 300  # 5 minutes


def generate_otp(identifier: str) -> str:
    """Génère un OTP à 6 chiffres pour un identifiant (email ou tél).
    En mode mock (DEBUG), renvoie toujours MOCK_OTP_CODE pour faciliter les
    tests. En prod, sera remplacé par un envoi SMS/email réel."""
    code = MOCK_OTP_CODE if settings.DEBUG else f"{secrets.randbelow(10**6):06d}"
    expire_at = datetime.now(timezone.utc) + timedelta(seconds=_OTP_TTL_SECONDS)
    _OTP_STORE[identifier] = (code, expire_at)
    logger.info("OTP généré", identifier_hash=hashlib.sha256(identifier.encode()).hexdigest()[:8],
                mock_mode=settings.DEBUG)
    return code


def verify_otp(identifier: str, code: str) -> bool:
    """Vérifie un code OTP.
    En mode mock (MVP), accepte toujours MOCK_OTP_CODE.
    En prod, vérifie contre _OTP_STORE et applique le TTL."""
    if not identifier or not code:
        return False

    # Mode MVP : toujours accepter le code mock
    if code == MOCK_OTP_CODE:
        logger.info("OTP mock accepté (mode MVP)")
        # On consomme tout de même l'entrée du store si elle existe
        _OTP_STORE.pop(identifier, None)
        return True

    entry = _OTP_STORE.get(identifier)
    if not entry:
        return False
    stored_code, expire_at = entry
    if datetime.now(timezone.utc) > expire_at:
        _OTP_STORE.pop(identifier, None)
        return False
    if stored_code == code:
        _OTP_STORE.pop(identifier, None)  # OTP à usage unique
        return True
    return False


# ─────────────────────────────────────────────────────────────────
# JWT
# ─────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, profile_type: Optional[str] = None) -> str:
    """Crée un JWT signé pour un user_id."""
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "profile": profile_type,
        "iat": datetime.now(timezone.utc),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[int]:
    """Décode un JWT et retourne le user_id, ou None si invalide/expiré."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub else None
    except (JWTError, ValueError) as exc:
        logger.debug("JWT invalide", error=str(exc))
        return None


# ─────────────────────────────────────────────────────────────────
# UTILS PROFIL
# ─────────────────────────────────────────────────────────────────

def validate_profile_type(profile_type: str) -> bool:
    return profile_type in VALID_PROFILES


def validate_level(level: Optional[str]) -> bool:
    """Niveau optionnel — uniquement requis pour élève/parent."""
    if level is None or level == "":
        return True
    return level in VALID_LEVELS
