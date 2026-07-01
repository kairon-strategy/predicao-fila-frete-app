"""Logging estruturado (structlog) + init do Sentry.

- Em produção: JSON no stdout (parseável por Grafana Loki depois).
- Em dev: saída colorida e legível.
- Sentry só liga se SENTRY_DSN estiver setada (degrade gracioso).

Regra LGPD (seção 8): NUNCA logar CPF/CNPJ/nome de comprador. Se precisar,
use `hash_pii()`.
"""

from __future__ import annotations

import hashlib
import logging
import sys

import structlog

from kairon.core.config import settings

_configured = False


def hash_pii(value: str) -> str:
    """Hash determinístico para PII que não pode aparecer em claro no log (LGPD)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def configure_logging() -> None:
    """Idempotente. Chamado uma vez no boot da app."""
    global _configured
    if _configured:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,  # injeta correlation-id do request
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    _init_sentry()
    _configured = True


def _init_sentry() -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[StarletteIntegration(), FastApiIntegration()],
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Retorna um logger estruturado. Use em vez de print() (ver anti-padrões)."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)
