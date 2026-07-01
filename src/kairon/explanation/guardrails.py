"""Guardrails do copiloto LLM (ADR-005 + seção 8).

Funções PURAS (fáceis de testar). Duas responsabilidades:
1. sanitize_input  — limpa input livre do usuário (anti prompt-injection).
2. enforce_output  — valida a saída do LLM ANTES de devolver ao cliente.

Regra dura: o LLM NUNCA prevê frete. Se a saída contiver um valor monetário de
frete que não seja um dos valores fornecidos pelo motor, bloqueia (erro + alerta).
"""

from __future__ import annotations

import re

from kairon.core.exceptions import GuardrailViolation
from kairon.core.logging import get_logger

log = get_logger(__name__)

MAX_WORDS = 500
VALUE_TOLERANCE = 1.0  # R$/t — margem de arredondamento aceitável

# Padrões de injeção / formatação a remover do input livre.
_HTML_TAG = re.compile(r"<[^>]+>")
_MARKDOWN = re.compile(r"[`*_#>\[\]]")
_SYSTEM_CMDS = re.compile(
    r"(?i)\b(ignore (all|previous)|disregard|system prompt|you are now|jailbreak|sudo|rm -rf)\b"
)
# Número monetário associado a frete: "R$ 123,45" ou "123.45/t" ou "... por tonelada".
_MONEY_NEAR_FREIGHT = re.compile(
    r"(?:R\$\s*)?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*(?:/\s*t\b|por\s+tonelada|/tonelada|reais?\s+por\s+tonelada)",
    re.IGNORECASE,
)


def sanitize_input(text: str) -> str:
    """Remove HTML, markdown e comandos de sistema de input livre do usuário."""
    cleaned = _HTML_TAG.sub("", text)
    # Markdown ANTES do token: senão o stripper de markdown comeria os colchetes de "[removido]".
    cleaned = _MARKDOWN.sub("", cleaned)
    cleaned = _SYSTEM_CMDS.sub("[removido]", cleaned)
    return cleaned.strip()


def _to_float(raw: str) -> float:
    """Converte '1.234,56' ou '1234.56' para float."""
    s = raw.replace(".", "").replace(",", ".") if "," in raw else raw.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def enforce_output(
    text: str,
    *,
    allowed_values: list[float],
    origem: str,
    destino: str,
) -> str:
    """Valida a saída do LLM. Levanta GuardrailViolation se violar uma regra dura."""
    # 1. Tamanho.
    if len(text.split()) > MAX_WORDS:
        _violate("resposta excede 500 palavras", text)

    # 2. Deve citar a rota (origem OU destino) e ao menos um valor fornecido.
    lower = text.lower()
    cites_route = origem.lower() in lower or destino.lower() in lower
    cites_value = any(_value_in_text(text, v) for v in allowed_values)
    if not (cites_route and cites_value):
        _violate("resposta não cita rota e/ou valor fornecido", text)

    # 3. Predição numérica não solicitada: nenhum R$/t pode divergir dos valores dados.
    for match in _MONEY_NEAR_FREIGHT.finditer(text):
        value = _to_float(match.group(1))
        if value != value:  # NaN
            continue
        if not any(abs(value - allowed) <= VALUE_TOLERANCE for allowed in allowed_values):
            _violate(f"LLM inventou valor de frete não solicitado: {value}", text)

    return text


def _value_in_text(text: str, value: float) -> bool:
    """Aceita '123', '123,45' ou '123.45' representando o valor."""
    as_int = str(int(round(value)))
    comma = f"{value:.2f}".replace(".", ",")
    dot = f"{value:.2f}"
    return any(token in text for token in (as_int, comma, dot))


def _violate(reason: str, text: str) -> None:
    # Alerta Sentry via log de erro (o SDK captura logs de erro se configurado).
    log.error("guardrail.violation", reason=reason, output_preview=text[:120])
    raise GuardrailViolation(f"Guardrail bloqueou a saída do LLM: {reason}")
