"""Habilita RLS em todas as tabelas do schema public

Contexto: no Supabase o PostgREST expõe o schema ``public`` via a *anon key*
(pública em qualquer frontend). Sem RLS, qualquer um com a anon key lê/escreve
direto no banco, contornando a nossa API (ADR-012). Habilitar RLS **sem policies**
faz o default ser *deny* para os papéis do PostgREST (anon/authenticated), enquanto
a nossa API — que conecta como ``postgres`` (bypassa RLS) — segue com acesso total.
O isolamento por tenant continua sendo feito na aplicação (ADR-008).

Idempotente e sem efeito em Postgres local (RLS ligado só muda quem NÃO bypassa).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Todas as tabelas de negócio + controle expostas no schema public.
_TABLES = (
    "tenants",
    "users",
    "routes",
    "raw_diesel_prices",
    "predictions",
    "explanation_cache",
    "audit_events",
    "alerts",
    "alembic_version",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")
        # FORCE garante que até o dono da tabela respeite RLS via PostgREST;
        # a app conecta como superuser (postgres), que continua bypassando.
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY;")
