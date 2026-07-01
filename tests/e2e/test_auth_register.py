"""E2E do sistema de login completo: registro (tenant+admin) e criação de usuários."""

from __future__ import annotations

import httpx


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client: httpx.AsyncClient, tenant: str, email: str, pw: str) -> str:
    resp = await client.post(
        "/v1/auth/register",
        json={"tenant_name": tenant, "email": email, "password": pw},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_register_creates_tenant_and_isolated(client: httpx.AsyncClient) -> None:
    token = await _register(client, "Acme Agro", "boss@acme.com", "senha1234")
    me = (await client.get("/v1/auth/me", headers=_auth(token))).json()
    assert me["email"] == "boss@acme.com"
    assert me["role"] == "admin"
    # tenant novo não enxerga as rotas semeadas (isolamento)
    routes = (await client.get("/v1/routes", headers=_auth(token))).json()
    assert routes == []


async def test_register_duplicate_email_409(client: httpx.AsyncClient) -> None:
    await _register(client, "T1", "dup@x.com", "senha1234")
    resp = await client.post(
        "/v1/auth/register",
        json={"tenant_name": "T2", "email": "dup@x.com", "password": "senha1234"},
    )
    assert resp.status_code == 409


async def test_register_short_password_422(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/v1/auth/register",
        json={"tenant_name": "T", "email": "a@b.com", "password": "curta"},
    )
    assert resp.status_code == 422


async def test_admin_creates_user_and_they_login(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "Beta", "admin@beta.com", "senha1234")
    created = await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "ana@beta.com", "password": "senha1234", "role": "analyst"},
    )
    assert created.status_code == 201
    assert created.json()["role"] == "analyst"

    # o novo usuário consegue logar
    login = await client.post(
        "/v1/auth/login", json={"email": "ana@beta.com", "password": "senha1234"}
    )
    assert login.status_code == 200


async def test_create_user_requires_admin(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "Gamma", "admin@gamma.com", "senha1234")
    await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "view@gamma.com", "password": "senha1234", "role": "viewer"},
    )
    viewer = (
        await client.post(
            "/v1/auth/login", json={"email": "view@gamma.com", "password": "senha1234"}
        )
    ).json()["access_token"]

    denied = await client.post(
        "/v1/auth/users",
        headers=_auth(viewer),
        json={"email": "x@gamma.com", "password": "senha1234", "role": "viewer"},
    )
    assert denied.status_code == 403


async def test_create_user_invalid_role_422(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "Delta", "admin@delta.com", "senha1234")
    resp = await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "y@delta.com", "password": "senha1234", "role": "superuser"},
    )
    assert resp.status_code == 422
