"""FastAPI app factory — monta todos os routers dos bounded contexts.

Este é o único ponto que "conhece" todos os contexts (é o deploy único do
monólito modular, ADR-008). Cada context expõe um `router` que é montado aqui.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

# Registra TODAS as tabelas ORM na metadata no boot. Sem isso, FKs entre contexts
# (ex: predictions.tenant_id -> tenants) não resolvem, pois cada router importa só
# o seu próprio modelo. Imports com efeito colateral (registram no Base.metadata).
import kairon.alerts.models  # noqa: E402,F401
import kairon.audit.models  # noqa: E402,F401
import kairon.explanation.models  # noqa: E402,F401
import kairon.ingestion.anp.models  # noqa: E402,F401
import kairon.knowledge.models  # noqa: E402,F401
import kairon.prediction.db_models  # noqa: E402,F401
import kairon.tenant.models  # noqa: E402,F401
from kairon import __version__
from kairon.core.database import check_database
from kairon.core.exceptions import KaironError
from kairon.core.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log.info("app.startup", version=__version__)
    yield
    log.info("app.shutdown")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Kairon Frete API",
        version=__version__,
        description="Predição de frete rodoviário agro. Baseline + LightGBM + SHAP.",
        lifespan=lifespan,
    )

    _register_cors(app)
    _register_middleware(app)
    _register_exception_handlers(app)
    _register_health(app)
    _register_metrics(app)
    _register_routers(app)
    return app


def _register_cors(app: FastAPI) -> None:
    from fastapi.middleware.cors import CORSMiddleware

    from kairon.core.config import settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Headers que o JS do browser pode LER (CORS esconde os demais). Retry-After
        # no 429 do login precisa ser legível para o front mostrar "tente em X min".
        expose_headers=["Retry-After"],
    )


def _register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation_and_logging(request: Request, call_next):  # type: ignore[no-untyped-def]
        # correlation-id: reaproveita header do cliente ou gera um novo.
        correlation_id = request.headers.get("x-correlation-id", str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
        # rota-template (não a URL concreta) evita explosão de cardinalidade no /metrics.
        route = request.scope.get("route")
        path_label = getattr(route, "path", request.url.path)
        from kairon.core import metrics

        metrics.observe(
            method=request.method,
            path=path_label,
            status=response.status_code,
            duration_seconds=duration_ms / 1000,
        )
        log.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["x-correlation-id"] = correlation_id
        structlog.contextvars.clear_contextvars()
        return response


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(KaironError)
    async def kairon_error_handler(_: Request, exc: KaironError) -> JSONResponse:
        log.warning("domain.error", error_code=exc.error_code, message=exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error_code, "message": exc.message, "details": exc.details},
        )


def _register_health(app: FastAPI) -> None:
    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        """Liveness: o processo está de pé? (não checa dependências)."""
        return {"status": "ok", "version": __version__}

    @app.get("/ready", tags=["ops"])
    async def ready() -> JSONResponse:
        """Readiness: Postgres responde? (LLM é informativo — degrada p/ template)."""
        from kairon.explanation.claude_client import get_client

        db_ok = await check_database()
        llm_configured = get_client().is_enabled
        return JSONResponse(
            status_code=200 if db_ok else 503,
            content={"ready": db_ok, "postgres": db_ok, "llm_configured": llm_configured},
        )


def _register_metrics(app: FastAPI) -> None:
    @app.get("/metrics", tags=["ops"], include_in_schema=False)
    async def metrics_endpoint() -> Response:
        from kairon.core import metrics

        payload, content_type = metrics.render_latest()
        return Response(content=payload, media_type=content_type)


def _register_routers(app: FastAPI) -> None:
    """Importes locais: mantêm o boot resiliente e evitam ciclos de import."""
    from kairon.alerts.router import router as alerts_router
    from kairon.explanation.config_router import router as copilot_config_router
    from kairon.explanation.router import router as explanation_router
    from kairon.knowledge.router import router as knowledge_router
    from kairon.prediction.router import router as prediction_router
    from kairon.simulation.router import router as simulation_router
    from kairon.tenant.router import router as tenant_router

    app.include_router(tenant_router, prefix="/v1")
    app.include_router(prediction_router, prefix="/v1", tags=["prediction"])
    app.include_router(explanation_router, prefix="/v1", tags=["explanation"])
    app.include_router(copilot_config_router, prefix="/v1")
    app.include_router(knowledge_router, prefix="/v1", tags=["knowledge"])
    app.include_router(simulation_router, prefix="/v1", tags=["simulation"])
    app.include_router(alerts_router, prefix="/v1")


app = create_app()
