"""Testa o fallback do scraper ANP (URL vazia -> frame mock, sem rede) + pipeline até normalizar."""

from __future__ import annotations

from kairon.ingestion.anp.normalizer import normalize
from kairon.ingestion.anp.scraper import fetch_diesel_csv


async def test_fetch_sem_url_retorna_mock() -> None:
    # settings.anp_diesel_csv_url é "" por padrão -> circuit breaker devolve mock (sem rede).
    raw = await fetch_diesel_csv()
    assert not raw.empty


async def test_scraper_para_normalizer_end_to_end() -> None:
    raw = await fetch_diesel_csv()
    norm = normalize(raw)
    # Após normalizar, colunas canônicas e só diesel.
    assert set(norm.columns) == {"data", "uf", "cidade", "preco_medio", "fonte"}
    assert len(norm) > 0
    assert (norm["preco_medio"] > 0).all()
