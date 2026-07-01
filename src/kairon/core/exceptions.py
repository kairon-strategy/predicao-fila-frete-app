"""Exceções de domínio compartilhadas.

Cada bounded context pode definir as suas, mas todas herdam de KaironError
para o handler global em main.py conseguir mapear -> HTTP consistentemente.
"""

from __future__ import annotations


class KaironError(Exception):
    """Base de toda exceção de domínio Kairon."""

    status_code: int = 500
    error_code: str = "kairon_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(KaironError):
    status_code = 404
    error_code = "not_found"


class ValidationError(KaironError):
    status_code = 422
    error_code = "validation_error"


class UpstreamError(KaironError):
    """Falha em dependência externa (ANP, Anthropic, etc.)."""

    status_code = 502
    error_code = "upstream_error"


class GuardrailViolation(KaironError):
    """LLM violou uma regra dura (ex: tentou prever frete). Ver ADR-005."""

    status_code = 500
    error_code = "guardrail_violation"
