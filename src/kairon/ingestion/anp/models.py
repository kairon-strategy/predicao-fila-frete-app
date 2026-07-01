"""ORM do context ingestion: raw_diesel_prices (populada pelo ETL ANP).

Lida também pelo prediction.service para pegar o diesel mais recente por UF.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from kairon.core.database import Base


class RawDieselPrice(Base):
    __tablename__ = "raw_diesel_prices"
    __table_args__ = (
        UniqueConstraint("data", "uf", "cidade", "fonte", name="uq_diesel_data_uf_cidade"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data: Mapped[date] = mapped_column(Date)
    uf: Mapped[str] = mapped_column(String(2))
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preco_medio: Mapped[float] = mapped_column(Float)
    fonte: Mapped[str] = mapped_column(String(60), server_default="ANP")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
