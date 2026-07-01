"""Wrapper mínimo do SDK anthropic (ADR-005/011: sem LangChain).

Assíncrono. Se ANTHROPIC_API_KEY não estiver setada, `is_enabled` = False e o
service cai no template estático (não crasha). Retry com tenacity em erro transiente.
"""

from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential

from kairon.core.config import settings
from kairon.core.exceptions import UpstreamError
from kairon.core.logging import get_logger

log = get_logger(__name__)


class ClaudeClient:
    def __init__(self) -> None:
        self._client = None
        if settings.anthropic_api_key:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

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
            raise UpstreamError("Claude desabilitado (sem ANTHROPIC_API_KEY)")
        try:
            message = await self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=settings.anthropic_max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001 — normaliza qualquer erro do SDK
            log.warning("claude.call_failed", error=str(exc))
            raise UpstreamError("falha ao chamar Claude") from exc

        # Concatena blocos de texto da resposta (só blocos do tipo "text" têm .text).
        parts = [
            getattr(block, "text", "")
            for block in message.content
            if getattr(block, "type", None) == "text"
        ]
        return "".join(parts).strip()


_client: ClaudeClient | None = None


def get_client() -> ClaudeClient:
    global _client
    if _client is None:
        _client = ClaudeClient()
    return _client
