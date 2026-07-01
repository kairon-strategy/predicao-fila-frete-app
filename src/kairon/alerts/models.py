"""ORM do context alerts. Feed por tenant, com severidade e tipo."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from kairon.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(index=True)
    severity: Mapped[str] = mapped_column(String(20))  # critical | warn | info
    alert_type: Mapped[str] = mapped_column(String(40))  # diesel_spike | antt_revision | ...
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # ex: UF
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), server_default="active")  # active | resolved
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
