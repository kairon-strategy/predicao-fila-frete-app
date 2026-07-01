"""Feature engineering: transforma um pedido de cotação num vetor de features.

Mantido deliberadamente simples e explícito (manutenibilidade > sofisticação).
As MESMAS features alimentam baseline, LightGBM e SHAP — fonte única.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date

# Fator de sazonalidade por mês (1.0 = neutro). Safra/entressafra do agro:
# pico de demanda de frete no 1º tri (escoamento soja/milho) e 3º tri (2ª safra).
SEASONALITY: dict[int, float] = {
    1: 1.12,
    2: 1.15,
    3: 1.18,
    4: 1.05,
    5: 0.98,
    6: 0.95,
    7: 1.02,
    8: 1.10,
    9: 1.08,
    10: 1.00,
    11: 0.97,
    12: 1.03,
}

# Defaults usados quando não há dado externo (ex: ANP ainda não populada).
DEFAULT_DIESEL_PRICE_BRL_PER_L = 6.20
DEFAULT_PISO_ANTT_BRL_PER_TON = 90.0


@dataclass(frozen=True)
class FeatureVector:
    """Features numéricas de uma cotação. Ordem estável -> usada pelo LightGBM."""

    distancia_km: float
    diesel_price: float
    piso_antt: float
    seasonality: float
    month: int
    produto_is_fertilizante: int  # 1 fertilizante, 0 caso contrário (ex: algodão)

    def as_row(self) -> list[float]:
        """Vetor ordenado para o modelo. NÃO reordene sem retreinar."""
        return [
            self.distancia_km,
            self.diesel_price,
            self.piso_antt,
            self.seasonality,
            float(self.month),
            float(self.produto_is_fertilizante),
        ]

    @staticmethod
    def feature_names() -> list[str]:
        return [
            "distancia_km",
            "diesel_price",
            "piso_antt",
            "seasonality",
            "month",
            "produto_is_fertilizante",
        ]

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


_FERTILIZANTES = {"ureia", "map", "kcl", "cloreto", "npk", "fertilizante", "nitrato"}


def build_features(
    *,
    distancia_km: float,
    produto: str,
    target_date: date,
    diesel_price: float | None = None,
    piso_antt: float | None = None,
) -> FeatureVector:
    month = target_date.month
    return FeatureVector(
        distancia_km=distancia_km,
        diesel_price=diesel_price if diesel_price is not None else DEFAULT_DIESEL_PRICE_BRL_PER_L,
        piso_antt=piso_antt if piso_antt is not None else DEFAULT_PISO_ANTT_BRL_PER_TON,
        seasonality=SEASONALITY.get(month, 1.0),
        month=month,
        produto_is_fertilizante=1 if produto.strip().lower() in _FERTILIZANTES else 0,
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância aproximada em km (fallback quando a rota não tem distancia_km)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))
