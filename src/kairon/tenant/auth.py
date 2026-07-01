"""Autenticação/autorização por request (US-001/US-004/US-006).

- `Principal`: quem está fazendo a request (tenant + papel).
- `get_principal`: extrai do JWT. Sem token -> principal ANÔNIMO no tenant default
  (compat MVP: os endpoints públicos de predição continuam funcionando).
  Token presente porém inválido -> 401.
- `require_role`: RBAC (admin | analyst | viewer).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from kairon.core.logging import get_logger
from kairon.tenant.security import decode_token

log = get_logger(__name__)

# Tenant default do MVP single-tenant. Casa com o seed (uuid.UUID(int=0)).
DEFAULT_TENANT_ID = uuid.UUID(int=0)

ROLES = ("admin", "analyst", "viewer")


@dataclass(frozen=True)
class Principal:
    tenant_id: uuid.UUID
    role: str
    user_id: uuid.UUID | None = None
    authenticated: bool = False


# Anônimo: tenant default, papel admin (compat MVP — endpoints abertos seguem full).
_ANONYMOUS = Principal(tenant_id=DEFAULT_TENANT_ID, role="admin", user_id=None, authenticated=False)


async def get_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization:
        return _ANONYMOUS
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "esquema de auth inválido")

    token = authorization.split(" ", 1)[1]
    payload = decode_token(token, expected_type="access")
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido ou expirado")

    try:
        tenant_id = uuid.UUID(payload["tenant_id"])
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "claims do token inválidas") from exc

    return Principal(
        tenant_id=tenant_id,
        role=payload.get("role", "viewer"),
        user_id=user_id,
        authenticated=True,
    )


def require_role(*allowed: str):  # type: ignore[no-untyped-def]
    """Dependency factory de RBAC. Ex: Depends(require_role('admin', 'analyst'))."""

    async def _checker(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"papel '{principal.role}' não autorizado (requer: {', '.join(allowed)})",
            )
        return principal

    return _checker
