"""Schemas Pydantic do endpoint /v1/predict (request + response)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PredictRequest(BaseModel):
    origem: str = Field(..., examples=["Sinop-MT"], min_length=2, max_length=120)
    destino: str = Field(..., examples=["Sorriso-MT"], min_length=2, max_length=120)
    produto: str = Field(..., examples=["ureia"], min_length=2, max_length=60)
    data: date = Field(..., description="Data alvo da cotação", examples=["2026-08-15"])
    carga_ton: float | None = Field(default=None, gt=0, examples=[30])
    # Override de mercado: se enviado (ex: slider de diesel), sobrepõe o preço da ANP.
    diesel_price: float | None = Field(default=None, gt=0, examples=[6.20])

    @field_validator("origem", "destino", "produto")
    @classmethod
    def strip_and_lower_noise(cls, v: str) -> str:
        # Sanitização básica de input livre (seção 8: anti prompt-injection).
        return v.strip()


class Driver(BaseModel):
    """Um driver explicativo da predição (top-5 por |SHAP|)."""

    feature: str = Field(..., examples=["diesel_lag30"])
    shap_value: float = Field(..., examples=[12.4])
    direction: Literal["up", "down"] = Field(..., description="empurra o frete para cima/baixo")


class PredictResponse(BaseModel):
    # model_version colide com o namespace protegido "model_" do Pydantic; liberamos.
    model_config = ConfigDict(protected_namespaces=())

    prediction_id: str
    frete_r_per_ton: float = Field(..., description="Frete estimado em R$/tonelada")
    banda_p10: float = Field(..., description="Piso da banda (quantil 10%)")
    banda_p90: float = Field(..., description="Teto da banda (quantil 90%)")
    drivers: list[Driver]
    model_version: str


class RouteRankingItem(BaseModel):
    """Uma linha do ranking de rotas (US-034)."""

    route_id: str
    origem: str
    destino: str
    produto: str
    corredor: str | None
    distancia_km: float
    frete_r_per_ton: float
    r_per_ton_km: float
    banda_p10: float
    banda_p90: float
    var_30d_pct: float = Field(..., description="Variação vs 30d atrás (avaliações do modelo)")
    mape: float | None = Field(default=None, description="None no MVP (ver US-094)")


class RouteHistoryPoint(BaseModel):
    month: str = Field(..., examples=["2026-07"])
    frete_r_per_ton: float
    banda_p10: float
    banda_p90: float


class RouteHistoryResponse(BaseModel):
    route_id: str
    origem: str
    destino: str
    produto: str
    points: list[RouteHistoryPoint]
    note: str
