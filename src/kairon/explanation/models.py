"""ORM do context explanation: cache de explicações (hash do prompt -> texto)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
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
