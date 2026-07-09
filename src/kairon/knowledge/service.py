"""Base de conhecimento (RAG): ingestão (chunk+embed) e recuperação + pergunta.

Escopo por tenant: a busca considera a base do tenant + a base global (NULL).
Guardrails: a pergunta passa por redação de PII; a resposta é ancorada SÓ nos
trechos recuperados (com citação), reduzindo alucinação. Ver docs/GOVERNANCA_IA.md.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.audit.writer import write_event
from kairon.core.exceptions import UpstreamError
from kairon.core.logging import get_logger
from kairon.explanation import copilot_config, guardrails
from kairon.explanation.claude_client import get_client_for
from kairon.knowledge.embeddings import get_embedding_client
from kairon.knowledge.models import KbChunk, KbDocument

log = get_logger(__name__)

MAX_CHUNK_CHARS = 900
CHUNK_OVERLAP = 120


def chunk_text(text: str) -> list[str]:
    """Chunking simples e estrutural: agrupa parágrafos até ~900 chars, com leve
    overlap para não perder contexto na borda."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 2 <= MAX_CHUNK_CHARS:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                chunks.append(buf)
            # overlap: começa o próximo com a cauda do anterior
            tail = buf[-CHUNK_OVERLAP:] if buf else ""
            buf = f"{tail}\n\n{p}" if tail else p
            # parágrafo maior que o limite: quebra bruta
            while len(buf) > MAX_CHUNK_CHARS:
                chunks.append(buf[:MAX_CHUNK_CHARS])
                buf = buf[MAX_CHUNK_CHARS - CHUNK_OVERLAP :]
    if buf.strip():
        chunks.append(buf)
    return chunks


async def ingest_document(
    session: AsyncSession,
    tenant_id: uuid.UUID | None,
    title: str,
    text: str,
    source: str | None = None,
    created_by: str | None = None,
) -> dict:
    """Cria um documento, quebra em chunks, gera embeddings e persiste."""
    embedder = get_embedding_client()
    if not embedder.is_enabled:
        raise UpstreamError("ingestão indisponível (sem OPENAI_API_KEY para embeddings)")
    chunks = chunk_text(text)
    if not chunks:
        raise UpstreamError("documento vazio após chunking")

    doc = KbDocument(
        tenant_id=tenant_id, title=title.strip(), source=source, created_by=created_by
    )
    session.add(doc)
    await session.flush()

    vectors = await embedder.embed(chunks)
    for i, (content, emb) in enumerate(zip(chunks, vectors, strict=True)):
        session.add(
            KbChunk(
                document_id=doc.id,
                tenant_id=tenant_id,
                content=content,
                embedding=emb,
                chunk_index=i,
            )
        )
    await session.flush()
    await write_event(
        session,
        event_type="knowledge.document_ingested",
        entity_id=str(doc.id),
        payload={"by": created_by, "title": title, "chunks": len(chunks)},
        tenant_id=tenant_id,
    )
    log.info("knowledge.ingested", doc_id=str(doc.id), chunks=len(chunks))
    return {"document_id": str(doc.id), "title": title, "chunks": len(chunks)}


async def list_documents(session: AsyncSession, tenant_id: uuid.UUID | None) -> list[dict]:
    """Documentos visíveis ao tenant (do tenant + globais)."""
    stmt = (
        select(KbDocument)
        .where(or_(KbDocument.tenant_id.is_(None), KbDocument.tenant_id == tenant_id))
        .order_by(KbDocument.created_at.desc())
    )
    docs = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(d.id),
            "title": d.title,
            "source": d.source,
            "scope": "global" if d.tenant_id is None else "tenant",
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


async def delete_document(
    session: AsyncSession, tenant_id: uuid.UUID | None, doc_id: uuid.UUID
) -> bool:
    """Remove um documento do tenant (e seus chunks via cascade). Base global não
    é apagada por esta rota (só o próprio tenant)."""
    doc = (
        await session.execute(
            select(KbDocument).where(
                KbDocument.id == doc_id, KbDocument.tenant_id == tenant_id
            )
        )
    ).scalars().first()
    if doc is None:
        return False
    await session.execute(delete(KbChunk).where(KbChunk.document_id == doc.id))
    await session.delete(doc)
    await session.flush()
    return True


async def retrieve(
    session: AsyncSession, tenant_id: uuid.UUID | None, query: str, k: int
) -> list[dict]:
    """Top-k chunks mais próximos (cosine) da pergunta, no escopo do tenant + global."""
    embedder = get_embedding_client()
    qemb = (await embedder.embed([query]))[0]
    dist = KbChunk.embedding.cosine_distance(qemb).label("dist")
    stmt = (
        select(KbChunk.content, KbDocument.title, KbDocument.source, dist)
        .join(KbDocument, KbChunk.document_id == KbDocument.id)
        .where(or_(KbChunk.tenant_id.is_(None), KbChunk.tenant_id == tenant_id))
        .order_by(dist)
        .limit(k)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {"content": r.content, "title": r.title, "source": r.source, "distance": float(r.dist)}
        for r in rows
    ]


def _build_rag_prompt(question: str, contexts: list[dict]) -> str:
    blocks = []
    for i, c in enumerate(contexts, 1):
        src = f" (fonte: {c['source']})" if c.get("source") else ""
        blocks.append(f"[{i}] {c['title']}{src}\n{c['content']}")
    ctx = "\n\n".join(blocks)
    return (
        "Você é o copiloto do Kairon Frete. Responda à PERGUNTA usando SOMENTE o "
        "CONTEXTO abaixo. Regras invioláveis:\n"
        "- Se a resposta não estiver no contexto, diga claramente que não encontrou "
        "na base de conhecimento. NUNCA invente.\n"
        "- Cite as fontes usadas como [1], [2] etc.\n"
        "- Português claro e objetivo, no máximo 180 palavras.\n\n"
        f"CONTEXTO:\n{ctx}\n\n"
        f"PERGUNTA: {question}\n\nResposta:"
    )


async def ask(
    session: AsyncSession, tenant_id: uuid.UUID | None, question: str, k: int
) -> dict:
    """RAG: recupera contexto, monta prompt e responde com citações (ou 'não sei')."""
    embedder = get_embedding_client()
    clean_q = guardrails.sanitize_input(question)  # LGPD: redige PII da pergunta

    if not embedder.is_enabled:
        return {
            "answer": "A base de conhecimento está indisponível no momento.",
            "sources": [],
            "grounded": False,
        }

    try:
        contexts = await retrieve(session, tenant_id, clean_q, k)
    except UpstreamError:
        # Falha de embeddings (ex.: cota da OpenAI) → degrada sem 500.
        log.warning("knowledge.retrieve_failed", tenant_id=str(tenant_id))
        return {
            "answer": "A base de conhecimento está indisponível no momento.",
            "sources": [],
            "grounded": False,
        }
    if not contexts:
        return {
            "answer": "Não encontrei nada na base de conhecimento sobre isso.",
            "sources": [],
            "grounded": False,
        }

    cfg = await copilot_config.resolve_config(session, tenant_id)
    answer = ""
    if cfg.enabled:
        client = get_client_for(cfg.provider)
        if client.is_enabled:
            prompt = _build_rag_prompt(clean_q, contexts)
            try:
                answer = (
                    await client.complete(
                        prompt,
                        model=cfg.model,
                        max_tokens=cfg.max_tokens,
                        temperature=cfg.temperature,
                    )
                ).strip()
            except UpstreamError:
                log.warning("knowledge.llm_failed", tenant_id=str(tenant_id))

    if not answer:
        # Sem LLM: devolve o trecho mais relevante como fallback (ainda ancorado).
        answer = f"Trecho mais relevante da base:\n{contexts[0]['content']}"

    sources = []
    seen = set()
    for c in contexts:
        key = (c["title"], c.get("source"))
        if key not in seen:
            seen.add(key)
            sources.append({"title": c["title"], "source": c.get("source")})
    await write_event(
        session,
        event_type="knowledge.asked",
        payload={"chunks": len(contexts), "grounded": True},
        tenant_id=tenant_id,
    )
    return {"answer": answer, "sources": sources, "grounded": True}
