"""Shared test infrastructure for Kairon Frete.

DB-backed strategy
------------------
These fixtures spin up a real Postgres so tests exercise the actual endpoints
(service + router + main) and coverage is captured.

Postgres source (in priority order):
  1. env ``TEST_DATABASE_URL`` — CI provides a postgres service; set this and the
     same conftest works in CI and locally with zero Docker.
  2. otherwise, a ``testcontainers`` Postgres 16 container is started (needs Docker).

If neither is available (no ``TEST_DATABASE_URL`` and Docker/testcontainers is
missing), the ``postgres_url`` fixture raises ``pytest.skip`` so DB-backed tests
skip cleanly instead of erroring. (``allow_module_level=True`` is wrong here — that
is for module import time, not for a fixture.)

Schema is built with ``Base.metadata.create_all`` (not alembic) for speed. All ORM
model modules are imported first so the metadata is complete.

Deterministic explanations
--------------------------
``/v1/explain`` returns ``source="template"`` only when the Claude client is
disabled. ``settings`` is cached via ``lru_cache`` and the app may be imported
before env is set, so patching env alone is fragile. The cleanest, import-order
independent approach is an autouse fixture that replaces the module-level singleton
``kairon.explanation.claude_client._client`` with a stub whose ``is_enabled`` is
False. We also unset ANTHROPIC_API_KEY as defence in depth.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# All ORM model modules — importing them registers their tables on Base.metadata.
from kairon.core.database import Base  # noqa: E402


def _to_asyncpg_url(url: str) -> str:
    """Normalise any Postgres URL to the ``postgresql+asyncpg://`` async driver."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Async Postgres URL. Prefers env TEST_DATABASE_URL; else a testcontainer.

    Skips (not errors) if no DB is reachable, so DB-backed tests are skipped
    cleanly on machines without Docker and without a provided DATABASE_URL.
    """
    env_url = os.getenv("TEST_DATABASE_URL")
    if env_url:
        yield _to_asyncpg_url(env_url)
        return

    try:
        from testcontainers.postgres import PostgresContainer
    except Exception as exc:  # pragma: no cover - import/env dependent
        pytest.skip(f"testcontainers unavailable and TEST_DATABASE_URL unset: {exc}")
        return

    try:
        container = PostgresContainer("postgres:16-alpine")
        container.start()
    except Exception as exc:  # pragma: no cover - Docker not running
        pytest.skip(f"Docker/testcontainers Postgres unavailable: {exc}")
        return

    try:
        yield _to_asyncpg_url(container.get_connection_url())
    finally:
        container.stop()


@pytest_asyncio.fixture(scope="function")
async def engine(postgres_url: str) -> AsyncIterator[AsyncEngine]:
    """Fresh async engine with the full schema created via create_all."""
    # Import every ORM module so Base.metadata is complete before create_all.
    import kairon.alerts.models  # noqa: F401
    import kairon.audit.models  # noqa: F401
    import kairon.explanation.models  # noqa: F401
    import kairon.ingestion.anp.models  # noqa: F401
    import kairon.prediction.db_models  # noqa: F401
    import kairon.tenant.models  # noqa: F401

    eng = create_async_engine(postgres_url, echo=False, pool_pre_ping=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A standalone AsyncSession bound to the test engine (for direct DB setup)."""
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


@pytest.fixture(autouse=True)
def _disable_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the template path in /v1/explain (deterministic, offline).

    Replaces the claude_client singleton with a stub whose is_enabled is False,
    and unsets ANTHROPIC_API_KEY as defence in depth.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    import kairon.explanation.claude_client as cc

    class _DisabledClient:
        is_enabled = False

        async def complete(self, prompt: str) -> str:  # pragma: no cover - never called
            raise AssertionError("Claude must stay disabled in tests")

    monkeypatch.setattr(cc, "_client", _DisabledClient(), raising=False)


@pytest.fixture(autouse=True)
def _enable_open_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Testes criam tenants isolados via /register; habilita o cadastro aberto.

    Produção é invite-only (settings.allow_open_registration=False). O teste do
    gate 403 sobrescreve isto localmente com monkeypatch.
    """
    from kairon.core.config import settings

    monkeypatch.setattr(settings, "allow_open_registration", True, raising=False)


@pytest.fixture(autouse=True)
def _clear_login_ratelimit() -> None:
    """Zera o rate limiter de login (estado global do processo) entre testes."""
    from kairon.tenant import ratelimit

    ratelimit._attempts.clear()


@pytest_asyncio.fixture
async def app(engine: AsyncEngine) -> AsyncIterator[FastAPI]:
    """FastAPI app with get_session overridden to use the test engine."""
    from kairon.core.database import get_session
    from kairon.main import create_app

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_session] = _override_get_session
    try:
        yield application
    finally:
        application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Async HTTP client wired to the app via ASGI transport (no network)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Client autenticado como admin no tenant default.

    Endpoints protegidos exigem token (get_principal -> 401 sem auth). Módulos que
    exercitam esses endpoints sobrescrevem `client` para apontar aqui.
    """
    import uuid

    from kairon.tenant.auth import DEFAULT_TENANT_ID
    from kairon.tenant.permissions import ALL_PERMISSIONS
    from kairon.tenant.security import create_access_token

    token = create_access_token(
        user_id=uuid.UUID(int=1),
        tenant_id=DEFAULT_TENANT_ID,
        role="admin",
        permissions=sorted(ALL_PERMISSIONS),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c


@pytest_asyncio.fixture
async def seed_route(engine: AsyncEngine) -> None:
    """Insert the default tenant + canonical Sinop-MT -> Sorriso-MT / ureia route.

    Route carries the default tenant so anonymous requests (which resolve to the
    default tenant) see it via the tenant-scoped ranking.
    """
    from kairon.prediction.db_models import Route
    from kairon.tenant.auth import DEFAULT_TENANT_ID
    from kairon.tenant.models import Tenant

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        if await sess.get(Tenant, DEFAULT_TENANT_ID) is None:
            sess.add(Tenant(id=DEFAULT_TENANT_ID, name="Default", slug="default"))
            await sess.flush()
        sess.add(
            Route(
                tenant_id=DEFAULT_TENANT_ID,
                origem="Sinop-MT",
                destino="Sorriso-MT",
                produto="ureia",
                distancia_km=130,
                piso_antt_r_per_ton=90,
            )
        )
        await sess.commit()
