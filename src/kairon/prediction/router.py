"""Router FastAPI do context prediction: POST /v1/predict."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.database import get_session
from kairon.prediction import ranking, service
from kairon.prediction.schemas import (
    PredictRequest,
    PredictResponse,
    RouteHistoryResponse,
    RouteRankingItem,
)
from kairon.tenant.auth import Principal, get_principal, require_role

router = APIRouter()

# Guard de RBAC como singleton de módulo (evita chamada em default de argumento).
_predict_guard = require_role("admin", "analyst")


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
    # RBAC (US-006): admin/analyst preveem; viewer só lê ranking. Anônimo = admin (MVP).
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
    principal: Principal = Depends(get_principal),
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
    principal: Principal = Depends(get_principal),
) -> RouteHistoryResponse:
    return await ranking.route_history(
        session, route_id, tenant_id=principal.tenant_id, months=months
    )
