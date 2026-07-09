"""Client de embeddings (OpenAI). Reaproveita OPENAI_API_KEY e os limites do LLM.

Se a chave não estiver setada, `is_enabled` = False e a ingestão/RAG degradam
sem crashar (o copiloto continua explicando via prompt estruturado).
"""

from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential

from kairon.core.config import settings
from kairon.core.exceptions import UpstreamError
from kairon.core.logging import get_logger

log = get_logger(__name__)


class EmbeddingClient:
    def __init__(self) -> None:
        self._client = None
        if settings.openai_api_key:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=float(settings.llm_timeout_seconds),
                max_retries=0,
            )

    @property
    def is_enabled(self) -> bool:
        return self._client is not None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Gera embeddings para uma lista de textos. Levanta UpstreamError se falhar."""
        if self._client is None:
            raise UpstreamError("embeddings desabilitado (sem OPENAI_API_KEY)")
        try:
            resp = await self._client.embeddings.create(
                model=settings.openai_embedding_model, input=texts
            )
        except Exception as exc:  # noqa: BLE001 — normaliza erro do SDK
            log.warning("embeddings.failed", error=str(exc))
            raise UpstreamError("falha ao gerar embeddings") from exc
        return [d.embedding for d in resp.data]


_client: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    global _client
    if _client is None:
        _client = EmbeddingClient()
    return _client
