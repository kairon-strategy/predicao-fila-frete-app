"""Baseline determinístico de frete (R$/tonelada).

Sempre funciona — sem dependência de modelo treinado. É o piso de confiança:
se o LightGBM ou o SHAP falharem, a resposta ainda sai do baseline.

Fórmula (explícita de propósito):
    frete = (custo_combustivel + custo_operacional) * sazonalidade
    e nunca abaixo do piso ANTT.

Componentes retornados alimentam a explicação (drivers) quando não há SHAP real.
"""

from __future__ import annotations

from dataclasses import dataclass

from kairon.prediction.features import FeatureVector

# Consumo médio caminhão-graneleiro (L/km) e capacidade (t). Fonte: bibliografia ANTT.
CONSUMO_L_POR_KM = 0.40
CAPACIDADE_TON = 30.0
# Custo operacional R$/(t·km): pedágio, pneu, manutenção, motorista, margem.
CUSTO_OPERACIONAL_R_POR_TON_KM = 0.085


@dataclass(frozen=True)
class BaselineResult:
    frete_r_per_ton: float
    custo_combustivel: float
    custo_operacional: float
    sazonalidade: float
    piso_aplicado: bool  # True se o piso ANTT prevaleceu sobre a fórmula


def predict_baseline(fv: FeatureVector) -> BaselineResult:
    fuel = fv.distancia_km * (CONSUMO_L_POR_KM / CAPACIDADE_TON) * fv.diesel_price
    operating = fv.distancia_km * CUSTO_OPERACIONAL_R_POR_TON_KM
    # Sazonalidade global × efeito de corredor/lane (varia por rota).
    subtotal = (fuel + operating) * fv.seasonality * fv.lane_factor

    piso_aplicado = subtotal < fv.piso_antt
    frete = max(subtotal, fv.piso_antt)

    return BaselineResult(
        frete_r_per_ton=round(frete, 2),
        custo_combustivel=round(fuel, 2),
        custo_operacional=round(operating, 2),
        sazonalidade=fv.seasonality,
        piso_aplicado=piso_aplicado,
    )
