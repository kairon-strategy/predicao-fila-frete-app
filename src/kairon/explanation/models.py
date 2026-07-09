"""ORM do context explanation: cache de explicações + configuração do copiloto.

Config do copiloto (prompts + settings) é por tenant, com `tenant_id` NULL =
padrão global do sistema. A resolução (tenant -> global -> default do código)
fica em `copilot_config.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairon.core.database import Base


class ExplanationCache(Base):
    __tablename__ = "explanation_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("predictions.id"), nullable=True
    )
    prompt_hash: Mapped[str] = mapped_column(String(64), unique=True)
    explanation: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), server_default="llm")  # llm | template
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CopilotPrompt(Base):
    """Prompt de um fluxo do copiloto. tenant_id NULL = padrão global.

    Uma linha por (tenant_id, prompt_key). Se um tenant não tiver linha, herda a
    global (NULL); se não houver global, cai no template em disco (.j2).
    """

    __tablename__ = "copilot_prompts"
    __table_args__ = (UniqueConstraint("tenant_id", "prompt_key", name="uq_copilot_prompt"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    prompt_key: Mapped[str] = mapped_column(String(50))  # explain_prediction | explain_with_question | simulate_nl
    content: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CopilotSettings(Base):
    """Configuração do copiloto por tenant. tenant_id NULL = padrão global.

    Campos NULL = 'herda' (do global ou do env). `enabled=False` força template.
    """

    __tablename__ = "copilot_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_copilot_settings_tenant"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=func.true())
    provider: Mapped[str] = mapped_column(String(20), server_default="auto")  # auto | openai | anthropic
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_words: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_per_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
