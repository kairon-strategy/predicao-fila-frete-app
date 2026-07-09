"""Orquestra a explicação: predição -> prompt -> (cache|LLM|template) -> guardrails -> audit.

O provedor de LLM é resolvido em `claude_client.get_client()` (OpenAI se
OPENAI_API_KEY estiver setada, senão Claude). Degrade gracioso: sem nenhuma
chave, gera um texto de template estático (determinístico) que também passa
pelos guardrails. Nunca crasha por falta de LLM.
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
from kairon.core.config import settings
from kairon.core.exceptions import GuardrailViolation, NotFoundError, UpstreamError
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

    # Sanitiza input livre: cap de tamanho (custo/abuso), redação de PII (LGPD) e
    # anti prompt-injection. Ver docs/GOVERNANCA_IA.md §4/§6.
    clean_question: str | None = None
    if question:
        capped = question[: settings.llm_max_input_chars]
        pii_types = guardrails.scan_pii(capped)
        clean_question = guardrails.sanitize_input(capped)
        if pii_types:
            # Observabilidade LGPD: registra o TIPO de PII redigida, nunca o valor.
            log.info("explanation.pii_redacted", prediction_id=prediction_id, types=sorted(set(pii_types)))
            await write_event(
                session,
                event_type="explanation.pii_redacted",
                entity_id=str(pred.id),
                payload={"types": sorted(set(pii_types)), "prediction_id": str(pred.id)},
                tenant_id=pred.tenant_id,
            )
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

    # ---- gera (LLM com guardrail de saída, senão template) ----
    allowed = [pred.frete_r_per_ton, pred.banda_p10, pred.banda_p90]
    client = get_client()
    explanation: str | None = None
    source = "template"

    if client.is_enabled:
        try:
            candidate = await client.complete(prompt)
            if candidate.strip():
                # Valida a saída do LLM ANTES de aceitar. Se violar, cai no template.
                explanation = guardrails.enforce_output(
                    candidate, allowed_values=allowed, origem=pred.origem, destino=pred.destino
                )
                source = "llm"
        except UpstreamError:
            log.warning("explanation.llm_upstream_error", prediction_id=prediction_id)
        except GuardrailViolation:
            # Saída do LLM reprovada no guardrail → degrada para template (não 500).
            log.warning("explanation.guardrail_fallback", prediction_id=prediction_id)

    if explanation is None:
        # Fallback determinístico — também passa pelo guardrail (defesa em profundidade).
        raw = _static_explanation(pred, clean_question)
        explanation = guardrails.enforce_output(
            raw, allowed_values=allowed, origem=pred.origem, destino=pred.destino
        )
        source = "template"

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
