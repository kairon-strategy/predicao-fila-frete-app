"""Modelos ORM (SQLAlchemy 2.x) do context prediction: Route e Prediction.

Separado de `models/` (que guarda os modelos de ML) para evitar colisão de nome.
DDL correspondente está em migrations/versions/0001_initial_schema.py.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from kairon.core.database import Base


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    origem: Mapped[str] = mapped_column(String(120))
    destino: Mapped[str] = mapped_column(String(120))
    distancia_km: Mapped[float] = mapped_column(Float)
    produto: Mapped[str] = mapped_column(String(60))
    corredor: Mapped[str | None] = mapped_column(String(60), nullable=True)
    piso_antt_r_per_ton: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_prediction_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    origem: Mapped[str] = mapped_column(String(120))
    destino: Mapped[str] = mapped_column(String(120))
    produto: Mapped[str] = mapped_column(String(60))
    data_alvo: Mapped[date] = mapped_column(Date)
    carga_ton: Mapped[float | None] = mapped_column(Float, nullable=True)
    frete_r_per_ton: Mapped[float] = mapped_column(Float)
    banda_p10: Mapped[float] = mapped_column(Float)
    banda_p90: Mapped[float] = mapped_column(Float)
    drivers: Mapped[list] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
