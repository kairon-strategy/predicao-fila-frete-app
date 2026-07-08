"""Wrapper mínimo do SDK openai (ADR-005/011: sem LangChain).

Mesma interface do ClaudeClient (`is_enabled` + `complete`), para o service
trocar de provedor sem mudar nada. Usa a Responses API (client.responses.create).
Se OPENAI_API_KEY não estiver setada, `is_enabled` = False e o service cai no
template estático (não crasha). Retry com tenacity em erro transiente.
"""

from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential

from kairon.core.config import settings
from kairon.core.exceptions import UpstreamError
from kairon.core.logging import get_logger

log = get_logger(__name__)


class OpenAIClient:
    def __init__(self) -> None:
        self._client = None
        if settings.openai_api_key:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    @property
    def is_enabled(self) -> bool:
        return self._client is not None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )
    async def complete(self, prompt: str) -> str:
        """Manda um prompt e devolve o texto. Levanta UpstreamError se falhar de vez."""
        if self._client is None:
            raise UpstreamError("OpenAI desabilitado (sem OPENAI_API_KEY)")
        try:
            response = await self._client.responses.create(
                model=settings.openai_model,
                input=prompt,
                max_output_tokens=settings.openai_max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 — normaliza qualquer erro do SDK
            log.warning("openai.call_failed", error=str(exc))
            raise UpstreamError("falha ao chamar OpenAI") from exc

        # A Responses API expõe o texto agregado em .output_text.
        return (response.output_text or "").strip()
