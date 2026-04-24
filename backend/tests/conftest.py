"""
Fixtures pytest pour les tests du chatbot éducatif.
Utilise SQLite en mémoire pour les tests de base de données.
"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Forcer le mode allégé et SQLite pour les tests
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["USE_LIGHTWEIGHT_MODE"] = "True"
os.environ["DEBUG"] = "True"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from app.database.models import Base
from app.database.connection import get_db


@pytest.fixture(scope="session")
def event_loop():
    """Crée un event loop partagé pour toute la session de tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Crée un engine SQLite en mémoire pour chaque test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Fournit une session de base de données pour chaque test."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """Client HTTP de test pour les endpoints FastAPI."""
    from app.main import app

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
