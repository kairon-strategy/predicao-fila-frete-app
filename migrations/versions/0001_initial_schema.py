"""initial schema — tenants, routes, raw_diesel_prices, predictions, explanation_cache, audit_events

Revision ID: 0001
Revises:
Create Date: 2026-07-01

DDL escrito à mão (não autogenerate — ver anti-padrões). Toda tabela com dado
sensível tem coluna tenant_id preparada para RLS na v2 (seção 8).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- tenants ----
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- routes (55 rotas do MVP: 50 fertilizante + 5 algodão) ----
    op.create_table(
        "routes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("origem", sa.String(120), nullable=False),
        sa.Column("destino", sa.String(120), nullable=False),
        sa.Column("distancia_km", sa.Float(), nullable=False),
        sa.Column("produto", sa.String(60), nullable=False),
        sa.Column("corredor", sa.String(60), nullable=True),
        sa.Column("piso_antt_r_per_ton", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_routes_od", "routes", ["origem", "destino", "produto"])

    # ---- raw_diesel_prices (populada pelo ETL ANP) ----
    op.create_table(
        "raw_diesel_prices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("uf", sa.String(2), nullable=False),
        sa.Column("cidade", sa.String(120), nullable=True),
        sa.Column("preco_medio", sa.Float(), nullable=False),
        sa.Column("fonte", sa.String(60), nullable=False, server_default="ANP"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("data", "uf", "cidade", "fonte", name="uq_diesel_data_uf_cidade"),
    )
    op.create_index("ix_diesel_data_uf", "raw_diesel_prices", ["data", "uf"])

    # ---- predictions (source of truth das predições servidas) ----
    op.create_table(
        "predictions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("origem", sa.String(120), nullable=False),
        sa.Column("destino", sa.String(120), nullable=False),
        sa.Column("produto", sa.String(60), nullable=False),
        sa.Column("data_alvo", sa.Date(), nullable=False),
        sa.Column("carga_ton", sa.Float(), nullable=True),
        sa.Column("frete_r_per_ton", sa.Float(), nullable=False),
        sa.Column("banda_p10", sa.Float(), nullable=False),
        sa.Column("banda_p90", sa.Float(), nullable=False),
        sa.Column("drivers", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        # idempotência: mesma chave + tenant = mesma predição.
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_prediction_idempotency"),
    )

    # ---- explanation_cache (hash do prompt -> texto, TTL 1h) ----
    op.create_table(
        "explanation_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prediction_id", sa.Uuid(), sa.ForeignKey("predictions.id"), nullable=True),
        sa.Column("prompt_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="llm"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ---- audit_events (append-only, imutável — seção 8) ----
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_type_created", "audit_events", ["event_type", "created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("explanation_cache")
    op.drop_table("predictions")
    op.drop_table("raw_diesel_prices")
    op.drop_index("ix_routes_od", table_name="routes")
    op.drop_table("routes")
    op.drop_table("tenants")
