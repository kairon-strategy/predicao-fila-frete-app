"""Autenticação/autorização por request (US-001/US-004/US-006).

- `Principal`: quem está fazendo a request (tenant + papel).
- `get_principal`: extrai do JWT. Sem token OU token inválido -> 401
  (autenticação é obrigatória em todo endpoint protegido; /health, login e
  register são públicos por não dependerem deste dependency).
- `require_permission`: RBAC dinâmico — exige uma chave de permissão (vinda do
  perfil do usuário, embutida no JWT). `require_role` fica como legado.
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
    permissions: frozenset[str] = frozenset()


async def get_principal(authorization: str | None = Header(default=None)) -> Principal:
    # Autenticação obrigatória: sem Authorization -> 401 (nunca mais anônimo=admin).
    if not authorization:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "autenticação obrigatória")
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
        permissions=frozenset(payload.get("perms", [])),
    )


def require_permission(*required: str):  # type: ignore[no-untyped-def]
    """Dependency factory de RBAC dinâmico. Ex: Depends(require_permission('routes:write')).

    Exige TODAS as chaves informadas (AND). Nega com 403 se faltar alguma.
    """

    async def _checker(principal: Principal = Depends(get_principal)) -> Principal:
        missing = [k for k in required if k not in principal.permissions]
        if missing:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"permissão negada (requer: {', '.join(required)})",
            )
        return principal

    return _checker


def require_role(*allowed: str):  # type: ignore[no-untyped-def]
    """Legado (RBAC por papel). Mantido para compat; endpoints usam require_permission."""

    async def _checker(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"papel '{principal.role}' não autorizado (requer: {', '.join(allowed)})",
            )
        return principal

    return _checker
