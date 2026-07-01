"""alerts table (EPIC 8 — detecção + feed)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("alert_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alerts_tenant_status", "alerts", ["tenant_id", "status"])
    op.create_index(
        "ix_alerts_dedup", "alerts", ["tenant_id", "alert_type", "entity_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_dedup", table_name="alerts")
    op.drop_index("ix_alerts_tenant_status", table_name="alerts")
    op.drop_table("alerts")
