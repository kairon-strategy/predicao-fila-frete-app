"""Serviço do context alerts: feed, resolução e disparo de detecção (US-051/052/048)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.alerts.detectors import detect_diesel_spikes
from kairon.alerts.models import Alert
from kairon.core.exceptions import NotFoundError
from kairon.core.logging import get_logger

log = get_logger(__name__)

# Ordenação do feed: severidade primeiro (US-051), depois mais recente.
_SEVERITY_RANK = {"critical": 0, "warn": 1, "info": 2}


async def list_alerts(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    severity: str | None = None,
    alert_type: str | None = None,
    status: str = "active",
) -> list[Alert]:
    stmt = select(Alert).where(Alert.tenant_id == tenant_id, Alert.status == status)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if alert_type:
        stmt = stmt.where(Alert.alert_type == alert_type)
    alerts = list((await session.execute(stmt)).scalars().all())
    alerts.sort(key=lambda a: (_SEVERITY_RANK.get(a.severity, 9), -a.id))
    return alerts


async def resolve_alert(session: AsyncSession, tenant_id: uuid.UUID, alert_id: int) -> Alert:
    alert = (
        (
            await session.execute(
                select(Alert).where(Alert.id == alert_id, Alert.tenant_id == tenant_id)
            )
        )
        .scalars()
        .first()
    )
    if alert is None:
        raise NotFoundError(f"alerta {alert_id} não encontrado")
    alert.status = "resolved"
    alert.resolved_at = datetime.now(UTC)
    await session.flush()
    log.info("alerts.resolved", alert_id=alert_id, tenant_id=str(tenant_id))
    return alert


async def run_detection(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Roda os detectores disponíveis para o tenant. Retorna quantos alertas novos."""
    created = await detect_diesel_spikes(session, tenant_id)
    # TODO(#30): detectores ANTT (US-048) e CONAB (US-049) dependem de fonte externa.
    return len(created)
