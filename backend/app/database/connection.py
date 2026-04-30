"""
Connexion asynchrone à la base de données via SQLAlchemy.
Support SQLite (développement) et PostgreSQL/Supabase (production).
"""

from typing import AsyncGenerator
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings

logger = structlog.get_logger(__name__)

engine_args = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

if "sqlite" in settings.DATABASE_URL:
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

engine = create_async_engine(settings.DATABASE_URL, **engine_args)

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

    is_sqlite = "sqlite" in settings.DATABASE_URL

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

            for col, (sqlite_type, pg_type) in expected_columns.items():
                if col in existing:
                    continue
                col_type = sqlite_type if is_sqlite else pg_type
                logger.info("Ajout colonne manquante users", column=col)
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {col_type}"))
    except Exception as exc:
        # Migration best-effort — si elle échoue, l'app peut continuer (les
        # nouveaux endpoints d'auth retourneront simplement des erreurs)
        logger.warning("Migration users échouée (non-bloquant)", error=str(exc))


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
