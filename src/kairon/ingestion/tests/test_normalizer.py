"""Testes unitários puros para `normalize()`.

Sem DB, sem rede. Usam um DataFrame in-memory que imita os cabeçalhos raw
da ANP, incluindo linhas não-diesel (que devem ser filtradas) e uma chave
(data, uf, cidade) duplicada (que deve ser mediada).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from kairon.ingestion.anp.normalizer import normalize

EXPECTED_COLUMNS = ["data", "uf", "cidade", "preco_medio", "fonte"]


def _raw_sample() -> pd.DataFrame:
    """Frame raw sintético com aliases reais da ANP."""
    return pd.DataFrame(
        [
            # Duplicata para SP/SAO PAULO/2024-01-01 -> deve virar média (5.00 e 6.00 -> 5.50)
            {
                "Estado - Sigla": "SP",
                "Municipio": "SAO PAULO",
                "Produto": "OLEO DIESEL S10",
                "Preco Medio Revenda": "5,00",
                "Data da Coleta": "01/01/2024",
            },
            {
                "Estado - Sigla": "SP",
                "Municipio": "SAO PAULO",
                "Produto": "OLEO DIESEL",
                "Preco Medio Revenda": "6,00",
                "Data da Coleta": "01/01/2024",
            },
            # Diesel em outra cidade/UF.
            {
                "Estado - Sigla": "RJ",
                "Municipio": "RIO DE JANEIRO",
                "Produto": "OLEO DIESEL S10",
                "Preco Medio Revenda": "5,50",
                "Data da Coleta": "01/01/2024",
            },
            # Gasolina -> deve ser filtrada.
            {
                "Estado - Sigla": "SP",
                "Municipio": "SAO PAULO",
                "Produto": "GASOLINA COMUM",
                "Preco Medio Revenda": "7,00",
                "Data da Coleta": "01/01/2024",
            },
            # Etanol -> deve ser filtrada.
            {
                "Estado - Sigla": "MG",
                "Municipio": "BELO HORIZONTE",
                "Produto": "ETANOL HIDRATADO",
                "Preco Medio Revenda": "4,00",
                "Data da Coleta": "01/01/2024",
            },
            # Diesel sem preço -> deve ser descartada.
            {
                "Estado - Sigla": "BA",
                "Municipio": "SALVADOR",
                "Produto": "OLEO DIESEL",
                "Preco Medio Revenda": "",
                "Data da Coleta": "01/01/2024",
            },
        ]
    )


def test_output_columns_and_dtypes() -> None:
    out = normalize(_raw_sample())

    assert list(out.columns) == EXPECTED_COLUMNS
    assert out["preco_medio"].dtype == "float64"
    # cada valor de data é um datetime.date puro
    assert all(isinstance(d, date) for d in out["data"])
    assert (out["fonte"] == "ANP").all()
    assert (out["uf"].str.len() == 2).all()


def test_duplicate_key_is_averaged() -> None:
    out = normalize(_raw_sample())

    sp = out[(out["uf"] == "SP") & (out["cidade"] == "SAO PAULO")]
    # Uma única linha por (data, uf, cidade) após o group/average.
    assert len(sp) == 1
    assert sp.iloc[0]["preco_medio"] == 5.5


def test_gasoline_and_ethanol_are_dropped() -> None:
    out = normalize(_raw_sample())

    # Nenhum produto não-diesel sobrevive. MG só tinha etanol -> some.
    assert "MG" not in set(out["uf"])
    # BA só tinha diesel sem preço -> descartado.
    assert "BA" not in set(out["uf"])
    # Restam apenas as chaves de diesel válidas: SP (agregado) e RJ.
    assert set(out["uf"]) == {"SP", "RJ"}
    assert len(out) == 2


def test_empty_input_returns_empty_schema() -> None:
    out = normalize(pd.DataFrame())

    assert list(out.columns) == EXPECTED_COLUMNS
    assert len(out) == 0
