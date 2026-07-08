"""Router FastAPI do context explanation: POST /v1/explain."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.database import get_session
from kairon.explanation import service
from kairon.explanation.schemas import ExplainRequest, ExplainResponse
from kairon.tenant.auth import Principal, require_permission

router = APIRouter()

_explain_guard = require_permission("explain:run")


@router.post("/explain", response_model=ExplainResponse, summary="Explica uma predição (Claude)")
async def explain_endpoint(
    request: ExplainRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_explain_guard),
) -> ExplainResponse:
    return await service.explain(
        session, request.prediction_id, question=request.question, tenant_id=principal.tenant_id
    )
