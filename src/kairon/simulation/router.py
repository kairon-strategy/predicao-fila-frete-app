"""Router do context simulation. MVP: endpoint síncrono de Monte Carlo.

O Monte Carlo roda em milissegundos, então não há job assíncrono no MVP
(contrato job_id/polling entra na v2 se algum cenário ficar pesado).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from kairon.simulation.monte_carlo import SENSITIVITY, run_monte_carlo, simulate_segment
from kairon.tenant.auth import Principal, require_permission

router = APIRouter()

_sim_guard = require_permission("simulate:run")


class SimulateRequest(BaseModel):
    base_freight: float = Field(..., gt=0, description="Frete base (R$/t) a perturbar")
    iterations: int = Field(default=1000, ge=100, le=10000)


class SimulateResponse(BaseModel):
    mean: float
    p10: float
    p50: float
    p90: float
    iterations: int
    note: str


@router.post("/simulate", response_model=SimulateResponse, summary="Monte Carlo de frete (MVP)")
async def simulate_endpoint(
    request: SimulateRequest,
    _p: Principal = Depends(_sim_guard),
) -> SimulateResponse:
    result = run_monte_carlo(request.base_freight, iterations=request.iterations)
    return SimulateResponse(
        mean=result.mean,
        p10=result.p10,
        p50=result.p50,
        p90=result.p90,
        iterations=result.iterations,
        note="Cenário de fator único (diesel + sazonalidade).",
    )


# ---- Monte Carlo multi-driver por segmento (diesel · safra · piso ANTT) ----
class SegmentBase(BaseModel):
    segment: str = Field(..., description="fertilizante | algodão | grão")
    base_freight: float = Field(..., gt=0, description="Frete base R$/t do segmento")


class SimulateSegmentsRequest(BaseModel):
    # Premissas centrais (o valor dos sliders). Ex.: 0.20 = diesel +20%.
    diesel_pct: float = Field(default=0.0, ge=-0.10, le=0.30, description="Variação do diesel")
    safra_pct: float = Field(default=0.0, ge=-0.25, le=0.05, description="Variação da safra")
    piso_pct: float = Field(default=0.0, ge=0.0, le=0.15, description="Revisão do piso ANTT")
    iterations: int = Field(default=2000, ge=100, le=20000)
    bases: list[SegmentBase] = Field(default_factory=list)


class SegmentResult(BaseModel):
    segment: str
    base_freight: float
    mean: float
    p10: float
    p50: float
    p90: float
    delta_pct: float


class SimulateSegmentsResponse(BaseModel):
    iterations: int
    drivers: dict[str, float]
    segments: list[SegmentResult]


# Bases default por segmento (usadas se o cliente não enviar as do ranking).
_DEFAULT_BASES = {"fertilizante": 320.0, "algodão": 280.0, "grão": 300.0}


@router.post(
    "/simulate/segments",
    response_model=SimulateSegmentsResponse,
    summary="Monte Carlo por segmento (diesel · safra · piso ANTT)",
)
async def simulate_segments_endpoint(
    request: SimulateSegmentsRequest,
    _p: Principal = Depends(_sim_guard),
) -> SimulateSegmentsResponse:
    bases = {b.segment: b.base_freight for b in request.bases}
    results: list[SegmentResult] = []
    for i, segment in enumerate(SENSITIVITY):  # ordem fixa: fertilizante, algodão, grão
        base = bases.get(segment) or _DEFAULT_BASES[segment]
        sim = simulate_segment(
            segment,
            base,
            diesel_pct=request.diesel_pct,
            safra_pct=request.safra_pct,
            piso_pct=request.piso_pct,
            iterations=request.iterations,
            seed=42 + i,  # seeds distintos p/ não correlacionar os segmentos
        )
        results.append(SegmentResult(**sim.__dict__))
    return SimulateSegmentsResponse(
        iterations=request.iterations,
        drivers={
            "diesel_pct": request.diesel_pct,
            "safra_pct": request.safra_pct,
            "piso_pct": request.piso_pct,
        },
        segments=results,
    )
