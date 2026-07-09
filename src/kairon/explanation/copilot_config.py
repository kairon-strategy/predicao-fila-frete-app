"""Configuração do copiloto (prompts + settings) por tenant, com padrão global.

Resolução em cascata: linha do tenant -> linha global (tenant_id NULL) -> default
do código (template em disco / env). Usado pelo `service.explain` e pelos
endpoints admin em `config_router.py`. Ver docs/GOVERNANCA_IA.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, TemplateSyntaxError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.config import settings
from kairon.core.exceptions import NotFoundError, ValidationError
from kairon.explanation.models import CopilotPrompt, CopilotSettings

# Fluxos de prompt que o copiloto usa (key -> rótulo legível na UI). Fixos.
PROMPT_KEYS: dict[str, str] = {
    "explain_prediction": "Explicar predição",
    "explain_with_question": "Explicar com pergunta do usuário",
    "simulate_nl": "Simulação em linguagem natural",
}
_PROMPTS_DIR = Path(__file__).parent / "prompts"

PROVIDERS = ("auto", "openai", "anthropic")


# ---------------------------------------------------------------- prompts -----


def _file_default(prompt_key: str) -> str:
    """Conteúdo do template .j2 em disco (default de fábrica)."""
    path = _PROMPTS_DIR / f"{prompt_key}.j2"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _validate_prompt_key(prompt_key: str) -> None:
    if prompt_key not in PROMPT_KEYS:
        raise NotFoundError(f"prompt '{prompt_key}' não existe")


def _validate_template(content: str) -> None:
    if not content.strip():
        raise ValidationError("o prompt não pode ser vazio")
    try:
        Environment(autoescape=False).from_string(content)  # noqa: S701 — prompt, não HTML
    except TemplateSyntaxError as exc:
        raise ValidationError(f"template inválido: {exc.message}") from exc


async def _prompt_row(
    session: AsyncSession, tenant_id: uuid.UUID | None, prompt_key: str
) -> CopilotPrompt | None:
    stmt = select(CopilotPrompt).where(CopilotPrompt.prompt_key == prompt_key)
    stmt = stmt.where(
        CopilotPrompt.tenant_id == tenant_id
        if tenant_id is not None
        else CopilotPrompt.tenant_id.is_(None)
    )
    return (await session.execute(stmt)).scalars().first()


async def resolve_prompt(
    session: AsyncSession, tenant_id: uuid.UUID | None, prompt_key: str
) -> str:
    """Conteúdo efetivo do prompt: tenant -> global -> arquivo."""
    if tenant_id is not None:
        row = await _prompt_row(session, tenant_id, prompt_key)
        if row is not None:
            return row.content
    row = await _prompt_row(session, None, prompt_key)
    if row is not None:
        return row.content
    return _file_default(prompt_key)


async def list_prompts(session: AsyncSession, tenant_id: uuid.UUID | None) -> list[dict]:
    """Lista os fluxos com o conteúdo efetivo + de onde veio (scope)."""
    out: list[dict] = []
    for key, label in PROMPT_KEYS.items():
        tenant_row = await _prompt_row(session, tenant_id, key) if tenant_id is not None else None
        global_row = await _prompt_row(session, None, key)
        if tenant_row is not None:
            content, scope, row = tenant_row.content, "tenant", tenant_row
        elif global_row is not None:
            content, scope, row = global_row.content, "global", global_row
        else:
            content, scope, row = _file_default(key), "default", None
        out.append(
            {
                "key": key,
                "label": label,
                "content": content,
                "scope": scope,
                "is_override": tenant_row is not None,
                "updated_by": row.updated_by if row is not None else None,
                "updated_at": row.updated_at.isoformat() if row is not None else None,
                "default": _file_default(key),
            }
        )
    return out


async def upsert_prompt(
    session: AsyncSession,
    tenant_id: uuid.UUID | None,
    prompt_key: str,
    content: str,
    updated_by: str | None = None,
) -> dict:
    """Cria/atualiza o prompt do fluxo para o escopo (tenant ou global se None)."""
    _validate_prompt_key(prompt_key)
    _validate_template(content)
    row = await _prompt_row(session, tenant_id, prompt_key)
    if row is None:
        row = CopilotPrompt(tenant_id=tenant_id, prompt_key=prompt_key)
        session.add(row)
    row.content = content
    row.updated_by = updated_by
    await session.flush()
    return {"key": prompt_key, "content": content, "scope": "tenant" if tenant_id else "global"}


async def reset_prompt(
    session: AsyncSession, tenant_id: uuid.UUID | None, prompt_key: str
) -> None:
    """Remove o override do escopo -> volta a herdar (global ou arquivo)."""
    _validate_prompt_key(prompt_key)
    row = await _prompt_row(session, tenant_id, prompt_key)
    if row is not None:
        await session.delete(row)
        await session.flush()


# --------------------------------------------------------------- settings -----


@dataclass(frozen=True)
class ResolvedConfig:
    enabled: bool
    provider: str  # auto | openai | anthropic
    model: str | None
    max_tokens: int | None
    temperature: float | None
    max_words: int | None
    rate_limit_per_min: int


async def _settings_row(
    session: AsyncSession, tenant_id: uuid.UUID | None
) -> CopilotSettings | None:
    stmt = select(CopilotSettings).where(
        CopilotSettings.tenant_id == tenant_id
        if tenant_id is not None
        else CopilotSettings.tenant_id.is_(None)
    )
    return (await session.execute(stmt)).scalars().first()


def _pick(
    t: CopilotSettings | None, g: CopilotSettings | None, attr: str, default: Any
) -> Any:
    for row in (t, g):
        if row is not None and getattr(row, attr) is not None:
            return getattr(row, attr)
    return default


async def resolve_config(
    session: AsyncSession, tenant_id: uuid.UUID | None
) -> ResolvedConfig:
    """Config efetiva do copiloto: tenant -> global -> env/hardcoded."""
    t = await _settings_row(session, tenant_id) if tenant_id is not None else None
    g = await _settings_row(session, None)
    enabled = t.enabled if t is not None else (g.enabled if g is not None else True)
    return ResolvedConfig(
        enabled=enabled,
        provider=_pick(t, g, "provider", "auto"),
        model=_pick(t, g, "model", None),
        max_tokens=_pick(t, g, "max_tokens", None),
        temperature=_pick(t, g, "temperature", None),
        max_words=_pick(t, g, "max_words", None),
        rate_limit_per_min=_pick(t, g, "rate_limit_per_min", settings.explain_max_per_min),
    )


async def get_settings(session: AsyncSession, tenant_id: uuid.UUID | None) -> dict:
    """Para a UI: override cru do tenant (null = herda) + config efetiva em uso."""
    row = await _settings_row(session, tenant_id) if tenant_id is not None else None
    eff = await resolve_config(session, tenant_id)
    override = {
        "enabled": row.enabled if row is not None else None,
        "provider": row.provider if row is not None else None,
        "model": row.model if row is not None else None,
        "max_tokens": row.max_tokens if row is not None else None,
        "temperature": row.temperature if row is not None else None,
        "max_words": row.max_words if row is not None else None,
        "rate_limit_per_min": row.rate_limit_per_min if row is not None else None,
    }
    effective = {
        "enabled": eff.enabled,
        "provider": eff.provider,
        "model": eff.model or settings.openai_model,
        "max_tokens": eff.max_tokens or settings.openai_max_tokens,
        "temperature": eff.temperature,
        "max_words": eff.max_words or 500,
        "rate_limit_per_min": eff.rate_limit_per_min,
    }
    return {"has_override": row is not None, "override": override, "effective": effective}


def _validate_settings(data: dict) -> None:
    provider = data.get("provider")
    if provider is not None and provider not in PROVIDERS:
        raise ValidationError(f"provedor inválido: {provider} (use {', '.join(PROVIDERS)})")
    ranges = {
        "max_tokens": (1, 8192),
        "temperature": (0.0, 2.0),
        "max_words": (20, 2000),
        "rate_limit_per_min": (1, 600),
    }
    for field, (lo, hi) in ranges.items():
        v = data.get(field)
        if v is not None and not (lo <= v <= hi):
            raise ValidationError(f"{field} fora do intervalo permitido ({lo}–{hi})")


async def update_settings(
    session: AsyncSession,
    tenant_id: uuid.UUID | None,
    data: dict,
    updated_by: str | None = None,
) -> dict:
    """Upsert da linha de settings do escopo. Campos ausentes/None = herda."""
    _validate_settings(data)
    row = await _settings_row(session, tenant_id)
    if row is None:
        row = CopilotSettings(tenant_id=tenant_id)
        session.add(row)
    if "enabled" in data and data["enabled"] is not None:
        row.enabled = bool(data["enabled"])
    if "provider" in data and data["provider"] is not None:
        row.provider = data["provider"]
    for field in ("model", "max_tokens", "temperature", "max_words", "rate_limit_per_min"):
        if field in data:
            setattr(row, field, data[field])  # None limpa o override (volta a herdar)
    row.updated_by = updated_by
    await session.flush()
    return await get_settings(session, tenant_id)
