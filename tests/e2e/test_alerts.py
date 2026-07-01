"""E2E do EPIC 8: detecção de spike de diesel, feed, resolução e isolamento."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@pytest_asyncio.fixture
async def spiky_diesel(engine: AsyncEngine) -> None:
    """Insere série de diesel para a UF 'ZZ' com um salto no valor mais recente."""
    from kairon.ingestion.anp.models import RawDieselPrice

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    today = date.today()
    async with factory() as s:
        # 20 dias de baseline ~6.00 e o mais recente em 7.50 (+25% -> critical).
        for i in range(20, 0, -1):
            s.add(
                RawDieselPrice(
                    data=today - timedelta(days=i),
                    uf="ZZ",
                    cidade=None,
                    preco_medio=6.00,
                    fonte="TEST",
                )
            )
        s.add(RawDieselPrice(data=today, uf="ZZ", cidade=None, preco_medio=7.50, fonte="TEST"))
        await s.commit()


async def test_detect_creates_diesel_alert(client: httpx.AsyncClient, spiky_diesel: None) -> None:
    resp = await client.post("/v1/alerts/detect")
    assert resp.status_code == 200
    assert resp.json()["created"] >= 1

    feed = (await client.get("/v1/alerts")).json()
    diesel = [a for a in feed if a["alert_type"] == "diesel_spike" and a["entity_id"] == "ZZ"]
    assert len(diesel) == 1
    assert diesel[0]["severity"] == "critical"
    assert diesel[0]["meta"]["uf"] == "ZZ"


async def test_detect_is_idempotent(client: httpx.AsyncClient, spiky_diesel: None) -> None:
    first = (await client.post("/v1/alerts/detect")).json()["created"]
    second = (await client.post("/v1/alerts/detect")).json()["created"]
    assert first >= 1
    assert second == 0  # não duplica alerta já ativo


async def test_resolve_alert(client: httpx.AsyncClient, spiky_diesel: None) -> None:
    await client.post("/v1/alerts/detect")
    alert_id = (await client.get("/v1/alerts")).json()[0]["id"]

    resolved = await client.post(f"/v1/alerts/{alert_id}/resolve")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    assert (await client.get("/v1/alerts")).json() == []  # não está mais em "active"
    resolved_feed = (await client.get("/v1/alerts", params={"status": "resolved"})).json()
    assert any(a["id"] == alert_id for a in resolved_feed)


async def test_resolve_unknown_404(client: httpx.AsyncClient) -> None:
    assert (await client.post("/v1/alerts/999999/resolve")).status_code == 404


async def test_severity_filter(client: httpx.AsyncClient, spiky_diesel: None) -> None:
    await client.post("/v1/alerts/detect")
    warn_only = (await client.get("/v1/alerts", params={"severity": "warn"})).json()
    assert all(a["severity"] == "warn" for a in warn_only)  # o de ZZ é critical -> não aparece


async def test_alerts_isolated_by_tenant(client: httpx.AsyncClient, spiky_diesel: None) -> None:
    from kairon.tenant.security import create_access_token

    # detecção anônima cria alertas no tenant default
    await client.post("/v1/alerts/detect")
    assert len((await client.get("/v1/alerts")).json()) >= 1

    # token de OUTRO tenant não enxerga os alertas do default
    other = create_access_token(user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role="admin")
    other_feed = await client.get("/v1/alerts", headers={"Authorization": f"Bearer {other}"})
    assert other_feed.status_code == 200
    assert other_feed.json() == []
