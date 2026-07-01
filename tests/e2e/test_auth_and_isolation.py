"""E2E de auth (US-001), RBAC (US-006) e isolamento cross-tenant (US-004).

O teste de vazamento cross-tenant é requisito de aceite do US-004.
"""

from __future__ import annotations

import uuid

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@pytest_asyncio.fixture
async def iso_setup(engine: AsyncEngine) -> dict:
    """Cria 2 tenants, usuários (admin/viewer) e uma rota em cada. Retorna ids/creds."""
    from kairon.prediction.db_models import Route
    from kairon.tenant.models import Tenant, User
    from kairon.tenant.security import hash_password

    a_id, b_id = uuid.uuid4(), uuid.uuid4()
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        s.add_all(
            [
                Tenant(id=a_id, name="Tenant A", slug=f"a-{a_id.hex[:8]}"),
                Tenant(id=b_id, name="Tenant B", slug=f"b-{b_id.hex[:8]}"),
            ]
        )
        await s.flush()
        s.add_all(
            [
                User(
                    tenant_id=a_id,
                    email="admin@a.com",
                    hashed_password=hash_password("pwA123"),
                    role="admin",
                ),
                User(
                    tenant_id=a_id,
                    email="viewer@a.com",
                    hashed_password=hash_password("pwA123"),
                    role="viewer",
                ),
                User(
                    tenant_id=b_id,
                    email="admin@b.com",
                    hashed_password=hash_password("pwB123"),
                    role="admin",
                ),
            ]
        )
        route_a = Route(
            tenant_id=a_id,
            origem="AX-MT",
            destino="AY-MT",
            produto="ureia",
            distancia_km=200,
            piso_antt_r_per_ton=90,
        )
        route_b = Route(
            tenant_id=b_id,
            origem="BX-BA",
            destino="BY-BA",
            produto="ureia",
            distancia_km=300,
            piso_antt_r_per_ton=95,
        )
        s.add_all([route_a, route_b])
        await s.commit()
        return {"a": a_id, "b": b_id, "route_a": str(route_a.id), "route_b": str(route_b.id)}


async def _login(client: httpx.AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_login_and_me(client: httpx.AsyncClient, iso_setup: dict) -> None:
    token = await _login(client, "admin@a.com", "pwA123")
    me = await client.get("/v1/auth/me", headers=_auth(token))
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "admin@a.com"
    assert body["role"] == "admin"
    assert body["tenant_id"] == str(iso_setup["a"])


async def test_login_bad_password_401(client: httpx.AsyncClient, iso_setup: dict) -> None:
    resp = await client.post("/v1/auth/login", json={"email": "admin@a.com", "password": "wrong"})
    assert resp.status_code == 401


async def test_invalid_token_401(client: httpx.AsyncClient, iso_setup: dict) -> None:
    assert (await client.get("/v1/auth/me", headers=_auth("garbage.token"))).status_code == 401


async def test_refresh_flow(client: httpx.AsyncClient, iso_setup: dict) -> None:
    login = await client.post("/v1/auth/login", json={"email": "admin@a.com", "password": "pwA123"})
    refresh_token = login.json()["refresh_token"]
    refreshed = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    assert (await client.get("/v1/auth/me", headers=_auth(new_access))).status_code == 200


async def test_ranking_isolated_by_tenant(client: httpx.AsyncClient, iso_setup: dict) -> None:
    tok_a = await _login(client, "admin@a.com", "pwA123")
    tok_b = await _login(client, "admin@b.com", "pwB123")

    routes_a = (await client.get("/v1/routes", headers=_auth(tok_a))).json()
    routes_b = (await client.get("/v1/routes", headers=_auth(tok_b))).json()

    origens_a = {r["origem"] for r in routes_a}
    origens_b = {r["origem"] for r in routes_b}
    assert origens_a == {"AX-MT"}  # A só vê a rota dela
    assert origens_b == {"BX-BA"}  # B só vê a rota dele
    assert "BX-BA" not in origens_a and "AX-MT" not in origens_b


async def test_cross_tenant_route_history_404(client: httpx.AsyncClient, iso_setup: dict) -> None:
    tok_a = await _login(client, "admin@a.com", "pwA123")
    # A tenta ler o histórico da rota de B -> 404 (não vaza)
    resp = await client.get(f"/v1/routes/{iso_setup['route_b']}/history", headers=_auth(tok_a))
    assert resp.status_code == 404
    # a própria rota funciona
    own = await client.get(f"/v1/routes/{iso_setup['route_a']}/history", headers=_auth(tok_a))
    assert own.status_code == 200


async def test_cross_tenant_explain_404(client: httpx.AsyncClient, iso_setup: dict) -> None:
    tok_a = await _login(client, "admin@a.com", "pwA123")
    tok_b = await _login(client, "admin@b.com", "pwB123")

    # B cria uma predição
    pred_b = await client.post(
        "/v1/predict",
        headers={**_auth(tok_b), "idempotency-key": "iso-b-1"},
        json={"origem": "BX-BA", "destino": "BY-BA", "produto": "ureia", "data": "2026-08-15"},
    )
    assert pred_b.status_code == 200
    pid_b = pred_b.json()["prediction_id"]

    # A tenta explicar a predição de B -> 404
    leak = await client.post("/v1/explain", headers=_auth(tok_a), json={"prediction_id": pid_b})
    assert leak.status_code == 404
    # B explica a própria -> 200
    ok = await client.post("/v1/explain", headers=_auth(tok_b), json={"prediction_id": pid_b})
    assert ok.status_code == 200


async def test_rbac_viewer_cannot_predict(client: httpx.AsyncClient, iso_setup: dict) -> None:
    tok_viewer = await _login(client, "viewer@a.com", "pwA123")
    tok_admin = await _login(client, "admin@a.com", "pwA123")
    body = {"origem": "AX-MT", "destino": "AY-MT", "produto": "ureia", "data": "2026-08-15"}

    denied = await client.post(
        "/v1/predict", headers={**_auth(tok_viewer), "idempotency-key": "rbac-1"}, json=body
    )
    assert denied.status_code == 403

    allowed = await client.post(
        "/v1/predict", headers={**_auth(tok_admin), "idempotency-key": "rbac-2"}, json=body
    )
    assert allowed.status_code == 200

    # viewer ainda consegue LER o ranking (US-006)
    assert (await client.get("/v1/routes", headers=_auth(tok_viewer))).status_code == 200
