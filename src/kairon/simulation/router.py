"""Router do context simulation. MVP: endpoint síncrono de Monte Carlo.

O Monte Carlo roda em milissegundos, então não há job assíncrono no MVP
(contrato job_id/polling entra na v2 se algum cenário ficar pesado).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from kairon.simulation.monte_carlo import run_monte_carlo

router = APIRouter()


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
async def simulate_endpoint(request: SimulateRequest) -> SimulateResponse:
    result = run_monte_carlo(request.base_freight, iterations=request.iterations)
    return SimulateResponse(
        mean=result.mean,
        p10=result.p10,
        p50=result.p50,
        p90=result.p90,
        iterations=result.iterations,
        note="Simulação em linguagem natural e multi-fator: disponível em set/2026.",
    )
