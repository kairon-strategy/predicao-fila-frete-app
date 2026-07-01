"""Testes unitários do baseline e features (puros, sem DB)."""

from __future__ import annotations

from datetime import date

from kairon.prediction import shap_explainer
from kairon.prediction.features import SEASONALITY, FeatureVector, build_features
from kairon.prediction.models.baseline import predict_baseline
from kairon.prediction.models.lightgbm_residual import ResidualModel
from kairon.prediction.models.quantile import QuantileBands


def _fv(distancia_km: float = 300.0, produto: str = "ureia") -> FeatureVector:
    return build_features(
        distancia_km=distancia_km,
        produto=produto,
        target_date=date(2026, 8, 15),
        diesel_price=6.20,
        piso_antt=90.0,
    )


def test_baseline_scales_with_distance() -> None:
    curta = predict_baseline(_fv(distancia_km=100))
    longa = predict_baseline(_fv(distancia_km=1000))
    assert longa.frete_r_per_ton > curta.frete_r_per_ton


def test_baseline_respeita_piso_antt() -> None:
    # Distância minúscula -> fórmula abaixo do piso -> piso prevalece.
    res = predict_baseline(_fv(distancia_km=1))
    assert res.piso_aplicado is True
    assert res.frete_r_per_ton == 90.0


def test_seasonality_afeta_frete() -> None:
    jan = build_features(distancia_km=500, produto="ureia", target_date=date(2026, 3, 1))
    mai = build_features(distancia_km=500, produto="ureia", target_date=date(2026, 6, 1))
    assert SEASONALITY[3] > SEASONALITY[6]
    assert predict_baseline(jan).frete_r_per_ton > predict_baseline(mai).frete_r_per_ton


def test_fertilizante_flag() -> None:
    assert _fv(produto="ureia").produto_is_fertilizante == 1
    assert _fv(produto="algodao").produto_is_fertilizante == 0


def test_residual_zero_sem_modelo() -> None:
    model = ResidualModel()
    assert model.is_ready is False
    assert model.predict_residual(_fv()) == 0.0


def test_quantile_fallback_band() -> None:
    bands = QuantileBands()
    p10, p90 = bands.predict_band(_fv(), point_estimate=100.0)
    assert p10 < 100.0 < p90


def test_synthetic_drivers_top5() -> None:
    fv = _fv()
    baseline = predict_baseline(fv)
    drivers = shap_explainer.explain(fv, baseline, ResidualModel())
    assert 1 <= len(drivers) <= 5
    assert all(d["direction"] in ("up", "down") for d in drivers)
    # ordenado por |shap_value| desc
    vals = [abs(d["shap_value"]) for d in drivers]
    assert vals == sorted(vals, reverse=True)
