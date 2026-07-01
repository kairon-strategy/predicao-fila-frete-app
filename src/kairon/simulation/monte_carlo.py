"""Monte Carlo de frete (stub funcional no MVP).

Roda N iterações perturbando diesel e sazonalidade em torno de um ponto base para
dar uma distribuição de cenários. A versão completa (v2) puxa distribuições reais
das séries históricas. Ver simulation/router.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_ITERATIONS = 1000


@dataclass(frozen=True)
class SimulationResult:
    mean: float
    p10: float
    p50: float
    p90: float
    iterations: int


def run_monte_carlo(
    base_freight: float,
    *,
    diesel_volatility: float = 0.08,
    seasonal_volatility: float = 0.05,
    iterations: int = DEFAULT_ITERATIONS,
    seed: int = 42,
) -> SimulationResult:
    """Perturba o frete base com choques log-normais independentes.

    seed fixo -> resultado reproduzível (importante para auditoria).
    """
    rng = np.random.default_rng(seed)
    diesel_shock = rng.normal(1.0, diesel_volatility, iterations)
    seasonal_shock = rng.normal(1.0, seasonal_volatility, iterations)
    samples = base_freight * diesel_shock * seasonal_shock

    return SimulationResult(
        mean=round(float(np.mean(samples)), 2),
        p10=round(float(np.percentile(samples, 10)), 2),
        p50=round(float(np.percentile(samples, 50)), 2),
        p90=round(float(np.percentile(samples, 90)), 2),
        iterations=iterations,
    )
