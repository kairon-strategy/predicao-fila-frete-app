"""Testes unitários de auth: hashing, JWT e principal/RBAC (sem DB)."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from kairon.tenant import security
from kairon.tenant.auth import get_principal, require_role


def test_password_hash_roundtrip() -> None:
    h = security.hash_password("segredo123")
    assert h != "segredo123"
    assert security.verify_password("segredo123", h)
    assert not security.verify_password("errado", h)


def test_access_token_roundtrip() -> None:
    uid, tid = uuid.uuid4(), uuid.uuid4()
    token = security.create_access_token(user_id=uid, tenant_id=tid, role="admin")
    payload = security.decode_token(token, expected_type="access")
    assert payload is not None
    assert payload["sub"] == str(uid)
    assert payload["tenant_id"] == str(tid)
    assert payload["role"] == "admin"


def test_token_type_mismatch_rejected() -> None:
    uid, tid = uuid.uuid4(), uuid.uuid4()
    refresh = security.create_refresh_token(user_id=uid, tenant_id=tid, role="viewer")
    # pedir 'access' num refresh -> None
    assert security.decode_token(refresh, expected_type="access") is None
    assert security.decode_token(refresh, expected_type="refresh") is not None


def test_decode_garbage_returns_none() -> None:
    assert security.decode_token("nao.e.um.jwt") is None


async def test_get_principal_anonymous_rejected_401() -> None:
    # Sem token -> 401 (nunca mais anônimo tratado como admin).
    with pytest.raises(HTTPException) as exc:
        await get_principal(authorization=None)
    assert exc.value.status_code == 401


async def test_get_principal_bad_scheme_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_principal(authorization="Basic xyz")
    assert exc.value.status_code == 401


async def test_get_principal_valid_token() -> None:
    uid, tid = uuid.uuid4(), uuid.uuid4()
    token = security.create_access_token(user_id=uid, tenant_id=tid, role="analyst")
    principal = await get_principal(authorization=f"Bearer {token}")
    assert principal.authenticated is True
    assert principal.tenant_id == tid
    assert principal.role == "analyst"


async def test_require_role_allows_and_blocks() -> None:
    uid, tid = uuid.uuid4(), uuid.uuid4()
    checker = require_role("admin", "analyst")

    analyst = security.create_access_token(user_id=uid, tenant_id=tid, role="analyst")
    principal = await get_principal(authorization=f"Bearer {analyst}")
    assert (await checker(principal=principal)).role == "analyst"

    viewer = security.create_access_token(user_id=uid, tenant_id=tid, role="viewer")
    vp = await get_principal(authorization=f"Bearer {viewer}")
    with pytest.raises(HTTPException) as exc:
        await checker(principal=vp)
    assert exc.value.status_code == 403
