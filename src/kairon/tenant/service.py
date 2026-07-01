"""Serviço de auth: autenticação e emissão de tokens (US-001)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.exceptions import KaironError, ValidationError
from kairon.core.logging import get_logger
from kairon.tenant import security
from kairon.tenant.auth import ROLES
from kairon.tenant.models import Tenant, User
from kairon.tenant.schemas import TokenResponse, UserResponse

log = get_logger(__name__)


class AuthError(KaironError):
    status_code = 401
    error_code = "auth_error"


class ConflictError(KaironError):
    status_code = 409
    error_code = "conflict"


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email.strip().lower())
    return (await session.execute(stmt)).scalars().first()


async def login(session: AsyncSession, email: str, password: str) -> TokenResponse:
    user = await _get_user_by_email(session, email)
    # Verifica senha mesmo se user None? Não temos hash; retornamos erro genérico.
    if (
        user is None
        or not user.is_active
        or not security.verify_password(password, user.hashed_password)
    ):
        log.warning("auth.login_failed", email_hash=hash(email))
        raise AuthError("credenciais inválidas")

    log.info("auth.login_ok", user_id=str(user.id), tenant_id=str(user.tenant_id))
    return _issue_tokens(user_id=user.id, tenant_id=user.tenant_id, role=user.role)


async def refresh(session: AsyncSession, refresh_token: str) -> TokenResponse:
    payload = security.decode_token(refresh_token, expected_type="refresh")
    if payload is None:
        raise AuthError("refresh token inválido ou expirado")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthError("claims inválidas") from exc

    user = (await session.execute(select(User).where(User.id == user_id))).scalars().first()
    if user is None or not user.is_active:
        raise AuthError("usuário inativo ou inexistente")

    return _issue_tokens(user_id=user.id, tenant_id=user.tenant_id, role=user.role)


def _issue_tokens(*, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> TokenResponse:
    return TokenResponse(
        access_token=security.create_access_token(user_id=user_id, tenant_id=tenant_id, role=role),
        refresh_token=security.create_refresh_token(
            user_id=user_id, tenant_id=tenant_id, role=role
        ),
    )


def _slug(name: str) -> str:
    """Slug simples + sufixo curto único (evita colisão de slug entre tenants)."""
    base = "".join(c if c.isalnum() else "-" for c in name.strip().lower()).strip("-")[:40]
    return f"{base or 'tenant'}-{uuid.uuid4().hex[:6]}"


async def register(
    session: AsyncSession, tenant_name: str, email: str, password: str
) -> TokenResponse:
    """Auto-onboarding: cria um tenant novo + primeiro usuário (admin) e loga."""
    email = email.strip().lower()
    if await _get_user_by_email(session, email) is not None:
        raise ConflictError("já existe um usuário com esse email")

    tenant = Tenant(id=uuid.uuid4(), name=tenant_name.strip(), slug=_slug(tenant_name))
    session.add(tenant)
    await session.flush()  # garante tenant antes do FK do user

    user = User(
        tenant_id=tenant.id,
        email=email,
        hashed_password=security.hash_password(password),
        role="admin",
    )
    session.add(user)
    await session.flush()
    log.info("auth.registered", tenant_id=str(tenant.id), user_id=str(user.id))
    return _issue_tokens(user_id=user.id, tenant_id=tenant.id, role="admin")


async def create_user(
    session: AsyncSession, tenant_id: uuid.UUID, email: str, password: str, role: str
) -> UserResponse:
    """Admin cria um usuário no PRÓPRIO tenant (US-002)."""
    if role not in ROLES:
        raise ValidationError(f"papel inválido: {role} (use {', '.join(ROLES)})")
    email = email.strip().lower()
    if await _get_user_by_email(session, email) is not None:
        raise ConflictError("já existe um usuário com esse email")

    user = User(
        tenant_id=tenant_id,
        email=email,
        hashed_password=security.hash_password(password),
        role=role,
    )
    session.add(user)
    await session.flush()
    log.info("auth.user_created", tenant_id=str(tenant_id), user_id=str(user.id), role=role)
    return UserResponse(
        id=str(user.id), email=user.email, role=user.role, tenant_id=str(user.tenant_id)
    )
