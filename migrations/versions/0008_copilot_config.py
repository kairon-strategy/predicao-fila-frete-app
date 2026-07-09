"""Configuração do copiloto: copilot_prompts + copilot_settings (por tenant).

tenant_id NULL = padrão global. Também faz backfill das novas permissões
`copilot:read`/`copilot:write` nos perfis 'admin' de sistema já existentes
(novos tenants recebem via ensure_default_roles, pois admin = ALL_PERMISSIONS).

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "copilot_prompts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("prompt_key", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.String(120), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "prompt_key", name="uq_copilot_prompt"),
    )
    op.create_table(
        "copilot_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("provider", sa.String(20), server_default="auto", nullable=False),
        sa.Column("model", sa.String(60), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_words", sa.Integer(), nullable=True),
        sa.Column("rate_limit_per_min", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.String(120), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", name="uq_copilot_settings_tenant"),
    )

    # Backfill: dá copilot:read/write aos perfis 'admin' de sistema já existentes
    # (sem duplicar). Novos tenants recebem via ensure_default_roles.
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_key)
        SELECT r.id, p.key
        FROM roles r
        CROSS JOIN (VALUES ('copilot:read'), ('copilot:write')) AS p(key)
        WHERE r.slug = 'admin' AND r.is_system = true
          AND NOT EXISTS (
            SELECT 1 FROM role_permissions rp
            WHERE rp.role_id = r.id AND rp.permission_key = p.key
          )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_key IN ('copilot:read','copilot:write')")
    op.drop_table("copilot_settings")
    op.drop_table("copilot_prompts")
