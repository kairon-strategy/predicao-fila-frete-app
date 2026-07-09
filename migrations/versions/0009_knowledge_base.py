"""Base de conhecimento (RAG): extensão pgvector + kb_documents + kb_chunks.

tenant_id NULL = base global. Índice HNSW (cosine) para busca vetorial.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE kb_documents (
            id UUID PRIMARY KEY,
            tenant_id UUID REFERENCES tenants(id),
            title VARCHAR(300) NOT NULL,
            source VARCHAR(300),
            created_by VARCHAR(120),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_kb_documents_tenant_id ON kb_documents (tenant_id)")
    op.execute(
        """
        CREATE TABLE kb_chunks (
            id UUID PRIMARY KEY,
            document_id UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
            tenant_id UUID,
            content TEXT NOT NULL,
            embedding vector(1536) NOT NULL,
            section VARCHAR(300),
            chunk_index INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_kb_chunks_document_id ON kb_chunks (document_id)")
    op.execute("CREATE INDEX ix_kb_chunks_tenant_id ON kb_chunks (tenant_id)")
    op.execute(
        "CREATE INDEX ix_kb_chunks_embedding ON kb_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS kb_chunks")
    op.execute("DROP TABLE IF EXISTS kb_documents")
