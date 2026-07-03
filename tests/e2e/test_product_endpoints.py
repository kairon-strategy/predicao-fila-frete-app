"""E2E dos endpoints P0 de produto: ranking, histórico, explain-com-pergunta,
simulate assíncrono e /metrics."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

pytestmark = pytest.mark.usefixtures("seed_route")


@pytest_asyncio.fixture
async def client(auth_client: httpx.AsyncClient) -> httpx.AsyncClient:
    """Endpoints protegidos: usa o client autenticado (admin, tenant default)."""
    return auth_client


async def _first_prediction_id(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        "/v1/predict",
        headers={"idempotency-key": "prod-1"},
        json={
            "origem": "Sinop-MT",
            "destino": "Sorriso-MT",
            "produto": "ureia",
            "data": "2026-08-15",
            "carga_ton": 30,
        },
    )
    assert resp.status_code == 200
    return resp.json()["prediction_id"]


async def test_ranking_lists_routes(client: httpx.AsyncClient) -> None:
    resp = await client.get("/v1/routes")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    item = items[0]
    for key in ("route_id", "origem", "destino", "frete_r_per_ton", "r_per_ton_km", "var_30d_pct"):
        assert key in item
    assert item["frete_r_per_ton"] > 0
    assert item["mape"] is None  # honesto: MAPE real ainda não implementado (US-094)


async def test_ranking_filter_by_produto(client: httpx.AsyncClient) -> None:
    resp = await client.get("/v1/routes", params={"produto": "ureia"})
    assert resp.status_code == 200
    assert all(i["produto"].lower() == "ureia" for i in resp.json())
    # filtro que não casa nada retorna lista vazia
    empty = await client.get("/v1/routes", params={"produto": "inexistente-xyz"})
    assert empty.status_code == 200 and empty.json() == []


async def test_route_history(client: httpx.AsyncClient) -> None:
    route_id = (await client.get("/v1/routes")).json()[0]["route_id"]
    resp = await client.get(f"/v1/routes/{route_id}/history", params={"months": 6})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["points"]) == 6
    assert all(p["banda_p10"] <= p["frete_r_per_ton"] + 0.01 for p in body["points"])
    assert "modelo" in body["note"].lower()


async def test_route_history_unknown_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/v1/routes/not-a-uuid/history")
    assert resp.status_code == 404


async def test_explain_with_question(client: httpx.AsyncClient) -> None:
    pid = await _first_prediction_id(client)
    resp = await client.post(
        "/v1/explain",
        json={"prediction_id": pid, "question": "Por que o frete está nesse nível?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "template"  # sem ANTHROPIC_API_KEY nos testes
    # cita a rota e o valor (guardrail passou)
    assert "Sinop-MT" in body["explanation"] or "Sorriso-MT" in body["explanation"]


async def test_simulate_sync(client: httpx.AsyncClient) -> None:
    resp = await client.post("/v1/simulate", json={"base_freight": 150, "iterations": 500})
    assert resp.status_code == 200
    body = resp.json()
    assert body["p10"] < body["p90"]


async def test_metrics_endpoint(client: httpx.AsyncClient) -> None:
    # gera ao menos uma request para popular o contador
    await client.get("/health")
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "kairon_http_requests_total" in resp.text
