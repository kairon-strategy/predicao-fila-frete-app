"""Router FastAPI do context explanation: POST /v1/explain."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.config import settings
from kairon.core.database import get_session
from kairon.explanation import service
from kairon.explanation.schemas import ExplainRequest, ExplainResponse
from kairon.tenant import ratelimit
from kairon.tenant.auth import Principal, require_permission

router = APIRouter()

_explain_guard = require_permission("explain:run")


@router.post("/explain", response_model=ExplainResponse, summary="Explica uma predição (LLM)")
async def explain_endpoint(
    request: ExplainRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_explain_guard),
) -> ExplainResponse:
    # Rate limit por tenant: protege o custo do LLM contra abuso (ver §7).
    rl_key = f"explain:{principal.tenant_id}"
    if not ratelimit.hit(rl_key, max_attempts=settings.explain_max_per_min, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="limite de explicações por minuto atingido; tente novamente em instantes",
            headers={"Retry-After": "60"},
        )
    return await service.explain(
        session, request.prediction_id, question=request.question, tenant_id=principal.tenant_id
    )
