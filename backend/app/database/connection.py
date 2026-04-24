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
