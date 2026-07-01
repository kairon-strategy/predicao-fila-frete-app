"""Persistência das linhas normalizadas em `raw_diesel_prices` (upsert idempotente).

Usa upsert do PostgreSQL (`ON CONFLICT DO NOTHING`) sobre a unique constraint
`uq_diesel_data_uf_cidade`, para o ETL semanal ser reexecutável sem duplicar.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert

from kairon.core.database import SessionFactory
from kairon.core.logging import get_logger
from kairon.ingestion.anp.models import RawDieselPrice

log = get_logger(__name__)


async def load(rows: pd.DataFrame) -> int:
    """Faz upsert das linhas normalizadas. Retorna a contagem tentada."""
    if rows is None or rows.empty:
        log.info("anp.loader.done", count=0)
        return 0

    records = rows.to_dict(orient="records")

    async with SessionFactory() as session:
        stmt = pg_insert(RawDieselPrice).values(records)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_diesel_data_uf_cidade")
        await session.execute(stmt)
        await session.commit()

    count = len(records)
    log.info("anp.loader.done", count=count)
    return count
