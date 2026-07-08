"""RBAC dinâmico: tabelas roles + role_permissions (por tenant)

Só o schema. O seed dos 3 perfis padrão por tenant é feito por
`kairon.tenant.service.ensure_default_roles` (idempotente), chamado no register
e nos scripts de seed / backfill — evita seed data-dependente na migration.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_role_tenant_slug"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "role_id",
            sa.Uuid(),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("permission_key", sa.String(50), nullable=False),
        sa.UniqueConstraint("role_id", "permission_key", name="uq_role_permission"),
    )


def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_table("roles")
