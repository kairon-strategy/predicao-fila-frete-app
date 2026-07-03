"""SQLAlchemy 2.x async engine + session factory.

APENAS sintaxe 2.x async (ver anti-padrões). Bounded contexts declaram seus
modelos herdando de `Base` e obtêm sessões via `get_session` (dependency FastAPI).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from kairon.core.config import settings


class Base(DeclarativeBase):
    """Base declarativa única. Todo modelo do monólito herda daqui.

    Como é um monólito modular, uma metadata só — mas cada context define
    suas tabelas no seu próprio módulo `models.py`.
    """


def _connect_args() -> dict[str, object]:
    """Ajustes por destino. No pooler do Supabase (Supavisor/PgBouncer) o asyncpg
    precisa de `statement_cache_size=0` (prepared statements não sobrevivem ao
    pooler) e SSL. Em Postgres local/direto, nada disso é necessário.
    """
    url = settings.async_database_url
    if "pooler.supabase.com" in url or "supabase.co" in url:
        return {"statement_cache_size": 0, "ssl": "require"}
    return {}


def _make_engine() -> AsyncEngine:
    return create_async_engine(
        settings.async_database_url,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,  # detecta conexões mortas (Postgres reiniciado)
        echo=False,
        connect_args=_connect_args(),
    )


engine: AsyncEngine = _make_engine()

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Dependency FastAPI: uma sessão por request, commit/rollback automático."""
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_database() -> bool:
    """Readiness probe: SELECT 1. Retorna False se o Postgres não responder."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
