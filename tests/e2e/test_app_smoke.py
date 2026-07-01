"""Light smoke test: the app boots and exposes the v1 routes. No DB required."""

from __future__ import annotations


def test_openapi_exposes_v1_paths() -> None:
    from kairon.main import create_app

    app = create_app()
    schema = app.openapi()
    paths = schema["paths"]

    assert "/v1/predict" in paths
    assert "/v1/explain" in paths
    assert "/v1/simulate" in paths
