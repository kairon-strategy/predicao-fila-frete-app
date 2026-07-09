"""Router admin da configuração do copiloto: /v1/copilot/*.

Tudo aqui exige `copilot:read` (ler) ou `copilot:write` (editar) — por padrão só
o perfil admin tem essas permissões. A config é por tenant (do principal); o
padrão global (tenant NULL) é o fallback e não é editado por esta tela.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.database import get_session
from kairon.explanation import copilot_config
from kairon.explanation.schemas import (
    CopilotSettingsUpdate,
    PromptItem,
    PromptUpdate,
)
from kairon.tenant.auth import Principal, require_permission

router = APIRouter(prefix="/copilot", tags=["copilot-config"])

_read = require_permission("copilot:read")
_write = require_permission("copilot:write")


@router.get("/prompts", response_model=list[PromptItem], summary="Lista os prompts do copiloto")
async def list_prompts(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_read),
) -> list[dict]:
    return await copilot_config.list_prompts(session, principal.tenant_id)


@router.put("/prompts/{prompt_key}", summary="Cria/edita o prompt de um fluxo")
async def upsert_prompt(
    prompt_key: str,
    body: PromptUpdate,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_write),
) -> dict:
    return await copilot_config.upsert_prompt(
        session, principal.tenant_id, prompt_key, body.content, updated_by=str(principal.user_id)
    )


@router.delete(
    "/prompts/{prompt_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Restaura o prompt padrão (remove o override do tenant)",
)
async def reset_prompt(
    prompt_key: str,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_write),
) -> Response:
    await copilot_config.reset_prompt(session, principal.tenant_id, prompt_key)
    return Response(status_code=204)


@router.get("/settings", summary="Configuração efetiva do copiloto (+ override do tenant)")
async def get_settings(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_read),
) -> dict:
    return await copilot_config.get_settings(session, principal.tenant_id)


@router.put("/settings", summary="Edita a configuração do copiloto do tenant")
async def update_settings(
    body: CopilotSettingsUpdate,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_write),
) -> dict:
    return await copilot_config.update_settings(
        session,
        principal.tenant_id,
        body.model_dump(exclude_unset=True),
        updated_by=str(principal.user_id),
    )
