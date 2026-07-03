"""Ranking de rotas (US-034/036) e histórico de rota (US-018).

Reusa o pipeline de predição (baseline + LightGBM residual + quantile) para
calcular, por rota: frete atual, banda, R$/t·km e variação vs 30 dias atrás.

Nota honesta: `var_30d` compara duas AVALIAÇÕES do modelo (hoje vs 30d atrás),
não observações reais. `mape` fica None no MVP — MAPE real depende do monitor
previsto/realizado (US-094), ainda não implementado. Não inventamos número.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.logging import get_logger
from kairon.prediction.db_models import Route
from kairon.prediction.features import (
    DEFAULT_DIESEL_PRICE_BRL_PER_L,
    DEFAULT_PISO_ANTT_BRL_PER_TON,
    build_features,
)
from kairon.prediction.models.baseline import predict_baseline
from kairon.prediction.schemas import RouteHistoryPoint, RouteHistoryResponse, RouteRankingItem
from kairon.prediction.service import _latest_diesel_price, _load_models, _parse_uf

log = get_logger(__name__)


def _point_and_band(fv, residual_model, quantile_model) -> tuple[float, float, float]:  # type: ignore[no-untyped-def]
    baseline = predict_baseline(fv)
    point = round(baseline.frete_r_per_ton + residual_model.predict_residual(fv), 2)
    p10, p90 = quantile_model.predict_band(fv, point)
    return point, p10, p90


def _sub_months(d: date, months: int) -> date:
    """Primeiro dia do mês, `months` meses antes de `d` (sem libs externas)."""
    total = (d.year * 12 + (d.month - 1)) - months
    return date(total // 12, total % 12 + 1, 1)


async def _diesel_for(session: AsyncSession, origem: str) -> float:
    diesel = await _latest_diesel_price(session, _parse_uf(origem))
    return diesel if diesel is not None else DEFAULT_DIESEL_PRICE_BRL_PER_L


async def _latest_diesel_by_uf(session: AsyncSession) -> dict[str, float]:
    """Preço de diesel mais recente por UF em UMA query (evita N+1 no ranking).

    O ranking avalia dezenas de rotas; buscar o diesel por rota gera uma query
    remota por rota. Aqui trazemos tudo ordenado por data e ficamos com o mais
    recente de cada UF — um único round-trip.
    """
    from kairon.ingestion.anp.models import RawDieselPrice

    rows = (
        await session.execute(
            select(RawDieselPrice.uf, RawDieselPrice.preco_medio).order_by(
                RawDieselPrice.data.desc()
            )
        )
    ).all()
    latest: dict[str, float] = {}
    for uf, preco in rows:
        if uf not in latest:  # primeira ocorrência = data mais recente (order by desc)
            latest[uf] = preco
    return latest


def _piso(route: Route) -> float:
    return (
        route.piso_antt_r_per_ton
        if route.piso_antt_r_per_ton is not None
        else DEFAULT_PISO_ANTT_BRL_PER_TON
    )


async def rank_routes(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    produto: str | None = None,
    corredor: str | None = None,
) -> list[RouteRankingItem]:
    stmt = select(Route).where(Route.tenant_id == tenant_id)  # isolamento por tenant (US-004)
    if produto:
        stmt = stmt.where(Route.produto.ilike(produto))
    if corredor:
        stmt = stmt.where(Route.corredor.ilike(corredor))
    routes = (await session.execute(stmt)).scalars().all()

    residual_model, quantile_model = _load_models()
    today = datetime.now().date()
    d30 = today - timedelta(days=30)
    # Pré-busca o diesel de todas as UFs numa query só (evita N+1 no loop).
    diesel_by_uf = await _latest_diesel_by_uf(session)

    items: list[RouteRankingItem] = []
    for route in routes:
        uf = _parse_uf(route.origem)
        diesel = diesel_by_uf.get(uf) if uf else None
        diesel = diesel if diesel is not None else DEFAULT_DIESEL_PRICE_BRL_PER_L
        piso = _piso(route)
        fv_now = build_features(
            distancia_km=route.distancia_km,
            produto=route.produto,
            target_date=today,
            diesel_price=diesel,
            piso_antt=piso,
            origem=route.origem,
            destino=route.destino,
        )
        fv_30 = build_features(
            distancia_km=route.distancia_km,
            produto=route.produto,
            target_date=d30,
            diesel_price=diesel,
            piso_antt=piso,
            origem=route.origem,
            destino=route.destino,
        )
        point, p10, p90 = _point_and_band(fv_now, residual_model, quantile_model)
        point_30, _, _ = _point_and_band(fv_30, residual_model, quantile_model)
        var_30d = round((point - point_30) / point_30 * 100, 2) if point_30 else 0.0

        items.append(
            RouteRankingItem(
                route_id=str(route.id),
                origem=route.origem,
                destino=route.destino,
                produto=route.produto,
                corredor=route.corredor,
                distancia_km=route.distancia_km,
                frete_r_per_ton=point,
                r_per_ton_km=round(point / route.distancia_km, 3) if route.distancia_km else 0.0,
                banda_p10=p10,
                banda_p90=p90,
                var_30d_pct=var_30d,
                mape=None,  # US-094: monitor previsto vs realizado ainda não implementado
            )
        )

    # Ranking padrão: frete decrescente (rotas mais caras primeiro).
    items.sort(key=lambda i: i.frete_r_per_ton, reverse=True)
    return items


async def route_history(
    session: AsyncSession, route_id: str, *, tenant_id: uuid.UUID, months: int = 12
) -> RouteHistoryResponse:
    from kairon.core.exceptions import NotFoundError

    try:
        rid = uuid.UUID(route_id)
    except ValueError as exc:
        raise NotFoundError("route_id inválido") from exc

    # Filtra por tenant: rota de outro tenant retorna 404 (não vaza existência).
    route = (
        (await session.execute(select(Route).where(Route.id == rid, Route.tenant_id == tenant_id)))
        .scalars()
        .first()
    )
    if route is None:
        raise NotFoundError(f"rota {route_id} não encontrada")

    residual_model, quantile_model = _load_models()
    diesel = await _diesel_for(session, route.origem)
    piso = _piso(route)
    today = datetime.now().date()

    points: list[RouteHistoryPoint] = []
    for i in range(months - 1, -1, -1):
        month_start = _sub_months(today.replace(day=1), i)
        fv = build_features(
            distancia_km=route.distancia_km,
            produto=route.produto,
            target_date=month_start,
            diesel_price=diesel,
            piso_antt=piso,
            origem=route.origem,
            destino=route.destino,
        )
        point, p10, p90 = _point_and_band(fv, residual_model, quantile_model)
        points.append(
            RouteHistoryPoint(
                month=month_start.strftime("%Y-%m"),
                frete_r_per_ton=point,
                banda_p10=p10,
                banda_p90=p90,
            )
        )

    return RouteHistoryResponse(
        route_id=route_id,
        origem=route.origem,
        destino=route.destino,
        produto=route.produto,
        points=points,
        note="Série implícita pelo modelo (baseline + LightGBM), não observações reais.",
    )
