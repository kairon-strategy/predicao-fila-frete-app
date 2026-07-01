"""Detectores de alerta (EPIC 8).

MVP: `detect_diesel_spikes` roda sobre raw_diesel_prices (dados que já ingerimos)
— não depende de scraping externo. Compara o preço mais recente por UF com a média
dos dias anteriores; salto grande vira alerta.

ANTT (US-048) e CONAB (US-049) reais dependem de fontes externas + scraping —
follow-up documentado (TODO(#30)). O framework de detector já fica pronto.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.alerts.models import Alert
from kairon.core.logging import get_logger
from kairon.ingestion.anp.models import RawDieselPrice

log = get_logger(__name__)

DIESEL_ALERT_TYPE = "diesel_spike"
WARN_PCT = 4.0
CRITICAL_PCT = 8.0
LOOKBACK_DAYS = 30
MIN_SAMPLES = 5  # precisa de histórico mínimo para uma baseline confiável


async def _has_active_alert(
    session: AsyncSession, tenant_id: uuid.UUID, alert_type: str, entity_id: str
) -> bool:
    stmt = select(Alert.id).where(
        Alert.tenant_id == tenant_id,
        Alert.alert_type == alert_type,
        Alert.entity_id == entity_id,
        Alert.status == "active",
    )
    return (await session.execute(stmt)).first() is not None


async def detect_diesel_spikes(session: AsyncSession, tenant_id: uuid.UUID) -> list[Alert]:
    """Cria alertas para UFs cujo diesel mais recente saltou vs a média recente.

    Idempotente por (tenant, tipo, UF, active): não duplica alerta já aberto.
    """
    ufs = (await session.execute(select(RawDieselPrice.uf).distinct())).scalars().all()
    created: list[Alert] = []

    for uf in ufs:
        # Agrega por DATA (média do dia): robusto a múltiplas linhas por (data, uf)
        # — cidades/fontes distintas não bagunçam qual é o "preço mais recente".
        day_rows = (
            await session.execute(
                select(RawDieselPrice.data, func.avg(RawDieselPrice.preco_medio))
                .where(RawDieselPrice.uf == uf)
                .group_by(RawDieselPrice.data)
                .order_by(RawDieselPrice.data.desc())
                .limit(LOOKBACK_DAYS + 1)
            )
        ).all()
        prices = [float(avg) for _, avg in day_rows]
        if len(prices) < MIN_SAMPLES:
            continue

        latest = prices[0]
        baseline_samples = prices[1:]
        baseline = sum(baseline_samples) / len(baseline_samples)
        if baseline <= 0:
            continue

        pct = (latest - baseline) / baseline * 100
        severity = "critical" if pct >= CRITICAL_PCT else "warn" if pct >= WARN_PCT else None
        if severity is None:
            continue

        if await _has_active_alert(session, tenant_id, DIESEL_ALERT_TYPE, uf):
            continue

        alert = Alert(
            tenant_id=tenant_id,
            severity=severity,
            alert_type=DIESEL_ALERT_TYPE,
            entity_id=uf,
            title=f"Diesel em alta em {uf}: +{pct:.1f}% vs média recente",
            body=(
                f"O preço médio de diesel em {uf} subiu {pct:.1f}% "
                f"(atual R$ {latest:.2f}/L vs média R$ {baseline:.2f}/L dos últimos "
                f"{len(baseline_samples)} registros). Frete rodoviário nas rotas com origem "
                f"em {uf} pode pressionar para cima."
            ),
            meta={
                "uf": uf,
                "latest": round(latest, 3),
                "baseline": round(baseline, 3),
                "pct": round(pct, 2),
            },
        )
        session.add(alert)
        created.append(alert)

    if created:
        await session.flush()
        log.info("alerts.diesel_detected", tenant_id=str(tenant_id), count=len(created))
    return created
