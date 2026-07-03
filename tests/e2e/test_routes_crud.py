"""E2E do CRUD de rotas: criar/listar/editar/excluir + RBAC + isolamento."""

from __future__ import annotations

import httpx


def _auth(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


async def _register(client: httpx.AsyncClient, tenant: str, email: str) -> str:
    r = await client.post(
        "/v1/auth/register",
        json={"tenant_name": tenant, "email": email, "password": "senha1234"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


_ROUTE = {
    "origem": "Sorriso-MT",
    "destino": "Porto de Santos-SP",
    "produto": "soja",
    "distancia_km": 2050,
    "corredor": "Corredor Centro-Sul",
    "piso_antt_r_per_ton": 120,
}


async def test_route_crud_lifecycle(client: httpx.AsyncClient) -> None:
    tok = await _register(client, "Acme", "admin@acme.com")
    # create
    c = await client.post("/v1/routes", headers=_auth(tok), json=_ROUTE)
    assert c.status_code == 201, c.text
    rid = c.json()["route_id"]
    # list
    lst = await client.get("/v1/routes/manage", headers=_auth(tok))
    assert lst.status_code == 200
    assert any(r["route_id"] == rid for r in lst.json())
    # update
    upd = await client.put(
        f"/v1/routes/{rid}", headers=_auth(tok), json={**_ROUTE, "distancia_km": 2100}
    )
    assert upd.status_code == 200
    assert upd.json()["distancia_km"] == 2100
    # delete
    d = await client.delete(f"/v1/routes/{rid}", headers=_auth(tok))
    assert d.status_code == 204
    assert (await client.get("/v1/routes/manage", headers=_auth(tok))).json() == []


async def test_route_write_requires_role(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "Beta", "admin@beta.com")
    # admin cria um viewer
    await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "v@beta.com", "password": "senha1234", "role": "viewer"},
    )
    viewer = (
        await client.post("/v1/auth/login", json={"email": "v@beta.com", "password": "senha1234"})
    ).json()["access_token"]
    # viewer não pode criar rota
    resp = await client.post("/v1/routes", headers=_auth(viewer), json=_ROUTE)
    assert resp.status_code == 403
    # mas pode listar (leitura)
    assert (await client.get("/v1/routes/manage", headers=_auth(viewer))).status_code == 200


async def test_route_isolated_by_tenant(client: httpx.AsyncClient) -> None:
    a = await _register(client, "TA", "a@ta.com")
    b = await _register(client, "TB", "b@tb.com")
    rid = (await client.post("/v1/routes", headers=_auth(a), json=_ROUTE)).json()["route_id"]
    # B não vê a rota de A
    assert (await client.get("/v1/routes/manage", headers=_auth(b))).json() == []
    # B não edita/exclui a rota de A -> 404
    assert (await client.put(f"/v1/routes/{rid}", headers=_auth(b), json=_ROUTE)).status_code == 404
    assert (await client.delete(f"/v1/routes/{rid}", headers=_auth(b))).status_code == 404
