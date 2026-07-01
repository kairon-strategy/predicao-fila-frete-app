"""Testes do Monte Carlo stub."""

from __future__ import annotations

from kairon.simulation.monte_carlo import run_monte_carlo


def test_monte_carlo_ordena_quantis() -> None:
    r = run_monte_carlo(150.0, iterations=2000)
    assert r.p10 < r.p50 < r.p90
    assert 140 < r.mean < 160  # perto do base com pouca volatilidade


def test_monte_carlo_reproduzivel() -> None:
    a = run_monte_carlo(200.0, seed=7)
    b = run_monte_carlo(200.0, seed=7)
    assert a == b
