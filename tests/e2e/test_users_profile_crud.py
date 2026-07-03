"""E2E do CRUD de usuários + perfil (/me) + empresa (/tenant)."""

from __future__ import annotations

import httpx


def _auth(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


async def _register(
    client: httpx.AsyncClient, tenant: str, email: str, name: str | None = None
) -> str:
    body = {"tenant_name": tenant, "email": email, "password": "senha1234"}
    if name:
        body["name"] = name
    r = await client.post("/v1/auth/register", json=body)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ---- Usuários ----
async def test_users_list_and_update(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "Acme", "admin@acme.com", name="Chefe")
    # admin aparece na lista
    users = (await client.get("/v1/auth/users", headers=_auth(admin))).json()
    assert len(users) == 1 and users[0]["email"] == "admin@acme.com" and users[0]["name"] == "Chefe"
    # cria analyst
    created = await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "ana@acme.com", "password": "senha1234", "role": "analyst", "name": "Ana"},
    )
    assert created.status_code == 201
    uid = created.json()["id"]
    assert len((await client.get("/v1/auth/users", headers=_auth(admin))).json()) == 2
    # edita papel + desativa
    upd = await client.patch(
        f"/v1/auth/users/{uid}", headers=_auth(admin), json={"role": "viewer", "is_active": False}
    )
    assert upd.status_code == 200
    assert upd.json()["role"] == "viewer" and upd.json()["is_active"] is False


async def test_users_list_requires_admin(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "Beta", "admin@beta.com")
    await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "ana@beta.com", "password": "senha1234", "role": "analyst"},
    )
    analyst = (
        await client.post("/v1/auth/login", json={"email": "ana@beta.com", "password": "senha1234"})
    ).json()["access_token"]
    assert (await client.get("/v1/auth/users", headers=_auth(analyst))).status_code == 403


# ---- Perfil ----
async def test_update_me_name_and_password(client: httpx.AsyncClient) -> None:
    tok = await _register(client, "Gamma", "user@gamma.com")
    upd = await client.patch(
        "/v1/auth/me", headers=_auth(tok), json={"name": "João Silva", "password": "novaSenha123"}
    )
    assert upd.status_code == 200 and upd.json()["name"] == "João Silva"
    # /me reflete o nome
    assert (await client.get("/v1/auth/me", headers=_auth(tok))).json()["name"] == "João Silva"
    # login com a nova senha
    assert (
        await client.post(
            "/v1/auth/login", json={"email": "user@gamma.com", "password": "novaSenha123"}
        )
    ).status_code == 200


# ---- Empresa ----
async def test_tenant_get_and_update(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "Delta Ltda", "admin@delta.com")
    got = await client.get("/v1/auth/tenant", headers=_auth(admin))
    assert got.status_code == 200 and got.json()["name"] == "Delta Ltda"
    upd = await client.patch(
        "/v1/auth/tenant", headers=_auth(admin), json={"name": "Delta Agro S.A."}
    )
    assert upd.status_code == 200 and upd.json()["name"] == "Delta Agro S.A."


async def test_tenant_update_requires_admin(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "Eps", "admin@eps.com")
    await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "v@eps.com", "password": "senha1234", "role": "viewer"},
    )
    viewer = (
        await client.post("/v1/auth/login", json={"email": "v@eps.com", "password": "senha1234"})
    ).json()["access_token"]
    assert (
        await client.patch("/v1/auth/tenant", headers=_auth(viewer), json={"name": "X"})
    ).status_code == 403
