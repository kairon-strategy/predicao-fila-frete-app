"""RBAC dinâmico: perfis (roles) por tenant + resolução de permissões.

Perfis vivem no banco (por tenant); permissões são um catálogo fixo do código
(`permissions.PERMISSIONS`). Os 3 perfis padrão são semeados por tenant como
`is_system` (não deletáveis, mas com permissões editáveis).
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.exceptions import KaironError, NotFoundError, ValidationError
from kairon.core.logging import get_logger
from kairon.tenant.models import Role, RolePermission, User
from kairon.tenant.permissions import (
    DEFAULT_ROLES,
    PERMISSIONS,
    SYSTEM_ROLE_SLUGS,
    is_valid_permission,
)

log = get_logger(__name__)


class ConflictError(KaironError):
    status_code = 409
    error_code = "conflict"


def _slugify(name: str) -> str:
    base = "".join(c if c.isalnum() else "-" for c in name.strip().lower()).strip("-")[:40]
    return base or "perfil"


async def ensure_default_roles(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Semeia os 3 perfis padrão + permissões no tenant (idempotente)."""
    existing = set(
        (
            await session.execute(select(Role.slug).where(Role.tenant_id == tenant_id))
        ).scalars().all()
    )
    for slug, (name, perms) in DEFAULT_ROLES.items():
        if slug in existing:
            continue
        role = Role(tenant_id=tenant_id, name=name, slug=slug, is_system=True)
        session.add(role)
        await session.flush()
        for key in perms:
            session.add(RolePermission(role_id=role.id, permission_key=key))
    await session.flush()


async def permissions_for_role(
    session: AsyncSession, tenant_id: uuid.UUID, role_slug: str
) -> list[str]:
    """Permissões de um perfil (por slug) dentro do tenant. [] se o perfil não existir."""
    role = (
        await session.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.slug == role_slug)
        )
    ).scalars().first()
    if role is None:
        # fallback: se o tenant ainda não tem perfis semeados, usa o default do código
        if role_slug in DEFAULT_ROLES:
            return sorted(DEFAULT_ROLES[role_slug][1])
        return []
    keys = (
        await session.execute(
            select(RolePermission.permission_key).where(RolePermission.role_id == role.id)
        )
    ).scalars().all()
    return sorted(keys)


async def role_exists(session: AsyncSession, tenant_id: uuid.UUID, slug: str) -> bool:
    r = (
        await session.execute(
            select(Role.id).where(Role.tenant_id == tenant_id, Role.slug == slug)
        )
    ).scalars().first()
    return r is not None


def permission_catalog() -> list[dict[str, str]]:
    """Catálogo de permissões para a UI montar a matriz."""
    return [{"key": k, "group": g, "label": lbl} for k, (g, lbl) in PERMISSIONS.items()]


async def _role_to_dict(session: AsyncSession, role: Role) -> dict:
    perms = (
        await session.execute(
            select(RolePermission.permission_key).where(RolePermission.role_id == role.id)
        )
    ).scalars().all()
    users = (
        await session.execute(
            select(func.count())
            .select_from(User)
            .where(User.tenant_id == role.tenant_id, User.role == role.slug)
        )
    ).scalar_one()
    return {
        "id": str(role.id),
        "name": role.name,
        "slug": role.slug,
        "is_system": role.is_system,
        "permissions": sorted(perms),
        "user_count": int(users),
    }


async def list_roles(session: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    await ensure_default_roles(session, tenant_id)  # garante os padrões
    roles = (
        await session.execute(
            select(Role).where(Role.tenant_id == tenant_id).order_by(Role.is_system.desc(), Role.name)
        )
    ).scalars().all()
    return [await _role_to_dict(session, r) for r in roles]


def _validate_perms(permissions: list[str]) -> None:
    invalid = [p for p in permissions if not is_valid_permission(p)]
    if invalid:
        raise ValidationError(f"permissões inválidas: {', '.join(invalid)}")


async def create_role(
    session: AsyncSession, tenant_id: uuid.UUID, name: str, permissions: list[str]
) -> dict:
    _validate_perms(permissions)
    slug = _slugify(name)
    if await role_exists(session, tenant_id, slug):
        raise ConflictError(f"já existe um perfil com o slug '{slug}'")
    role = Role(tenant_id=tenant_id, name=name.strip(), slug=slug, is_system=False)
    session.add(role)
    await session.flush()
    for key in set(permissions):
        session.add(RolePermission(role_id=role.id, permission_key=key))
    await session.flush()
    log.info("roles.created", tenant_id=str(tenant_id), slug=slug)
    return await _role_to_dict(session, role)


async def update_role(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    role_id: uuid.UUID,
    *,
    name: str | None = None,
    permissions: list[str] | None = None,
) -> dict:
    role = (
        await session.execute(
            select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id)
        )
    ).scalars().first()
    if role is None:
        raise NotFoundError("perfil não encontrado")
    if name is not None:
        role.name = name.strip()  # slug (usado no token) não muda ao renomear
    if permissions is not None:
        _validate_perms(permissions)
        await session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        for key in set(permissions):
            session.add(RolePermission(role_id=role.id, permission_key=key))
    await session.flush()
    log.info("roles.updated", tenant_id=str(tenant_id), slug=role.slug)
    return await _role_to_dict(session, role)


async def delete_role(session: AsyncSession, tenant_id: uuid.UUID, role_id: uuid.UUID) -> None:
    role = (
        await session.execute(
            select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id)
        )
    ).scalars().first()
    if role is None:
        raise NotFoundError("perfil não encontrado")
    if role.is_system or role.slug in SYSTEM_ROLE_SLUGS:
        raise ValidationError("perfil de sistema não pode ser excluído")
    in_use = (
        await session.execute(
            select(func.count())
            .select_from(User)
            .where(User.tenant_id == tenant_id, User.role == role.slug)
        )
    ).scalar_one()
    if in_use:
        raise ValidationError(f"perfil em uso por {in_use} usuário(s); reatribua antes de excluir")
    await session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
    await session.delete(role)
    await session.flush()
    log.info("roles.deleted", tenant_id=str(tenant_id), slug=role.slug)
