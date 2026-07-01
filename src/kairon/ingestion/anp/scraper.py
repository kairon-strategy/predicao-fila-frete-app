"""Download do CSV público de preços de combustíveis da ANP.

Fonte de referência (série histórica semanal, semicolon-separated, latin-1):
https://dados.gov.br/dados/conjuntos-dados/serie-historica-de-precos-de-combustiveis-e-de-glp

Este módulo faz apenas o download e devolve o frame RAW (sem normalizar).
A normalização vive em `normalizer.py` (função pura, testável).
"""

from __future__ import annotations

import io
from datetime import date, timedelta

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from kairon.core.config import settings
from kairon.core.logging import get_logger

log = get_logger(__name__)

# Timeout do download do CSV (segundos). Os arquivos da ANP são grandes.
_HTTP_TIMEOUT = 60.0


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
async def _download(url: str) -> bytes:
    """Baixa o CSV cru. Com retry exponencial (3 tentativas)."""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def fetch_diesel_csv() -> pd.DataFrame:
    """Baixa o CSV da ANP e devolve o DataFrame RAW.

    Circuit breaker: se a URL estiver vazia OU o download falhar após os retries,
    loga um aviso e devolve um frame sintético (mock) para manter o `make etl-anp`
    funcionando offline. A normalização é feita depois, em `normalize()`.
    """
    url = settings.anp_diesel_csv_url

    # TODO(#12): apontar `anp_diesel_csv_url` para o CSV real da série histórica
    # da ANP (dados.gov.br). Enquanto vazio/indisponível, caímos no mock.
    if not url:
        log.warning("anp.scraper.fallback_mock", reason="empty_url")
        return _mock_raw_frame()

    try:
        raw = await _download(url)
    except Exception as exc:  # download falhou após todos os retries
        log.warning("anp.scraper.fallback_mock", reason="download_failed", error=str(exc))
        return _mock_raw_frame()

    # Arquivos reais da ANP: separador ';', encoding latin-1.
    frame = pd.read_csv(io.BytesIO(raw), sep=";", encoding="latin-1", dtype=str)
    log.info("anp.scraper.downloaded", url=url, rows=len(frame))
    return frame


def _mock_raw_frame() -> pd.DataFrame:
    """Gera ~30 linhas plausíveis com o layout raw da ANP (para modo offline).

    Colunas com nomes semelhantes aos do CSV real (aliases tratados em
    `normalizer.py`). Inclui produtos diesel e não-diesel de propósito.
    """
    ufs = ["SP", "RJ", "MG", "RS", "PR", "BA"]
    cidades = {
        "SP": "SAO PAULO",
        "RJ": "RIO DE JANEIRO",
        "MG": "BELO HORIZONTE",
        "RS": "PORTO ALEGRE",
        "PR": "CURITIBA",
        "BA": "SALVADOR",
    }
    produtos = ["OLEO DIESEL S10", "OLEO DIESEL", "GASOLINA COMUM"]
    base_date = date(2024, 1, 1)

    rows: list[dict[str, str]] = []
    for i, uf in enumerate(ufs):
        semana = (base_date + timedelta(days=7 * (i % 3))).strftime("%d/%m/%Y")
        for j, produto in enumerate(produtos):
            preco = 5.10 + 0.15 * i + 0.30 * j
            rows.append(
                {
                    "Estado - Sigla": uf,
                    "Municipio": cidades[uf],
                    "Produto": produto,
                    "Preco Medio Revenda": f"{preco:.3f}".replace(".", ","),
                    "Data da Coleta": semana,
                }
            )

    return pd.DataFrame(rows)
