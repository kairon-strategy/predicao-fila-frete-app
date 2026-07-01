"""Métricas Prometheus (US-093).

Expõe contagem e latência de requests por rota/método/status. O /metrics é
montado em main.py. Mantido simples: um Counter + um Histogram no registry default.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "kairon_http_requests_total",
    "Total de requests HTTP",
    labelnames=("method", "path", "status"),
)

REQUEST_LATENCY = Histogram(
    "kairon_http_request_duration_seconds",
    "Latência das requests HTTP em segundos",
    labelnames=("method", "path"),
    # buckets pensados para o SLA de /v1/predict (< 500ms) e caudas.
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


def observe(*, method: str, path: str, status: int, duration_seconds: float) -> None:
    """Registra uma request. `path` deve ser a rota-template (não a URL concreta)."""
    REQUEST_COUNT.labels(method=method, path=path, status=str(status)).inc()
    REQUEST_LATENCY.labels(method=method, path=path).observe(duration_seconds)


def render_latest() -> tuple[bytes, str]:
    """Retorna (payload, content_type) para o handler /metrics."""
    return generate_latest(), CONTENT_TYPE_LATEST
