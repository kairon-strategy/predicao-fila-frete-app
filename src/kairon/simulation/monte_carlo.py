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


# --------------------------------------------------------------------------- #
# Monte Carlo multi-driver por segmento (diesel · safra · piso ANTT)
# --------------------------------------------------------------------------- #

# Segmentos do agro e os produtos que caem em cada um.
SEGMENTS: dict[str, set[str]] = {
    "fertilizante": {"ureia", "map", "kcl", "cloreto", "npk", "fertilizante", "nitrato"},
    "algodão": {"algodão", "algodao"},
    "grão": {"soja", "milho", "sorgo", "trigo", "grão", "grao"},
}

# Sensibilidade do frete a cada driver, POR SEGMENTO (quanto o frete varia por
# 1.0 de variação do driver). Diesel pesa em todos (combustível ~ custo direto).
# Safra move a DEMANDA de frete: forte nos grãos (escoamento), moderada no
# algodão, quase neutra/contracíclica no fertilizante (fluxo de entrada). Piso
# ANTT é regulatório e só empurra o frete para cima.
SENSITIVITY: dict[str, dict[str, float]] = {
    "fertilizante": {"diesel": 0.45, "safra": -0.10, "piso": 0.30},
    "algodão": {"diesel": 0.45, "safra": 0.25, "piso": 0.30},
    "grão": {"diesel": 0.50, "safra": 0.60, "piso": 0.25},
}

# Volatilidade (desvio) em torno da premissa central de cada driver.
_VOL = {"diesel": 0.06, "safra": 0.08, "piso": 0.03}


@dataclass(frozen=True)
class SegmentSimulation:
    segment: str
    base_freight: float
    mean: float
    p10: float
    p50: float
    p90: float
    delta_pct: float  # variação da média vs base_freight


def segment_of(produto: str) -> str | None:
    p = produto.strip().lower()
    for seg, produtos in SEGMENTS.items():
        if p in produtos:
            return seg
    return None


def simulate_segment(
    segment: str,
    base_freight: float,
    *,
    diesel_pct: float,
    safra_pct: float,
    piso_pct: float,
    iterations: int = DEFAULT_ITERATIONS,
    seed: int = 42,
) -> SegmentSimulation:
    """Distribuição de frete de um segmento sob premissas de diesel/safra/piso.

    Cada driver é amostrado como uma normal em torno da premissa central (o valor
    do slider), com volatilidade própria; a sensibilidade do segmento traduz a
    variação do driver em variação de frete. O piso ANTT só sobe (clip >= 0) e o
    resultado nunca fica abaixo do piso regulatório (frete não cai indefinidamente).
    """
    sens = SENSITIVITY.get(segment, SENSITIVITY["fertilizante"])
    rng = np.random.default_rng(seed)
    diesel = rng.normal(diesel_pct, _VOL["diesel"], iterations)
    safra = rng.normal(safra_pct, _VOL["safra"], iterations)
    piso = np.clip(rng.normal(piso_pct, _VOL["piso"], iterations), 0.0, None)

    mult = 1.0 + sens["diesel"] * diesel + sens["safra"] * safra + sens["piso"] * piso
    # frete não vai abaixo de 80% do base (piso regulatório amortece a queda).
    samples = base_freight * np.maximum(mult, 0.80)

    mean = float(np.mean(samples))
    return SegmentSimulation(
        segment=segment,
        base_freight=round(base_freight, 2),
        mean=round(mean, 2),
        p10=round(float(np.percentile(samples, 10)), 2),
        p50=round(float(np.percentile(samples, 50)), 2),
        p90=round(float(np.percentile(samples, 90)), 2),
        delta_pct=round((mean - base_freight) / base_freight * 100, 2) if base_freight else 0.0,
    )
