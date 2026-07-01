"""Cliente HTTP para a API do Kairon Frete.

Módulo enxuto usado pelas páginas Streamlit. Lê a URL base de KAIRON_API_URL
e expõe funções de alto nível para os endpoints da API.

O token de acesso, quando presente, fica em ``st.session_state["access_token"]``.
Requests sem token resolvem para o tenant demo (papel admin) — a UI é usável
sem login.
"""

from __future__ import annotations

import os
import uuid

import requests
import streamlit as st

API_URL = os.getenv("KAIRON_API_URL", "http://localhost:8000").rstrip("/")

# Timeout razoável para chamadas síncronas na UI (conexão, leitura).
TIMEOUT_SECONDS = 10


class ApiError(Exception):
    """Erro amigável para falhas de comunicação com a API.

    Expõe ``status_code`` (quando houver resposta HTTP) para a UI distinguir
    casos como 403 (RBAC) de falhas genéricas.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _extract_error_message(response: requests.Response) -> str:
    """Tenta extrair a mensagem de erro enviada pelo servidor."""
    try:
        body = response.json()
    except ValueError:
        return response.text or f"Erro HTTP {response.status_code}"

    if isinstance(body, dict):
        # FastAPI usa "detail"; aceitamos também "message"/"error".
        for key in ("detail", "message", "error"):
            value = body.get(key)
            if value:
                return value if isinstance(value, str) else str(value)
    return f"Erro HTTP {response.status_code}"


def _auth_headers(extra: dict | None = None) -> dict:
    """Monta os headers da requisição, injetando o Bearer se houver token."""
    headers: dict[str, str] = dict(extra or {})
    token = st.session_state.get("access_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request(
    method: str,
    path: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
    headers: dict | None = None,
) -> dict | list:
    url = f"{API_URL}{path}"
    try:
        response = requests.request(
            method,
            url,
            json=json,
            params=params,
            headers=_auth_headers(headers),
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise ApiError(
            f"Não foi possível conectar à API em {API_URL}. " "Verifique se o serviço está no ar."
        ) from exc

    if not response.ok:
        raise ApiError(_extract_error_message(response), status_code=response.status_code)

    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("A API retornou uma resposta inválida.") from exc


# --- Autenticação ---------------------------------------------------------
def login(email: str, password: str) -> dict:
    """Chama POST /v1/auth/login e retorna os tokens."""
    return _request("POST", "/v1/auth/login", json={"email": email, "password": password})


def me() -> dict:
    """Chama GET /v1/auth/me (requer token) e retorna dados do usuário."""
    return _request("GET", "/v1/auth/me")


# --- Predição e explicação ------------------------------------------------
def predict(payload: dict) -> dict:
    """Chama POST /v1/predict.

    Gera uma idempotency-key única (uuid4) por submissão e injeta o Bearer
    quando o usuário está logado.
    """
    headers = {"idempotency-key": str(uuid.uuid4())}
    return _request("POST", "/v1/predict", json=payload, headers=headers)


def explain(prediction_id: str, question: str | None = None) -> dict:
    """Chama POST /v1/explain para obter a explicação de uma predição."""
    return _request(
        "POST",
        "/v1/explain",
        json={"prediction_id": prediction_id, "question": question},
    )


# --- Rotas e histórico ----------------------------------------------------
def get_routes(produto: str | None = None, corredor: str | None = None) -> list:
    """Chama GET /v1/routes com filtros opcionais."""
    params = {}
    if produto:
        params["produto"] = produto
    if corredor:
        params["corredor"] = corredor
    return _request("GET", "/v1/routes", params=params)


def get_route_history(route_id: str, months: int = 12) -> dict:
    """Chama GET /v1/routes/{route_id}/history."""
    return _request("GET", f"/v1/routes/{route_id}/history", params={"months": months})


# --- Simulação ------------------------------------------------------------
def simulate(base_freight: float, iterations: int) -> dict:
    """Chama POST /v1/simulate (Monte Carlo simples)."""
    return _request(
        "POST",
        "/v1/simulate",
        json={"base_freight": base_freight, "iterations": iterations},
    )


# --- Alertas --------------------------------------------------------------
def get_alerts(
    severity: str | None = None,
    alert_type: str | None = None,
    status: str | None = "active",
) -> list:
    """Chama GET /v1/alerts com filtros opcionais."""
    params = {}
    if severity:
        params["severity"] = severity
    if alert_type:
        params["type"] = alert_type
    if status:
        params["status"] = status
    return _request("GET", "/v1/alerts", params=params)


def resolve_alert(alert_id: str) -> dict:
    """Chama POST /v1/alerts/{id}/resolve."""
    return _request("POST", f"/v1/alerts/{alert_id}/resolve")


def detect_alerts() -> dict:
    """Chama POST /v1/alerts/detect e retorna {"created", "detail"}."""
    return _request("POST", "/v1/alerts/detect")


# --- Saúde ----------------------------------------------------------------
def health() -> bool:
    """Consulta GET /health. Retorna True se saudável, False caso contrário.

    Nunca levanta exceção: usada apenas como indicador visual.
    """
    try:
        response = requests.get(f"{API_URL}/health", timeout=TIMEOUT_SECONDS)
        return response.ok
    except requests.RequestException:
        return False
