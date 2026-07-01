"""Router do context alerts: feed, resolução e disparo de detecção."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.alerts import service
from kairon.alerts.schemas import AlertResponse, DetectResponse
from kairon.core.database import get_session
from kairon.tenant.auth import Principal, get_principal, require_role

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Detecção é uma ação de escrita: admin/analyst apenas (US-006).
_detect_guard = require_role("admin", "analyst")


@router.get("", response_model=list[AlertResponse], summary="Feed de alertas do tenant (US-051)")
async def list_alerts(
    severity: str | None = Query(default=None, description="critical | warn | info"),
    alert_type: str | None = Query(default=None, alias="type"),
    status: str = Query(default="active", description="active | resolved"),
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> list[AlertResponse]:
    alerts = await service.list_alerts(
        session, principal.tenant_id, severity=severity, alert_type=alert_type, status=status
    )
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("/{alert_id}/resolve", response_model=AlertResponse, summary="Resolve alerta (US-052)")
async def resolve_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> AlertResponse:
    alert = await service.resolve_alert(session, principal.tenant_id, alert_id)
    return AlertResponse.model_validate(alert)


@router.post("/detect", response_model=DetectResponse, summary="Dispara detecção de alertas")
async def detect(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_detect_guard),
) -> DetectResponse:
    count = await service.run_detection(session, principal.tenant_id)
    return DetectResponse(created=count, detail=f"{count} alerta(s) novo(s) detectado(s)")
