"""Router do contexto knowledge (RAG).

- POST /v1/copilot/ask   — perguntar à base (quem tem explain:run)
- GET/POST/DELETE /v1/knowledge/documents — gestão da base (admin: copilot:read/write)

A pergunta é escopada ao tenant do principal (+ base global). PII da pergunta é
redigida antes de ir ao provedor (guardrails).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.config import settings
from kairon.core.database import get_session
from kairon.knowledge import service
from kairon.knowledge.schemas import (
    AskRequest,
    AskResponse,
    DocumentItem,
    IngestRequest,
    IngestResponse,
)
from kairon.tenant.auth import Principal, require_permission

router = APIRouter()

_ask_guard = require_permission("explain:run")
_read = require_permission("copilot:read")
_write = require_permission("copilot:write")


@router.post("/copilot/ask", response_model=AskResponse, summary="Pergunta à base (RAG)")
async def ask(
    body: AskRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_ask_guard),
) -> dict:
    return await service.ask(
        session, principal.tenant_id, body.question, body.k or settings.rag_top_k
    )


@router.get(
    "/knowledge/documents", response_model=list[DocumentItem], summary="Lista documentos da base"
)
async def list_documents(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_read),
) -> list[dict]:
    return await service.list_documents(session, principal.tenant_id)


@router.post(
    "/knowledge/documents",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingere um documento na base (chunk + embed)",
)
async def ingest_document(
    body: IngestRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_write),
) -> dict:
    return await service.ingest_document(
        session,
        principal.tenant_id,
        title=body.title,
        text=body.text,
        source=body.source,
        created_by=str(principal.user_id),
    )


@router.delete(
    "/knowledge/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove um documento da base do tenant",
)
async def delete_document(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_write),
) -> Response:
    ok = await service.delete_document(session, principal.tenant_id, doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="documento não encontrado")
    return Response(status_code=204)
