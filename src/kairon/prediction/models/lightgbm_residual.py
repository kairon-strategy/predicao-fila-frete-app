"""LightGBM que prevê o RESÍDUO do baseline (actual - baseline).

Por que residual e não o frete direto? O baseline já captura ~90% do sinal
(distância·diesel·piso). O LightGBM só corrige o que o baseline erra —
modelo menor, mais estável, menos propenso a extrapolar besteira (ADR-004).

Sem artefato treinado, `predict_residual` retorna 0.0 -> a resposta = baseline puro.
"""

from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np

from kairon.core.logging import get_logger
from kairon.prediction.features import FeatureVector

log = get_logger(__name__)


class ResidualModel:
    def __init__(self) -> None:
        self._booster: lgb.Booster | None = None

    @property
    def is_ready(self) -> bool:
        return self._booster is not None

    def train(self, x: np.ndarray, residuals: np.ndarray) -> None:
        """Treina o corretor de resíduo. x: (n, n_features), residuals: (n,)."""
        dataset = lgb.Dataset(x, label=residuals, feature_name=FeatureVector.feature_names())
        params = {
            "objective": "regression",
            "metric": "l2",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "verbose": -1,
        }
        self._booster = lgb.train(params, dataset, num_boost_round=200)
        log.info("lightgbm_residual.trained", n_samples=int(x.shape[0]))

    def predict_residual(self, fv: FeatureVector) -> float:
        if self._booster is None:
            return 0.0
        row = np.array([fv.as_row()], dtype=float)
        return float(self._booster.predict(row)[0])

    def save(self, path: str | Path) -> None:
        if self._booster is None:
            raise RuntimeError("nada a salvar: modelo não treinado")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._booster.save_model(str(path))

    @classmethod
    def load(cls, path: str | Path) -> ResidualModel:
        model = cls()
        if Path(path).exists():
            model._booster = lgb.Booster(model_file=str(path))
            log.info("lightgbm_residual.loaded", path=str(path))
        return model

    @property
    def booster(self) -> lgb.Booster | None:
        """Exposto para o SHAP TreeExplainer."""
        return self._booster
