"""Normalização do frame RAW da ANP para o schema de `raw_diesel_prices`.

Função pura (sem I/O) — fácil de testar unitariamente. Os cabeçalhos do CSV
da ANP variam entre anos/versões, então tratamos aliases conhecidos de forma
defensiva e caímos de volta com graça quando uma coluna não é encontrada.
"""

from __future__ import annotations

import pandas as pd

from kairon.core.logging import get_logger

log = get_logger(__name__)

_FONTE = "ANP"

# Aliases conhecidos por campo lógico -> possíveis nomes na origem (lower/strip).
_ALIASES: dict[str, tuple[str, ...]] = {
    "uf": ("estado - sigla", "uf", "sigla uf", "estado"),
    "cidade": ("municipio", "município", "cidade"),
    "produto": ("produto", "produto - descricao", "combustivel"),
    "preco": (
        "preco medio revenda",
        "preço médio revenda",
        "valor de venda",
        "preco de venda",
        "preço de venda",
        "preco medio",
    ),
    "data": ("data da coleta", "data coleta", "data", "mes"),
}


def _find_column(raw: pd.DataFrame, field: str) -> str | None:
    """Encontra a coluna real correspondente a um campo lógico via aliases."""
    lookup = {str(c).strip().lower(): c for c in raw.columns}
    for alias in _ALIASES[field]:
        if alias in lookup:
            return lookup[alias]
    return None


def _to_price(series: pd.Series) -> pd.Series:
    """Converte string de preço (vírgula decimal) para float, com defesa."""
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace("R$", "", regex=False)
        .str.replace(".", "", regex=False)  # separador de milhar (raro, mas ocorre)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """Normaliza o frame RAW da ANP.

    Retorna um DataFrame com EXATAMENTE as colunas:
    `data` (date), `uf` (2 chars upper), `cidade` (str|None),
    `preco_medio` (float), `fonte` (str, "ANP").

    Filtra somente produtos diesel, descarta linhas sem preço e agrega
    (média) por (data, uf, cidade).
    """
    empty = pd.DataFrame(
        {
            "data": pd.Series([], dtype="object"),
            "uf": pd.Series([], dtype="object"),
            "cidade": pd.Series([], dtype="object"),
            "preco_medio": pd.Series([], dtype="float64"),
            "fonte": pd.Series([], dtype="object"),
        }
    )

    if raw is None or raw.empty:
        log.warning("anp.normalizer.empty_input")
        return empty

    col_uf = _find_column(raw, "uf")
    col_cidade = _find_column(raw, "cidade")
    col_produto = _find_column(raw, "produto")
    col_preco = _find_column(raw, "preco")
    col_data = _find_column(raw, "data")

    missing = [
        name
        for name, col in (
            ("uf", col_uf),
            ("produto", col_produto),
            ("preco", col_preco),
            ("data", col_data),
        )
        if col is None
    ]
    if missing:
        log.warning("anp.normalizer.missing_columns", missing=missing, columns=list(raw.columns))
        return empty

    df = pd.DataFrame(
        {
            "uf": raw[col_uf].astype(str).str.strip().str.upper().str[:2],
            "produto": raw[col_produto].astype(str).str.strip().str.upper(),
            "preco_medio": _to_price(raw[col_preco]),
            "data": pd.to_datetime(raw[col_data], errors="coerce", dayfirst=True),
        }
    )
    if col_cidade is not None:
        cidade = raw[col_cidade].astype(str).str.strip().str.upper()
        df["cidade"] = cidade.where(cidade.ne("") & cidade.ne("NAN"), other=None)
    else:
        df["cidade"] = None

    # Somente produtos diesel (exclui gasolina, etanol, GLP, etc.).
    df = df[df["produto"].str.contains("DIESEL", na=False)]

    # Descarta linhas sem preço ou sem data válida.
    df = df.dropna(subset=["preco_medio", "data"])

    if df.empty:
        log.warning("anp.normalizer.no_diesel_rows")
        return empty

    df["data"] = df["data"].dt.date

    # Agrega (média) por chave, garantindo um preco_medio por (data, uf, cidade).
    grouped = df.groupby(["data", "uf", "cidade"], dropna=False)["preco_medio"].mean().reset_index()
    grouped["fonte"] = _FONTE
    grouped["preco_medio"] = grouped["preco_medio"].astype("float64")

    result = grouped[["data", "uf", "cidade", "preco_medio", "fonte"]].reset_index(drop=True)
    log.info("anp.normalizer.done", rows=len(result))
    return result
