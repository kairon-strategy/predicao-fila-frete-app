"""ORM da base de conhecimento (RAG): documentos + chunks com embedding.

Por tenant, com `tenant_id` NULL = base global do sistema. A busca é vetorial
(pgvector). Ver `service.py` para ingestão/recuperação e docs/GOVERNANCA_IA.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from kairon.core.config import settings
from kairon.core.database import Base


class KbDocument(Base):
    """Um documento da base de conhecimento (ex.: uma norma, uma FAQ)."""

    __tablename__ = "kb_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)  # URL/origem citável
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KbChunk(Base):
    """Um trecho (chunk) de um documento + seu embedding para busca vetorial."""

    __tablename__ = "kb_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kb_documents.id", ondelete="CASCADE"), index=True
    )
    # tenant_id desnormalizado do documento para escopar a busca sem join.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))
    section: Mapped[str | None] = mapped_column(String(300), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
