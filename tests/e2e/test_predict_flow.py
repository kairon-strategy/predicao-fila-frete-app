"""End-to-end tests over the real endpoints (DB-backed via the client fixture)."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.usefixtures("seed_route")

PREDICT_BODY = {
    "origem": "Sinop-MT",
    "destino": "Sorriso-MT",
    "produto": "ureia",
    "data": "2026-08-15",
    "carga_ton": 30,
}

# Absolute tolerance for the p10 <= frete <= p90 band assertion (rounding slack).
TOL = 0.5


async def test_predict_returns_valid_response(client: httpx.AsyncClient) -> None:
    resp = await client.post("/v1/predict", json=PREDICT_BODY, headers={"idempotency-key": "e2e-1"})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["frete_r_per_ton"] > 0
    assert body["banda_p10"] - TOL <= body["frete_r_per_ton"] <= body["banda_p90"] + TOL

    drivers = body["drivers"]
    assert isinstance(drivers, list) and len(drivers) > 0
    for d in drivers:
        assert "feature" in d
        assert "shap_value" in d
        assert d["direction"] in ("up", "down")

    assert body["model_version"]
    assert body["prediction_id"]


async def test_predict_missing_idempotency_key_is_422(client: httpx.AsyncClient) -> None:
    resp = await client.post("/v1/predict", json=PREDICT_BODY)
    assert resp.status_code == 422, resp.text


async def test_predict_is_idempotent(client: httpx.AsyncClient) -> None:
    headers = {"idempotency-key": "e2e-idem"}
    first = await client.post("/v1/predict", json=PREDICT_BODY, headers=headers)
    second = await client.post("/v1/predict", json=PREDICT_BODY, headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["prediction_id"] == second.json()["prediction_id"]


async def test_explain_after_predict(client: httpx.AsyncClient) -> None:
    pred = await client.post(
        "/v1/predict", json=PREDICT_BODY, headers={"idempotency-key": "e2e-explain"}
    )
    assert pred.status_code == 200, pred.text
    pred_body = pred.json()
    prediction_id = pred_body["prediction_id"]

    resp = await client.post("/v1/explain", json={"prediction_id": prediction_id})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["source"] == "template"
    explanation = body["explanation"]
    assert ("Sinop-MT" in explanation) or ("Sorriso-MT" in explanation)
    # The freight value (2 decimals) must appear in the explanation text.
    assert f"{pred_body['frete_r_per_ton']:.2f}" in explanation


async def test_health_and_ready(client: httpx.AsyncClient) -> None:
    health = await client.get("/health")
    assert health.status_code == 200
    hbody = health.json()
    assert hbody["status"] == "ok"

    ready = await client.get("/ready")
    assert ready.status_code in (200, 503)
    rbody = ready.json()
    assert "postgres" in rbody
