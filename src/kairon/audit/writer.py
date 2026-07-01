"""Escrita append-only de eventos de auditoria.

Interface usada por outros contexts (ex: explanation.service). Nunca atualiza nem
apaga — só insere. LGPD: o payload NÃO deve conter PII em claro (use hash_pii).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from kairon.audit.models import AuditEvent
from kairon.core.logging import get_logger

log = get_logger(__name__)


async def write_event(
    session: AsyncSession,
    *,
    event_type: str,
    payload: dict[str, Any],
    entity_id: str | None = None,
    tenant_id: uuid.UUID | None = None,
) -> None:
    """Insere um evento de auditoria. Best-effort: falha aqui não derruba o fluxo."""
    try:
        session.add(
            AuditEvent(
                tenant_id=tenant_id,
                event_type=event_type,
                entity_id=entity_id,
                payload=payload,
            )
        )
        await session.flush()
    except Exception as exc:  # noqa: BLE001
        log.warning("audit.write_failed", event_type=event_type, error=str(exc))
