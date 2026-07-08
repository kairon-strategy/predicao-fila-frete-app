"""E2E do RBAC dinâmico: perfis por tenant + matriz de permissões."""

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


async def test_default_roles_seeded_on_register(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "RolesCo", "admin@rolesco.com")
    roles = (await client.get("/v1/auth/roles", headers=_auth(admin))).json()
    slugs = {r["slug"] for r in roles}
    assert {"admin", "analyst", "viewer"} <= slugs
    admin_role = next(r for r in roles if r["slug"] == "admin")
    assert admin_role["is_system"] is True
    assert "roles:write" in admin_role["permissions"]
    # catálogo de permissões disponível
    cat = (await client.get("/v1/auth/permissions", headers=_auth(admin))).json()
    assert any(p["key"] == "routes:write" for p in cat)


async def test_custom_role_grants_exact_permissions(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "CustomCo", "admin@customco.com")
    # perfil só-leitura de rotas
    r = await client.post(
        "/v1/auth/roles",
        headers=_auth(admin),
        json={"name": "Somente Rotas", "permissions": ["routes:read"]},
    )
    assert r.status_code == 201, r.text
    slug = r.json()["slug"]

    # cria usuário com esse perfil e loga
    await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "u@customco.com", "password": "senha1234", "role": slug},
    )
    tok = (
        await client.post(
            "/v1/auth/login", json={"email": "u@customco.com", "password": "senha1234"}
        )
    ).json()["access_token"]

    me = (await client.get("/v1/auth/me", headers=_auth(tok))).json()
    assert me["permissions"] == ["routes:read"]
    # tem routes:read -> lê ranking
    assert (await client.get("/v1/routes", headers=_auth(tok))).status_code == 200
    # não tem routes:write -> 403 ao criar rota
    assert (
        await client.post(
            "/v1/routes",
            headers=_auth(tok),
            json={"origem": "Sorriso-MT", "destino": "Santos-SP", "produto": "soja", "distancia_km": 500},
        )
    ).status_code == 403
    # não tem predict:run -> 403
    assert (
        await client.post(
            "/v1/predict",
            headers={**_auth(tok), "idempotency-key": "rbac-1"},
            json={"origem": "Sorriso-MT", "destino": "Santos-SP", "produto": "soja", "data": "2026-08-15"},
        )
    ).status_code == 403


async def test_editing_role_permissions_applies_after_refresh(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "EditCo", "admin@editco.com")
    role = (
        await client.post(
            "/v1/auth/roles",
            headers=_auth(admin),
            json={"name": "Operador", "permissions": ["routes:read"]},
        )
    ).json()
    await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "op@editco.com", "password": "senha1234", "role": role["slug"]},
    )
    login = await client.post(
        "/v1/auth/login", json={"email": "op@editco.com", "password": "senha1234"}
    )
    refresh = login.json()["refresh_token"]

    # sem routes:write ainda
    assert (
        await client.post(
            "/v1/routes",
            headers=_auth(login.json()["access_token"]),
            json={"origem": "Sorriso-MT", "destino": "Santos-SP", "produto": "soja", "distancia_km": 500},
        )
    ).status_code == 403

    # admin concede routes:write ao perfil
    upd = await client.patch(
        f"/v1/auth/roles/{role['id']}",
        headers=_auth(admin),
        json={"permissions": ["routes:read", "routes:write"]},
    )
    assert upd.status_code == 200

    # após refresh, o novo token carrega a permissão
    new_access = (
        await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
    ).json()["access_token"]
    assert (
        await client.post(
            "/v1/routes",
            headers=_auth(new_access),
            json={"origem": "Sorriso-MT", "destino": "Santos-SP", "produto": "soja", "distancia_km": 500},
        )
    ).status_code == 201


async def test_delete_role_rules(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "DelCo", "admin@delco.com")
    roles = (await client.get("/v1/auth/roles", headers=_auth(admin))).json()
    admin_role_id = next(r["id"] for r in roles if r["slug"] == "admin")
    # perfil de sistema não pode ser excluído
    assert (
        await client.delete(f"/v1/auth/roles/{admin_role_id}", headers=_auth(admin))
    ).status_code == 422

    # cria perfil custom, usa num usuário -> não pode excluir
    role = (
        await client.post(
            "/v1/auth/roles",
            headers=_auth(admin),
            json={"name": "Temp", "permissions": ["routes:read"]},
        )
    ).json()
    await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "temp@delco.com", "password": "senha1234", "role": role["slug"]},
    )
    assert (
        await client.delete(f"/v1/auth/roles/{role['id']}", headers=_auth(admin))
    ).status_code == 422

    # perfil custom sem uso -> 204
    empty = (
        await client.post(
            "/v1/auth/roles",
            headers=_auth(admin),
            json={"name": "Vazio", "permissions": []},
        )
    ).json()
    assert (
        await client.delete(f"/v1/auth/roles/{empty['id']}", headers=_auth(admin))
    ).status_code == 204


async def test_non_admin_cannot_manage_roles(client: httpx.AsyncClient) -> None:
    admin = await _register(client, "GuardCo", "admin@guardco.com")
    await client.post(
        "/v1/auth/users",
        headers=_auth(admin),
        json={"email": "v@guardco.com", "password": "senha1234", "role": "viewer"},
    )
    vt = (
        await client.post(
            "/v1/auth/login", json={"email": "v@guardco.com", "password": "senha1234"}
        )
    ).json()["access_token"]
    # viewer não tem roles:read nem roles:write
    assert (await client.get("/v1/auth/roles", headers=_auth(vt))).status_code == 403
    assert (
        await client.post(
            "/v1/auth/roles", headers=_auth(vt), json={"name": "X", "permissions": []}
        )
    ).status_code == 403
