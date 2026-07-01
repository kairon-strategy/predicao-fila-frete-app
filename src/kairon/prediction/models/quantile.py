"""Banda de incerteza via LightGBM quantile regression (α=0.1 e α=0.9).

Dá o p10/p90 do frete. Sem modelo treinado, cai num fallback heurístico:
±12% em torno do ponto — banda plausível para o MVP não retornar banda vazia.
"""

from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np

from kairon.core.logging import get_logger
from kairon.prediction.features import FeatureVector

log = get_logger(__name__)

FALLBACK_BAND_PCT = 0.12  # ±12% quando não há modelo de quantil treinado


class QuantileBands:
    def __init__(self) -> None:
        self._low: lgb.Booster | None = None
        self._high: lgb.Booster | None = None

    @property
    def is_ready(self) -> bool:
        return self._low is not None and self._high is not None

    def train(self, x: np.ndarray, y: np.ndarray) -> None:
        """Treina dois boosters de quantil sobre o frete observado."""
        self._low = self._train_one(x, y, alpha=0.1)
        self._high = self._train_one(x, y, alpha=0.9)
        log.info("quantile.trained", n_samples=int(x.shape[0]))

    @staticmethod
    def _train_one(x: np.ndarray, y: np.ndarray, alpha: float) -> lgb.Booster:
        dataset = lgb.Dataset(x, label=y, feature_name=FeatureVector.feature_names())
        params = {
            "objective": "quantile",
            "alpha": alpha,
            "num_leaves": 31,
            "learning_rate": 0.05,
            "verbose": -1,
        }
        return lgb.train(params, dataset, num_boost_round=200)

    def predict_band(self, fv: FeatureVector, point_estimate: float) -> tuple[float, float]:
        """Retorna (p10, p90). Usa modelo se treinado; senão fallback ±%."""
        if self._low is None or self._high is None:
            low = point_estimate * (1 - FALLBACK_BAND_PCT)
            high = point_estimate * (1 + FALLBACK_BAND_PCT)
            return round(low, 2), round(high, 2)

        row = np.array([fv.as_row()], dtype=float)
        low = float(self._low.predict(row)[0])
        high = float(self._high.predict(row)[0])
        # Garante ordenação e coerência com o ponto (quantis podem cruzar).
        low, high = min(low, high), max(low, high)
        low = min(low, point_estimate)
        high = max(high, point_estimate)
        return round(low, 2), round(high, 2)

    def save(self, dir_path: str | Path) -> None:
        if self._low is None or self._high is None:
            raise RuntimeError("nada a salvar: quantis não treinados")
        d = Path(dir_path)
        d.mkdir(parents=True, exist_ok=True)
        self._low.save_model(str(d / "quantile_low.txt"))
        self._high.save_model(str(d / "quantile_high.txt"))

    @classmethod
    def load(cls, dir_path: str | Path) -> QuantileBands:
        model = cls()
        d = Path(dir_path)
        low_p, high_p = d / "quantile_low.txt", d / "quantile_high.txt"
        if low_p.exists() and high_p.exists():
            model._low = lgb.Booster(model_file=str(low_p))
            model._high = lgb.Booster(model_file=str(high_p))
            log.info("quantile.loaded", path=str(d))
        return model
