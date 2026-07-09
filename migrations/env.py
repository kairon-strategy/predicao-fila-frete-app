"""Alembic env — modo ASYNC (asyncpg), sem driver sync (ver core/config.py).

A URL vem de `settings.async_database_url`, nunca de alembic.ini (sem segredos no repo).
Importamos os models de cada context para que Base.metadata os enxergue
(útil quando/for usar autogenerate — sempre revisando a migration gerada, ADR anti-padrão).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from kairon.core.config import settings
from kairon.core.database import Base

# Importa os models para registrar as tabelas na metadata.
# (imports com efeito colateral; noqa para o linter não reclamar de "unused")
import kairon.alerts.models  # noqa: F401
import kairon.audit.models  # noqa: F401
import kairon.explanation.models  # noqa: F401
import kairon.ingestion.anp.models  # noqa: F401
import kairon.knowledge.models  # noqa: F401
import kairon.prediction.db_models  # noqa: F401
import kairon.tenant.models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


def run_migrations_offline() -> None:
    """Modo offline: gera SQL sem conectar."""
    context.configure(
        url=settings.async_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
