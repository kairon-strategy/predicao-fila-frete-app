"""CRUD de rotas (gestão) — isolado por tenant. Lógica via API (ADR-012)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.exceptions import NotFoundError
from kairon.core.logging import get_logger
from kairon.prediction.db_models import Route
from kairon.prediction.schemas import RouteResponse, RouteWrite

log = get_logger(__name__)


def _to_response(r: Route) -> RouteResponse:
    return RouteResponse(
        route_id=str(r.id),
        origem=r.origem,
        destino=r.destino,
        produto=r.produto,
        distancia_km=r.distancia_km,
        corredor=r.corredor,
        piso_antt_r_per_ton=r.piso_antt_r_per_ton,
    )


async def list_routes(session: AsyncSession, tenant_id: uuid.UUID) -> list[RouteResponse]:
    stmt = select(Route).where(Route.tenant_id == tenant_id).order_by(Route.origem, Route.destino)
    routes = (await session.execute(stmt)).scalars().all()
    return [_to_response(r) for r in routes]


async def create_route(
    session: AsyncSession, tenant_id: uuid.UUID, data: RouteWrite
) -> RouteResponse:
    route = Route(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        origem=data.origem.strip(),
        destino=data.destino.strip(),
        produto=data.produto.strip(),
        distancia_km=data.distancia_km,
        corredor=data.corredor.strip() if data.corredor else None,
        piso_antt_r_per_ton=data.piso_antt_r_per_ton,
    )
    session.add(route)
    await session.flush()
    log.info("route.created", tenant_id=str(tenant_id), route_id=str(route.id))
    return _to_response(route)


async def _get(session: AsyncSession, tenant_id: uuid.UUID, route_id: uuid.UUID) -> Route:
    route = (
        (
            await session.execute(
                select(Route).where(Route.id == route_id, Route.tenant_id == tenant_id)
            )
        )
        .scalars()
        .first()
    )
    if route is None:
        raise NotFoundError("rota não encontrada")
    return route


async def update_route(
    session: AsyncSession, tenant_id: uuid.UUID, route_id: uuid.UUID, data: RouteWrite
) -> RouteResponse:
    route = await _get(session, tenant_id, route_id)
    route.origem = data.origem.strip()
    route.destino = data.destino.strip()
    route.produto = data.produto.strip()
    route.distancia_km = data.distancia_km
    route.corredor = data.corredor.strip() if data.corredor else None
    route.piso_antt_r_per_ton = data.piso_antt_r_per_ton
    await session.flush()
    log.info("route.updated", tenant_id=str(tenant_id), route_id=str(route_id))
    return _to_response(route)


async def delete_route(session: AsyncSession, tenant_id: uuid.UUID, route_id: uuid.UUID) -> None:
    route = await _get(session, tenant_id, route_id)
    await session.delete(route)
    await session.flush()
    log.info("route.deleted", tenant_id=str(tenant_id), route_id=str(route_id))
