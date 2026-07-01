"""Orquestra a explicação: predição -> prompt -> (cache|Claude|template) -> guardrails -> audit.

Degrade gracioso: sem ANTHROPIC_API_KEY, gera um texto de template estático
(determinístico) que também passa pelos guardrails. Nunca crasha por falta de LLM.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.audit.writer import write_event
from kairon.core.exceptions import NotFoundError, UpstreamError
from kairon.core.logging import get_logger
from kairon.explanation import guardrails
from kairon.explanation.claude_client import get_client
from kairon.explanation.models import ExplanationCache
from kairon.explanation.schemas import ExplainResponse
from kairon.prediction.db_models import Prediction

log = get_logger(__name__)

CACHE_TTL = timedelta(hours=1)

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "prompts"),
    autoescape=select_autoescape(enabled_extensions=()),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render_prompt(pred: Prediction, question: str | None = None) -> str:
    template_name = "explain_with_question.j2" if question else "explain_prediction.j2"
    template = _env.get_template(template_name)
    return template.render(
        origem=pred.origem,
        destino=pred.destino,
        produto=pred.produto,
        data_alvo=pred.data_alvo.isoformat(),
        frete=f"{pred.frete_r_per_ton:.2f}",
        p10=f"{pred.banda_p10:.2f}",
        p90=f"{pred.banda_p90:.2f}",
        model_version=pred.model_version,
        drivers=pred.drivers,
        pergunta=question or "",
    )


def _static_explanation(pred: Prediction, question: str | None = None) -> str:
    """Fallback determinístico (sem LLM). Cita rota + data + valor (passa guardrails)."""
    top = pred.drivers[0]["feature"] if pred.drivers else "custo de combustível"
    base = (
        f"Para a rota {pred.origem} -> {pred.destino} ({pred.produto}), na data "
        f"{pred.data_alvo.isoformat()}, o frete estimado é de R$ {pred.frete_r_per_ton:.2f} "
        f"por tonelada, com banda entre R$ {pred.banda_p10:.2f} e R$ {pred.banda_p90:.2f} "
        f"por tonelada. O principal fator desta cotação é {top}. "
    )
    if question:
        base += (
            f'Sobre sua pergunta ("{question}"): o copiloto de linguagem está indisponível, '
            f"então respondemos em modo template com base nos drivers acima. "
        )
    base += f"Estimativa gerada pelo modelo {pred.model_version} " f"(explicação em modo template)."
    return base


async def explain(
    session: AsyncSession,
    prediction_id: str,
    question: str | None = None,
    tenant_id: uuid.UUID | None = None,
) -> ExplainResponse:
    try:
        pred_uuid = uuid.UUID(prediction_id)
    except ValueError as exc:
        raise NotFoundError("prediction_id inválido") from exc

    # Escopo por tenant: predição de outro tenant é 404 (US-004).
    stmt = select(Prediction).where(Prediction.id == pred_uuid)
    if tenant_id is not None:
        stmt = stmt.where(Prediction.tenant_id == tenant_id)
    pred = (await session.execute(stmt)).scalars().first()
    if pred is None:
        raise NotFoundError(f"predição {prediction_id} não encontrada")

    # Sanitiza input livre do usuário antes de montar o prompt (anti prompt-injection).
    clean_question = guardrails.sanitize_input(question) if question else None
    prompt = _render_prompt(pred, clean_question)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    # ---- cache (TTL 1h) ----
    now = datetime.now(UTC)
    cached = (
        (
            await session.execute(
                select(ExplanationCache).where(
                    ExplanationCache.prompt_hash == prompt_hash,
                    ExplanationCache.expires_at > now,
                )
            )
        )
        .scalars()
        .first()
    )
    if cached is not None:
        log.info("explanation.cache_hit", prediction_id=prediction_id)
        return ExplainResponse(
            prediction_id=prediction_id, explanation=cached.explanation, source=cached.source
        )

    # ---- gera (Claude ou template) ----
    client = get_client()
    source = "template"
    if client.is_enabled:
        try:
            raw = await client.complete(prompt)
            source = "llm"
        except UpstreamError:
            raw = _static_explanation(pred, clean_question)
    else:
        raw = _static_explanation(pred)

    # ---- guardrails (ANTES de devolver / cachear) ----
    explanation = guardrails.enforce_output(
        raw,
        allowed_values=[pred.frete_r_per_ton, pred.banda_p10, pred.banda_p90],
        origem=pred.origem,
        destino=pred.destino,
    )

    # ---- cache + audit ----
    session.add(
        ExplanationCache(
            prediction_id=pred.id,
            prompt_hash=prompt_hash,
            explanation=explanation,
            source=source,
            expires_at=now + CACHE_TTL,
        )
    )
    await write_event(
        session,
        event_type="explanation.served",
        entity_id=str(pred.id),
        payload={"source": source, "prediction_id": str(pred.id)},
        tenant_id=pred.tenant_id,
    )
    log.info("explanation.served", prediction_id=prediction_id, source=source)
    return ExplainResponse(prediction_id=prediction_id, explanation=explanation, source=source)
