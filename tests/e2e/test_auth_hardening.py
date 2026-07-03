"""E2E do endurecimento de auth: invite-only, role enum, reset de senha,
revogação (logout/troca de senha) e rate limit no login."""

from __future__ import annotations

import httpx
import pytest


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client: httpx.AsyncClient, tenant: str, email: str) -> str:
    r = await client.post(
        "/v1/auth/register",
        json={"tenant_name": tenant, "email": email, "password": "senha1234"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_register_gated_when_disabled(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kairon.core.config import settings

    monkeypatch.setattr(settings, "allow_open_registration", False, raising=False)
    r = await client.post(
        "/v1/auth/register",
        json={"tenant_name": "Gated Co", "email": "x@gated.com", "password": "senha1234"},
    )
    assert r.status_code == 403, r.text


async def test_invalid_role_rejected_422(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "RoleCo", "admin@roleco.com")
    r = await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "u@roleco.com", "password": "senha1234", "role": "superadmin"},
    )
    assert r.status_code == 422, r.text


async def test_admin_password_reset_and_revokes_session(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "ResetCo", "admin@resetco.com")
    # cria usuário e captura o refresh dele
    await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "user@resetco.com", "password": "oldpass123", "role": "analyst"},
    )
    login = await client.post(
        "/v1/auth/login", json={"email": "user@resetco.com", "password": "oldpass123"}
    )
    user_refresh = login.json()["refresh_token"]
    user_id = (
        await client.post(
            "/v1/auth/login", json={"email": "user@resetco.com", "password": "oldpass123"}
        )
    ).status_code
    assert user_id == 200

    # admin reseta a senha do usuário
    users = (await client.get("/v1/auth/users", headers=_auth(admin))).json()
    uid = next(u["id"] for u in users if u["email"] == "user@resetco.com")
    r = await client.patch(
        f"/v1/auth/users/{uid}", headers=_auth(admin), json={"password": "newpass456"}
    )
    assert r.status_code == 200, r.text

    # senha antiga não loga mais; nova sim
    assert (
        await client.post(
            "/v1/auth/login", json={"email": "user@resetco.com", "password": "oldpass123"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/v1/auth/login", json={"email": "user@resetco.com", "password": "newpass456"}
        )
    ).status_code == 200

    # refresh antigo foi revogado (token_version mudou)
    rr = await client.post("/v1/auth/refresh", json={"refresh_token": user_refresh})
    assert rr.status_code == 401, rr.text


async def test_logout_revokes_refresh(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "LogoutCo", "admin@logoutco.com")
    login = await client.post(
        "/v1/auth/login", json={"email": "admin@logoutco.com", "password": "senha1234"}
    )
    refresh = login.json()["refresh_token"]
    access = login.json()["access_token"]

    # refresh funciona antes do logout
    assert (
        await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
    ).status_code == 200

    # logout
    assert (await client.post("/v1/auth/logout", headers=_auth(access))).status_code == 204

    # refresh (o original) agora é rejeitado
    assert (
        await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
    ).status_code == 401


async def test_change_own_password_revokes_old_refresh(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "SelfCo", "admin@selfco.com")
    old_refresh = (
        await client.post(
            "/v1/auth/login", json={"email": "admin@selfco.com", "password": "senha1234"}
        )
    ).json()["refresh_token"]

    r = await client.patch("/v1/auth/me", headers=_auth(admin), json={"password": "brandnew123"})
    assert r.status_code == 200, r.text

    assert (
        await client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    ).status_code == 401


async def test_login_rate_limited_after_max_attempts(client: httpx.AsyncClient) -> None:
    await _register(client, "RateCo", "admin@rateco.com")
    # 5 tentativas erradas (limite padrão) -> ainda 401; a 6ª -> 429
    for _ in range(5):
        bad = await client.post(
            "/v1/auth/login", json={"email": "admin@rateco.com", "password": "errada00"}
        )
        assert bad.status_code == 401, bad.text
    blocked = await client.post(
        "/v1/auth/login", json={"email": "admin@rateco.com", "password": "errada00"}
    )
    assert blocked.status_code == 429, blocked.text
