"""Feature engineering: transforma um pedido de cotação num vetor de features.

Mantido deliberadamente simples e explícito (manutenibilidade > sofisticação).
As MESMAS features alimentam baseline, LightGBM e SHAP — fonte única.
"""

from __future__ import annotations

import hashlib
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
    # Efeito de corredor/lane (backhaul, concorrência, qualidade da via). Multiplica
    # o baseline. Fora do vetor do LightGBM (não faz parte de as_row) — é um ajuste
    # de mercado por lane. No dev é sintético (derivado do par origem/destino); com
    # dados reais, o efeito de lane passa a ser aprendido pelo modelo.
    lane_factor: float = 1.0

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


def lane_factor(origem: str | None, destino: str | None, produto: str, month: int) -> float:
    """Fator de mercado por lane (backhaul/concorrência/via), estável por rota.

    Determinístico a partir do par origem→destino+produto: uma base fixa por lane
    (± ~11%) mais uma leve fase sazonal **própria de cada lane** — assim a variação
    mês-a-mês difere entre rotas (do contrário todo o ranking teria o mesmo var_30d,
    pois a sazonalidade global é idêntica). Sintético no dev; aprendido com dado real.
    """
    if not origem or not destino:
        return 1.0
    key = f"{origem}|{destino}|{produto}".strip().lower()
    h = int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16)
    base = 0.90 + (h % 1000) / 1000 * 0.22  # [0.90, 1.12)
    phase = h % 12  # fase sazonal própria da lane
    seasonal = 1.0 + 0.035 * math.sin(2 * math.pi * (month + phase) / 12.0)  # ±3,5%
    return round(base * seasonal, 4)


def build_features(
    *,
    distancia_km: float,
    produto: str,
    target_date: date,
    diesel_price: float | None = None,
    piso_antt: float | None = None,
    origem: str | None = None,
    destino: str | None = None,
) -> FeatureVector:
    month = target_date.month
    return FeatureVector(
        distancia_km=distancia_km,
        diesel_price=diesel_price if diesel_price is not None else DEFAULT_DIESEL_PRICE_BRL_PER_L,
        piso_antt=piso_antt if piso_antt is not None else DEFAULT_PISO_ANTT_BRL_PER_TON,
        seasonality=SEASONALITY.get(month, 1.0),
        month=month,
        produto_is_fertilizante=1 if produto.strip().lower() in _FERTILIZANTES else 0,
        lane_factor=lane_factor(origem, destino, produto, month),
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância aproximada em km (fallback quando a rota não tem distancia_km)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))
