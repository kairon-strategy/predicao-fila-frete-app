"""Router FastAPI do context prediction: POST /v1/predict."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.database import get_session
from kairon.prediction import ranking, routes_crud, service
from kairon.prediction.schemas import (
    PredictRequest,
    PredictResponse,
    RouteHistoryResponse,
    RouteRankingItem,
    RouteResponse,
    RouteWrite,
)
from kairon.tenant.auth import Principal, require_permission

router = APIRouter()

# Guards de RBAC por permissão (singletons de módulo).
_predict_guard = require_permission("predict:run")
_write_guard = require_permission("routes:write")
_read_guard = require_permission("routes:read")


@router.post("/predict", response_model=PredictResponse, summary="Prevê frete R$/tonelada")
async def predict_endpoint(
    request: PredictRequest,
    idempotency_key: str = Header(
        ...,
        alias="idempotency-key",
        description="Chave obrigatória: mesma chave -> mesma predição (idempotência).",
        min_length=1,
        max_length=128,
    ),
    session: AsyncSession = Depends(get_session),
    # RBAC dinâmico: exige a permissão predict:run (perfil configurável por tenant).
    principal: Principal = Depends(_predict_guard),
) -> PredictResponse:
    return await service.predict(
        session, request, idempotency_key=idempotency_key, tenant_id=principal.tenant_id
    )


@router.get("/routes", response_model=list[RouteRankingItem], summary="Ranking de rotas")
async def list_routes(
    produto: str | None = Query(default=None, description="Filtra por produto"),
    corredor: str | None = Query(default=None, description="Filtra por corredor"),
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_read_guard),
) -> list[RouteRankingItem]:
    return await ranking.rank_routes(
        session, tenant_id=principal.tenant_id, produto=produto, corredor=corredor
    )


@router.get(
    "/routes/{route_id}/history",
    response_model=RouteHistoryResponse,
    summary="Histórico (12m) implícito pelo modelo",
)
async def route_history(
    route_id: str,
    months: int = Query(default=12, ge=1, le=36),
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_read_guard),
) -> RouteHistoryResponse:
    return await ranking.route_history(
        session, route_id, tenant_id=principal.tenant_id, months=months
    )


# ---- CRUD de rotas (gestão) ----
@router.get("/routes/manage", response_model=list[RouteResponse], summary="Lista rotas (gestão)")
async def manage_list_routes(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_read_guard),
) -> list[RouteResponse]:
    return await routes_crud.list_routes(session, principal.tenant_id)


@router.post(
    "/routes", response_model=RouteResponse, status_code=201, summary="Cria rota (admin/analyst)"
)
async def create_route(
    body: RouteWrite,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_write_guard),
) -> RouteResponse:
    return await routes_crud.create_route(session, principal.tenant_id, body)


@router.put(
    "/routes/{route_id}", response_model=RouteResponse, summary="Edita rota (admin/analyst)"
)
async def update_route(
    route_id: uuid.UUID,
    body: RouteWrite,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_write_guard),
) -> RouteResponse:
    return await routes_crud.update_route(session, principal.tenant_id, route_id, body)


@router.delete("/routes/{route_id}", status_code=204, summary="Exclui rota (admin/analyst)")
async def delete_route(
    route_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_write_guard),
) -> Response:
    await routes_crud.delete_route(session, principal.tenant_id, route_id)
    return Response(status_code=204)
