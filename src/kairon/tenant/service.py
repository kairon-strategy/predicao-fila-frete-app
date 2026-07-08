"""Serviço de auth: autenticação e emissão de tokens (US-001)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.audit import writer as audit
from kairon.core.exceptions import KaironError, NotFoundError, ValidationError
from kairon.core.logging import get_logger
from kairon.tenant import roles_service, security
from kairon.tenant.models import Tenant, User
from kairon.tenant.schemas import TenantResponse, TokenResponse, UserResponse

log = get_logger(__name__)


class AuthError(KaironError):
    status_code = 401
    error_code = "auth_error"


class ConflictError(KaironError):
    status_code = 409
    error_code = "conflict"


# Hash "dummy" (bcrypt válido) para gastar o MESMO tempo quando o usuário não
# existe/está inativo — evita timing attack de enumeração de emails (OWASP).
_DUMMY_PASSWORD_HASH = security.hash_password("kairon-timing-guard")


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email.strip().lower())
    return (await session.execute(stmt)).scalars().first()


async def login(session: AsyncSession, email: str, password: str) -> TokenResponse:
    user = await _get_user_by_email(session, email)
    # Tempo constante: roda bcrypt mesmo sem usuário (contra o dummy) para que a
    # latência não revele se o email existe. Mensagem sempre genérica.
    if user is None or not user.is_active:
        security.verify_password(password, _DUMMY_PASSWORD_HASH)
        log.warning("auth.login_failed", email_hash=hash(email))
        raise AuthError("credenciais inválidas")
    if not security.verify_password(password, user.hashed_password):
        log.warning("auth.login_failed", email_hash=hash(email))
        raise AuthError("credenciais inválidas")

    log.info("auth.login_ok", user_id=str(user.id), tenant_id=str(user.tenant_id))
    await audit.write_event(
        session,
        event_type="auth.login",
        entity_id=str(user.id),
        payload={"role": user.role},
        tenant_id=user.tenant_id,
    )
    perms = await roles_service.permissions_for_role(session, user.tenant_id, user.role)
    return _issue_tokens(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        token_version=user.token_version,
        permissions=perms,
    )


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
    # Revogação: refresh só vale se a versão de sessão bater (logout / troca de senha).
    if payload.get("tv") != user.token_version:
        raise AuthError("sessão revogada; faça login novamente")

    # Re-resolve as permissões (mudanças de perfil valem a partir daqui).
    perms = await roles_service.permissions_for_role(session, user.tenant_id, user.role)
    return _issue_tokens(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        token_version=user.token_version,
        permissions=perms,
    )


def _issue_tokens(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    token_version: int,
    permissions: list[str],
) -> TokenResponse:
    return TokenResponse(
        access_token=security.create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            token_version=token_version,
            permissions=permissions,
        ),
        refresh_token=security.create_refresh_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            token_version=token_version,
            permissions=permissions,
        ),
    )


def _slug(name: str) -> str:
    """Slug simples + sufixo curto único (evita colisão de slug entre tenants)."""
    base = "".join(c if c.isalnum() else "-" for c in name.strip().lower()).strip("-")[:40]
    return f"{base or 'tenant'}-{uuid.uuid4().hex[:6]}"


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        tenant_id=str(user.tenant_id),
    )


async def register(
    session: AsyncSession,
    tenant_name: str,
    email: str,
    password: str,
    name: str | None = None,
) -> TokenResponse:
    """Auto-onboarding: cria um tenant novo + primeiro usuário (admin) e loga."""
    email = email.strip().lower()
    if await _get_user_by_email(session, email) is not None:
        raise ConflictError("já existe um usuário com esse email")

    tenant = Tenant(id=uuid.uuid4(), name=tenant_name.strip(), slug=_slug(tenant_name))
    session.add(tenant)
    await session.flush()  # garante tenant antes do FK do user
    await roles_service.ensure_default_roles(session, tenant.id)  # 3 perfis padrão

    user = User(
        tenant_id=tenant.id,
        email=email,
        name=name.strip() if name else None,
        hashed_password=security.hash_password(password),
        role="admin",
    )
    session.add(user)
    await session.flush()
    log.info("auth.registered", tenant_id=str(tenant.id), user_id=str(user.id))
    await audit.write_event(
        session,
        event_type="auth.registered",
        entity_id=str(user.id),
        payload={"tenant": tenant.name},
        tenant_id=tenant.id,
    )
    perms = await roles_service.permissions_for_role(session, tenant.id, "admin")
    return _issue_tokens(
        user_id=user.id,
        tenant_id=tenant.id,
        role="admin",
        token_version=user.token_version,
        permissions=perms,
    )


async def create_user(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    email: str,
    password: str,
    role: str,
    name: str | None = None,
) -> UserResponse:
    """Admin cria um usuário no PRÓPRIO tenant (US-002)."""
    await roles_service.ensure_default_roles(session, tenant_id)
    if not await roles_service.role_exists(session, tenant_id, role):
        raise ValidationError(f"perfil inválido: {role}")
    email = email.strip().lower()
    if await _get_user_by_email(session, email) is not None:
        raise ConflictError("já existe um usuário com esse email")

    user = User(
        tenant_id=tenant_id,
        email=email,
        name=name.strip() if name else None,
        hashed_password=security.hash_password(password),
        role=role,
    )
    session.add(user)
    await session.flush()
    log.info("auth.user_created", tenant_id=str(tenant_id), user_id=str(user.id), role=role)
    await audit.write_event(
        session,
        event_type="auth.user_created",
        entity_id=str(user.id),
        payload={"role": role, "email": email},
        tenant_id=tenant_id,
    )
    return _to_user_response(user)


async def list_users(session: AsyncSession, tenant_id: uuid.UUID) -> list[UserResponse]:
    """Lista usuários do tenant (admin). Isolado por tenant_id."""
    stmt = select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)
    users = (await session.execute(stmt)).scalars().all()
    return [_to_user_response(u) for u in users]


async def update_user(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    role: str | None = None,
    is_active: bool | None = None,
    password: str | None = None,
) -> UserResponse:
    """Admin edita papel/ativação e/ou reseta a senha de um usuário do PRÓPRIO tenant.

    Reset de senha e desativação revogam as sessões do alvo (bump token_version):
    a senha nova/o bloqueio passam a valer imediatamente na renovação.
    """
    user = (
        (await session.execute(select(User).where(User.id == user_id, User.tenant_id == tenant_id)))
        .scalars()
        .first()
    )
    if user is None:
        raise NotFoundError("usuário não encontrado")
    revoke = False
    if role is not None:
        if not await roles_service.role_exists(session, tenant_id, role):
            raise ValidationError(f"perfil inválido: {role}")
        user.role = role
        revoke = True  # muda o perfil -> revoga sessões p/ novas permissões valerem já
    if is_active is not None:
        user.is_active = is_active
        if not is_active:
            revoke = True
    if password is not None:
        user.hashed_password = security.hash_password(password)
        revoke = True
    if revoke:
        user.token_version += 1
    await session.flush()
    log.info("auth.user_updated", tenant_id=str(tenant_id), user_id=str(user_id))
    await audit.write_event(
        session,
        event_type="auth.password_reset" if password is not None else "auth.user_updated",
        entity_id=str(user_id),
        payload={"role": role, "is_active": is_active, "password_reset": password is not None},
        tenant_id=tenant_id,
    )
    return _to_user_response(user)


async def update_me(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    name: str | None = None,
    password: str | None = None,
) -> UserResponse:
    """Usuário edita o próprio perfil (nome e/ou senha).

    Trocar a senha revoga as demais sessões (bump token_version). O token atual
    do próprio usuário segue válido até expirar; o refresh exigirá novo login.
    """
    user = (await session.execute(select(User).where(User.id == user_id))).scalars().first()
    if user is None:
        raise NotFoundError("usuário não encontrado")
    if name is not None:
        user.name = name.strip() or None
    if password is not None:
        user.hashed_password = security.hash_password(password)
        user.token_version += 1
    await session.flush()
    log.info("auth.me_updated", user_id=str(user_id))
    if password is not None:
        await audit.write_event(
            session,
            event_type="auth.password_changed",
            entity_id=str(user_id),
            payload={},
            tenant_id=user.tenant_id,
        )
    return _to_user_response(user)


async def logout(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoga as sessões do usuário (bump token_version).

    O refresh token para de funcionar imediatamente; o access token atual expira
    em <= access_token_ttl_min. Stateless no caminho de request (sem denylist).
    """
    user = (await session.execute(select(User).where(User.id == user_id))).scalars().first()
    if user is None:
        raise NotFoundError("usuário não encontrado")
    user.token_version += 1
    await session.flush()
    log.info("auth.logout", user_id=str(user_id))
    await audit.write_event(
        session,
        event_type="auth.logout",
        entity_id=str(user_id),
        payload={},
        tenant_id=user.tenant_id,
    )


async def get_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> TenantResponse:
    tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalars().first()
    if tenant is None:
        raise NotFoundError("empresa não encontrada")
    return TenantResponse(id=str(tenant.id), name=tenant.name, slug=tenant.slug)


async def update_tenant(session: AsyncSession, tenant_id: uuid.UUID, name: str) -> TenantResponse:
    """Admin edita o nome da empresa (tenant)."""
    tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalars().first()
    if tenant is None:
        raise NotFoundError("empresa não encontrada")
    tenant.name = name.strip()
    await session.flush()
    log.info("tenant.updated", tenant_id=str(tenant_id))
    return TenantResponse(id=str(tenant.id), name=tenant.name, slug=tenant.slug)
