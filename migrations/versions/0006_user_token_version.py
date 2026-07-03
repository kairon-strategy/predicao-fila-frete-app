"""users.token_version (revogação de sessão)

Bump da coluna invalida todos os tokens do usuário (logout / troca de senha).
O claim ``tv`` do JWT é comparado com este valor na renovação (refresh).

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
