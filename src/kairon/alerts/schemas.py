"""Schemas do context alerts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    severity: str
    alert_type: str
    entity_id: str | None
    title: str
    body: str
    meta: dict
    status: str
    created_at: datetime | None
    resolved_at: datetime | None


class DetectResponse(BaseModel):
    created: int
    detail: str
