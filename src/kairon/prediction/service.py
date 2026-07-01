"""Orquestra a predição: route+diesel -> features -> baseline -> LightGBM -> quantile -> SHAP.

Regras de robustez (manutenibilidade > sofisticação):
- Sem modelo treinado, a resposta = baseline + banda heurística + drivers sintéticos.
- Idempotência é checada explicitamente por idempotency_key (não depende de NULL semantics).
- Toda predição é persistida (source of truth) e um evento é publicado (audit/v2).
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.config import settings
from kairon.core.logging import get_logger
from kairon.prediction import shap_explainer
from kairon.prediction.db_models import Prediction, Route
from kairon.prediction.features import (
    DEFAULT_DIESEL_PRICE_BRL_PER_L,
    DEFAULT_PISO_ANTT_BRL_PER_TON,
    build_features,
)
from kairon.prediction.models.baseline import predict_baseline
from kairon.prediction.models.lightgbm_residual import ResidualModel
from kairon.prediction.models.quantile import QuantileBands
from kairon.prediction.schemas import Driver, PredictRequest, PredictResponse

log = get_logger(__name__)

MODELS_DIR = Path("models_store")
DEFAULT_DISTANCE_KM = 300.0  # fallback quando a rota não está cadastrada


@lru_cache
def _load_models() -> tuple[ResidualModel, QuantileBands]:
    """Carrega artefatos uma vez (cacheado). Ausência -> modelos "vazios" (fallback)."""
    residual = ResidualModel.load(MODELS_DIR / "residual.txt")
    quantile = QuantileBands.load(MODELS_DIR)
    if not residual.is_ready:
        log.warning("prediction.models_absent", detail="usando baseline + banda heurística")
    return residual, quantile


def _parse_uf(local: str) -> str | None:
    """Extrai a UF de um rótulo tipo 'Sinop-MT'. Retorna None se não achar."""
    if "-" in local:
        candidate = local.rsplit("-", 1)[-1].strip().upper()
        if len(candidate) == 2 and candidate.isalpha():
            return candidate
    return None


async def _lookup_route(
    session: AsyncSession, origem: str, destino: str, produto: str
) -> Route | None:
    stmt = select(Route).where(
        Route.origem.ilike(origem),
        Route.destino.ilike(destino),
        Route.produto.ilike(produto),
    )
    return (await session.execute(stmt)).scalars().first()


async def _latest_diesel_price(session: AsyncSession, uf: str | None) -> float | None:
    if uf is None:
        return None
    # Import local: raw_diesel_prices pertence ao context ingestion.
    from kairon.ingestion.anp.models import RawDieselPrice

    stmt = (
        select(RawDieselPrice.preco_medio)
        .where(RawDieselPrice.uf == uf)
        .order_by(RawDieselPrice.data.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def predict(
    session: AsyncSession,
    request: PredictRequest,
    idempotency_key: str,
    tenant_id: uuid.UUID | None = None,
) -> PredictResponse:
    # ---- idempotência: já existe predição com essa chave NESTE tenant? ----
    # Escopo por tenant evita colisão de chave entre tenants distintos (US-004).
    existing = (
        (
            await session.execute(
                select(Prediction).where(
                    Prediction.idempotency_key == idempotency_key,
                    Prediction.tenant_id == tenant_id,
                )
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        log.info("prediction.idempotent_hit", idempotency_key=idempotency_key)
        return _to_response(existing)

    # ---- contexto: rota + diesel ----
    route = await _lookup_route(session, request.origem, request.destino, request.produto)
    distancia_km = route.distancia_km if route else DEFAULT_DISTANCE_KM
    piso_antt = (
        route.piso_antt_r_per_ton
        if route and route.piso_antt_r_per_ton is not None
        else DEFAULT_PISO_ANTT_BRL_PER_TON
    )
    if route is None:
        log.warning(
            "prediction.route_not_found",
            origem=request.origem,
            destino=request.destino,
            fallback_km=DEFAULT_DISTANCE_KM,
        )

    if request.diesel_price is not None:
        diesel_price = request.diesel_price  # override de mercado (slider da UI)
    else:
        diesel = await _latest_diesel_price(session, _parse_uf(request.origem))
        diesel_price = diesel if diesel is not None else DEFAULT_DIESEL_PRICE_BRL_PER_L

    # ---- pipeline de modelo ----
    fv = build_features(
        distancia_km=distancia_km,
        produto=request.produto,
        target_date=request.data,
        diesel_price=diesel_price,
        piso_antt=piso_antt,
    )
    residual_model, quantile_model = _load_models()

    baseline = predict_baseline(fv)
    residual = residual_model.predict_residual(fv)
    point = round(baseline.frete_r_per_ton + residual, 2)
    p10, p90 = quantile_model.predict_band(fv, point)
    drivers = shap_explainer.explain(fv, baseline, residual_model)

    # ---- persiste (source of truth) ----
    record = Prediction(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
        origem=request.origem,
        destino=request.destino,
        produto=request.produto,
        data_alvo=request.data,
        carga_ton=request.carga_ton,
        frete_r_per_ton=point,
        banda_p10=p10,
        banda_p90=p90,
        drivers=drivers,
        model_version=settings.model_version,
    )
    session.add(record)
    await session.flush()  # garante record.id preenchido

    log.info(
        "prediction.created",
        prediction_id=str(record.id),
        frete_r_per_ton=point,
        model_version=settings.model_version,
    )
    return _to_response(record)


def _to_response(record: Prediction) -> PredictResponse:
    return PredictResponse(
        prediction_id=str(record.id),
        frete_r_per_ton=record.frete_r_per_ton,
        banda_p10=record.banda_p10,
        banda_p90=record.banda_p90,
        drivers=[Driver(**d) for d in record.drivers],
        model_version=record.model_version,
    )
