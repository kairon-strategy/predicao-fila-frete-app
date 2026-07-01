"""Explicabilidade: top-5 drivers da predição.

Dois caminhos:
1. Modelo treinado -> SHAP TreeExplainer real sobre o LightGBM de resíduo.
2. Sem modelo -> drivers sintéticos derivados dos componentes do baseline
   (o "SHAP fake OK" da spec). Determinístico e sempre explicável.

Ambos retornam a mesma estrutura: [{feature, shap_value, direction}].
"""

from __future__ import annotations

from typing import Any

from kairon.core.logging import get_logger
from kairon.prediction.features import FeatureVector
from kairon.prediction.models.baseline import BaselineResult
from kairon.prediction.models.lightgbm_residual import ResidualModel

log = get_logger(__name__)

TOP_K = 5


def _direction(value: float) -> str:
    return "up" if value >= 0 else "down"


def explain(
    fv: FeatureVector,
    baseline: BaselineResult,
    residual_model: ResidualModel,
) -> list[dict[str, Any]]:
    if residual_model.is_ready and residual_model.booster is not None:
        try:
            return _shap_drivers(fv, residual_model)
        except Exception as exc:  # noqa: BLE001 — SHAP nunca deve derrubar a predição
            log.warning("shap.failed_fallback_synthetic", error=str(exc))
    return _synthetic_drivers(fv, baseline)


def _shap_drivers(fv: FeatureVector, residual_model: ResidualModel) -> list[dict[str, Any]]:
    import numpy as np
    import shap

    explainer = shap.TreeExplainer(residual_model.booster)
    row = np.array([fv.as_row()], dtype=float)
    shap_values = explainer.shap_values(row)[0]
    names = FeatureVector.feature_names()

    drivers: list[dict[str, Any]] = [
        {"feature": name, "shap_value": round(float(val), 4), "direction": _direction(float(val))}
        for name, val in zip(names, shap_values, strict=True)
    ]
    drivers.sort(key=lambda d: abs(d["shap_value"]), reverse=True)
    return drivers[:TOP_K]


def _synthetic_drivers(fv: FeatureVector, baseline: BaselineResult) -> list[dict[str, Any]]:
    """Drivers determinísticos a partir dos componentes do baseline."""
    seasonal_effect = (baseline.sazonalidade - 1.0) * (
        baseline.custo_combustivel + baseline.custo_operacional
    )
    raw: list[dict[str, Any]] = [
        {"feature": "custo_combustivel", "shap_value": baseline.custo_combustivel},
        {"feature": "custo_operacional_distancia", "shap_value": baseline.custo_operacional},
        {"feature": "sazonalidade", "shap_value": seasonal_effect},
        {
            "feature": "piso_antt",
            "shap_value": fv.piso_antt if baseline.piso_aplicado else 0.0,
        },
        {
            "feature": "produto_fertilizante",
            "shap_value": 3.0 if fv.produto_is_fertilizante else -3.0,
        },
    ]
    drivers: list[dict[str, Any]] = [
        {
            "feature": d["feature"],
            "shap_value": round(d["shap_value"], 4),
            "direction": _direction(d["shap_value"]),
        }
        for d in raw
    ]
    drivers.sort(key=lambda d: abs(d["shap_value"]), reverse=True)
    return drivers[:TOP_K]
