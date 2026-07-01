"""Treina o modelo de resíduo (LightGBM) + bandas de quantil a partir do CSV sintético.

Fluxo:
  1. Carrega data/synthetic/routes_daily_prices.csv (rode o seed antes se faltar).
  2. Por linha: build_features -> predict_baseline -> residual = actual - baseline.
  3. Treina ResidualModel sobre (X, residuals)  -> models_store/residual.txt
     Treina QuantileBands sobre (X, actual)     -> models_store/quantile_{low,high}.txt
  4. Imprime MAPE in-sample de (baseline + residual) vs actual.

models_store/ é gitignored (artefatos regeráveis).

Uso:
    poetry run python scripts/train_baseline_model.py
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

import numpy as np

from kairon.prediction.features import build_features
from kairon.prediction.models.baseline import predict_baseline
from kairon.prediction.models.lightgbm_residual import ResidualModel
from kairon.prediction.models.quantile import QuantileBands

CSV_PATH = Path("data/synthetic/routes_daily_prices.csv")
MODELS_DIR = Path("models_store")
RESIDUAL_PATH = MODELS_DIR / "residual.txt"


def _load_dataset() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Retorna (X, residuals, actual_prices) a partir do CSV sintético."""
    if not CSV_PATH.exists():
        print(
            f"ERRO: {CSV_PATH} não encontrado.\n"
            "Rode o seed primeiro:\n"
            "    poetry run python scripts/seed_synthetic_data.py",
            file=sys.stderr,
        )
        raise SystemExit(1)

    rows_x: list[list[float]] = []
    residuals: list[float] = []
    actuals: list[float] = []

    with CSV_PATH.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            distancia_km = float(row["distancia_km"])
            produto = row["produto"]
            diesel_lag30 = float(row["diesel_lag30"])
            actual = float(row["preco_r_por_ton"])
            target_date = date.fromisoformat(row["date"])

            fv = build_features(
                distancia_km=distancia_km,
                produto=produto,
                target_date=target_date,
                diesel_price=diesel_lag30,
                piso_antt=None,
            )
            baseline = predict_baseline(fv)

            rows_x.append(fv.as_row())
            residuals.append(actual - baseline.frete_r_per_ton)
            actuals.append(actual)

    x = np.array(rows_x, dtype=float)
    return x, np.array(residuals, dtype=float), np.array(actuals, dtype=float)


def _in_sample_mape(x: np.ndarray, actuals: np.ndarray, model: ResidualModel) -> float:
    """MAPE de (baseline + residual previsto) vs actual, in-sample."""
    # baseline por linha, reconstruído a partir de X (mesma ordem de features).
    from kairon.prediction.features import FeatureVector

    baselines = np.array(
        [
            predict_baseline(
                FeatureVector(
                    distancia_km=r[0],
                    diesel_price=r[1],
                    piso_antt=r[2],
                    seasonality=r[3],
                    month=int(r[4]),
                    produto_is_fertilizante=int(r[5]),
                )
            ).frete_r_per_ton
            for r in x
        ],
        dtype=float,
    )
    predicted_residuals = np.array(model.booster.predict(x), dtype=float)
    predicted = baselines + predicted_residuals
    return float(np.mean(np.abs((actuals - predicted) / actuals)) * 100.0)


def main() -> None:
    print(f"[train] carregando {CSV_PATH} ...")
    x, residuals, actuals = _load_dataset()
    print(f"[train] {x.shape[0]} amostras, {x.shape[1]} features")

    print("[train] treinando ResidualModel (LightGBM) ...")
    residual_model = ResidualModel()
    residual_model.train(x, residuals)
    residual_model.save(RESIDUAL_PATH)
    print(f"[train] salvo: {RESIDUAL_PATH}")

    print("[train] treinando QuantileBands (p10/p90) ...")
    quantile = QuantileBands()
    quantile.train(x, actuals)
    quantile.save(MODELS_DIR)
    print(
        f"[train] salvo: {MODELS_DIR / 'quantile_low.txt'}, " f"{MODELS_DIR / 'quantile_high.txt'}"
    )

    mape = _in_sample_mape(x, actuals, residual_model)
    print(f"[train] MAPE in-sample (baseline+residual vs actual): {mape:.2f}%")
    print(f"[train] RESUMO: artefatos em {MODELS_DIR}/ (gitignored), MAPE={mape:.2f}%")


if __name__ == "__main__":
    main()
