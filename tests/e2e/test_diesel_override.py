"""O override de diesel (slider da UI) deve afetar a predição monotonicamente.

Usa uma rota LONGA com piso baixo, onde o custo de combustível domina (numa rota
curta o piso ANTT satura e o diesel não muda o resultado — comportamento correto).
"""

from __future__ import annotations

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@pytest_asyncio.fixture
async def long_route(engine: AsyncEngine) -> None:
    from kairon.prediction.db_models import Route
    from kairon.tenant.auth import DEFAULT_TENANT_ID
    from kairon.tenant.models import Tenant

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        if await s.get(Tenant, DEFAULT_TENANT_ID) is None:
            s.add(Tenant(id=DEFAULT_TENANT_ID, name="Default", slug="default"))
            await s.flush()
        s.add(
            Route(
                tenant_id=DEFAULT_TENANT_ID,
                origem="Sorriso-MT",
                destino="Porto de Santos-SP",
                produto="soja",
                distancia_km=2050,
                piso_antt_r_per_ton=10,
            )
        )
        await s.commit()


async def _predict(client: httpx.AsyncClient, key: str, diesel: float) -> float:
    resp = await client.post(
        "/v1/predict",
        headers={"idempotency-key": key},
        json={
            "origem": "Sorriso-MT",
            "destino": "Porto de Santos-SP",
            "produto": "soja",
            "data": "2026-08-15",
            "carga_ton": 32,
            "diesel_price": diesel,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["frete_r_per_ton"]


async def test_higher_diesel_raises_freight(client: httpx.AsyncClient, long_route: None) -> None:
    low = await _predict(client, "diesel-low", 4.5)
    high = await _predict(client, "diesel-high", 9.0)
    assert high > low
