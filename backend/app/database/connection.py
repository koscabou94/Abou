"""
Connexion asynchrone à la base de données via SQLAlchemy.
Support SQLite (développement) et PostgreSQL/Supabase (production).

Si la BD distante configurée est injoignable au boot (host inaccessible,
projet Supabase en pause...), on bascule automatiquement sur SQLite local.
Cela permet a l'app de tourner meme quand la BD prod a un probleme — au
prix d'une persistance ephemere sur Render free.
"""

import re
import socket
from typing import AsyncGenerator
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────
# RESOLUTION DE L'URL EFFECTIVE
# Si la BD configuree est distante mais injoignable, on bascule
# automatiquement sur SQLite local pour ne pas planter le service.
# ─────────────────────────────────────────────────────────────────

_SQLITE_FALLBACK = "sqlite+aiosqlite:///./edu_chatbot.db"


def _extract_host_port(url: str) -> tuple[str | None, int | None]:
    """Extrait (host, port) d'une URL postgres/mysql/etc."""
    # postgres://user:pass@host:port/dbname (ou postgresql+asyncpg://...)
    m = re.search(r"@([^:/?]+)(?::(\d+))?", url)
    if not m:
        return (None, None)
    return (m.group(1), int(m.group(2)) if m.group(2) else 5432)


def _is_remote_db_reachable(url: str, timeout: float = 3.0) -> bool:
    """Test rapide TCP : le host de la BD repond-il sur son port ?
    Retourne True pour SQLite (toujours dispo), False si injoignable."""
    if "sqlite" in url:
        return True
    host, port = _extract_host_port(url)
    if not host:
        return True  # URL malformee : on laisse SQLAlchemy planter avec un message clair
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.error, OSError) as exc:
        logger.warning(
            "BD distante injoignable au boot",
            host=host, port=port,
            error=str(exc),
        )
        return False


def _resolve_effective_url() -> str:
    """Renvoie l'URL effective : configuree si joignable, sinon SQLite local."""
    configured = settings.DATABASE_URL
    if _is_remote_db_reachable(configured):
        return configured
    logger.warning(
        "Fallback automatique sur SQLite local",
        reason="BD distante injoignable",
        sqlite_path=_SQLITE_FALLBACK,
        note="Persistance ephemere sur Render free. Reactiver Supabase pour une BD durable.",
    )
    return _SQLITE_FALLBACK


EFFECTIVE_DATABASE_URL = _resolve_effective_url()
_USING_FALLBACK = EFFECTIVE_DATABASE_URL != settings.DATABASE_URL


engine_args = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

if "sqlite" in EFFECTIVE_DATABASE_URL:
    engine_args["poolclass"] = NullPool
else:
    # PostgreSQL / Supabase pooler (transaction mode, port 6543)
    # statement_cache_size=0 obligatoire avec le pooler Supabase
    engine_args["pool_size"] = 3
    engine_args["max_overflow"] = 2
    engine_args["pool_recycle"] = 300
    engine_args["connect_args"] = {
        "ssl": "require",
        "statement_cache_size": 0,
    }

engine = create_async_engine(EFFECTIVE_DATABASE_URL, **engine_args)
logger.info(
    "Engine BD initialise",
    backend="sqlite" if "sqlite" in EFFECTIVE_DATABASE_URL else "postgres",
    fallback_active=_USING_FALLBACK,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error("Erreur transaction DB", error=str(exc))
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    from app.database.models import Base
    logger.info("Création des tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables créées avec succès")
    # Ajouter les colonnes manquantes sur les tables existantes (migration légère)
    await _ensure_users_auth_columns()


async def _ensure_users_auth_columns() -> None:
    """Migration légère : ajoute les colonnes d'authentification sur la table
    `users` si elles manquent. Évite de devoir DROP la BD pour intégrer les
    nouveaux champs (auth_method, ien, email, phone, password_hash, etc.).
    Compatible SQLite et PostgreSQL."""
    from sqlalchemy import text

    expected_columns = {
        # column_name : (sqlite_type, postgres_type)
        "auth_method":   ("VARCHAR(20)",  "VARCHAR(20)"),
        "ien":           ("VARCHAR(20)",  "VARCHAR(20)"),
        "email":         ("VARCHAR(120)", "VARCHAR(120)"),
        "phone":         ("VARCHAR(20)",  "VARCHAR(20)"),
        "password_hash": ("VARCHAR(200)", "VARCHAR(200)"),
        "profile_type":  ("VARCHAR(20)",  "VARCHAR(20)"),
        "full_name":     ("VARCHAR(100)", "VARCHAR(100)"),
        "school":        ("VARCHAR(150)", "VARCHAR(150)"),
        "level":         ("VARCHAR(20)",  "VARCHAR(20)"),
        "is_active":     ("BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT TRUE"),
        "last_login_at": ("DATETIME",     "TIMESTAMP WITH TIME ZONE"),
    }

    is_sqlite = "sqlite" in EFFECTIVE_DATABASE_URL
    logger.info("Migration users : verification du schema", dialect="sqlite" if is_sqlite else "postgres")

    try:
        async with engine.begin() as conn:
            if is_sqlite:
                result = await conn.execute(text("PRAGMA table_info(users)"))
                existing = {row[1] for row in result.fetchall()}
            else:
                result = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'users'"
                ))
                existing = {row[0] for row in result.fetchall()}

            added = []
            for col, (sqlite_type, pg_type) in expected_columns.items():
                if col in existing:
                    continue
                col_type = sqlite_type if is_sqlite else pg_type
                logger.info("Migration users : ajout colonne", column=col, type=col_type)
                try:
                    await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {col_type}"))
                    added.append(col)
                except Exception as col_exc:
                    logger.error("Migration users : echec colonne",
                                 column=col, error=str(col_exc))

            if added:
                logger.info("Migration users : colonnes ajoutees", columns=added)
            else:
                logger.info("Migration users : schema deja a jour",
                            existing_columns=len(existing))
    except Exception as exc:
        # Migration best-effort — si elle échoue, l'app peut continuer (les
        # nouveaux endpoints d'auth retourneront simplement des erreurs)
        logger.error("Migration users echouee (non-bloquant)",
                     error_type=type(exc).__name__, error=str(exc))


async def check_db_connection() -> bool:
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        logger.info("Connexion DB vérifiée")
        return True
    except Exception as exc:
        logger.error("Échec connexion DB", error=str(exc))
        return False
