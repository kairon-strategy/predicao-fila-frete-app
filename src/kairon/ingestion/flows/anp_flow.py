"""ETL de diesel da ANP — script simples (sem orquestrador).

MVP: baixar 1 CSV por semana não justifica Prefect. Roda como script:

    python -m kairon.ingestion.flows.anp_flow      # roda o ETL uma vez (make etl-anp)

Agendamento em produção: cron do SO / Render Cron Job apontando para o comando
acima (ex: `0 6 * * 1` = segunda 06:00). Sem dependência de orquestrador no MVP.
"""

from __future__ import annotations

import asyncio

from kairon.core.logging import get_logger
from kairon.ingestion.anp.loader import load as load_rows
from kairon.ingestion.anp.normalizer import normalize as normalize_frame
from kairon.ingestion.anp.scraper import fetch_diesel_csv

log = get_logger(__name__)


async def anp_etl() -> int:
    """Orquestra fetch -> normalize -> load. Retorna nº de linhas carregadas."""
    log.info("anp.etl.start")

    raw = await fetch_diesel_csv()
    log.info("anp.etl.fetched", raw_rows=len(raw))

    normalized = normalize_frame(raw)
    log.info("anp.etl.normalized", rows=len(normalized))

    count = await load_rows(normalized)
    log.info("anp.etl.done", loaded=count)
    return count


if __name__ == "__main__":
    try:
        asyncio.run(anp_etl())
    except Exception:
        log.exception("anp.etl.failed")
        raise
