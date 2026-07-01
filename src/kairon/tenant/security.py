"""Primitivas de segurança: hash de senha (bcrypt) + emissão/verificação de JWT (US-001).

Sem LangChain, sem passlib — bcrypt direto + python-jose. Funções puras, testáveis.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
from jose import JWTError, jwt

from kairon.core.config import settings

TokenType = Literal["access", "refresh"]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _create_token(
    *, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str, token_type: TokenType, ttl: timedelta
) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> str:
    return _create_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        token_type="access",
        ttl=timedelta(minutes=settings.access_token_ttl_min),
    )


def create_refresh_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> str:
    return _create_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        token_type="refresh",
        ttl=timedelta(days=settings.refresh_token_ttl_days),
    )


def decode_token(token: str, *, expected_type: TokenType | None = None) -> dict[str, Any] | None:
    """Decodifica e valida assinatura/expiração. None se inválido ou tipo inesperado."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None
    if expected_type is not None and payload.get("type") != expected_type:
        return None
    return payload
