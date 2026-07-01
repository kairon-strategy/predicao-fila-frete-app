"""Alertas — detecção, feed por severidade e resolução."""

from __future__ import annotations

import streamlit as st

from components import api_client
from components.sidebar import render_sidebar

st.set_page_config(page_title="Alertas • Kairon Frete", page_icon="🚚", layout="wide")

render_sidebar()

st.title("Alertas")
st.caption("Monitore desvios de frete e resolva alertas por severidade.")

SEVERIDADES = {"critical": "🔴 Crítico", "warn": "🟠 Atenção", "info": "🔵 Informativo"}

# --- Controles ------------------------------------------------------------
col_detect, col_sev, col_status = st.columns([1, 1, 1])

with col_detect:
    st.caption(" ")
    if st.button("Detectar agora", type="primary", use_container_width=True):
        try:
            resultado = api_client.detect_alerts()
        except api_client.ApiError as exc:
            if exc.status_code == 403:
                st.error("Seu perfil não tem permissão para disparar a detecção.")
            else:
                st.error(f"Falha na detecção: {exc}")
        else:
            criados = resultado.get("created", 0)
            st.success(
                f"Detecção concluída: {criados} alerta(s) criado(s). {resultado.get('detail', '')}"
            )

with col_sev:
    severidade_sel = st.selectbox(
        "Severidade",
        ["Todas", "critical", "warn", "info"],
        format_func=lambda s: "Todas" if s == "Todas" else SEVERIDADES.get(s, s),
    )
with col_status:
    status_sel = st.selectbox("Status", ["active", "resolved"], index=0)

severity = None if severidade_sel == "Todas" else severidade_sel

# --- Feed -----------------------------------------------------------------
st.divider()

try:
    alertas = api_client.get_alerts(severity=severity, status=status_sel)
except api_client.ApiError as exc:
    st.error(f"Não foi possível carregar os alertas: {exc}")
    st.stop()

if not alertas:
    st.info("Nenhum alerta para os filtros selecionados.")
    st.stop()

for alerta in alertas:
    sev = alerta.get("severity", "info")
    titulo = f"{SEVERIDADES.get(sev, sev)} · {alerta.get('title', 'Alerta')}"

    with st.container(border=True):
        # Cor por severidade via alert boxes nativos do Streamlit.
        if sev == "critical":
            st.error(titulo)
        elif sev == "warn":
            st.warning(titulo)
        else:
            st.info(titulo)

        st.write(alerta.get("body", ""))
        st.caption(
            f"Tipo: {alerta.get('alert_type', 'n/d')} · "
            f"Entidade: {alerta.get('entity_id', 'n/d')} · "
            f"Criado em: {alerta.get('created_at', 'n/d')}"
        )

        if alerta.get("status") == "active":
            if st.button("Resolver", key=f"resolve_{alerta['id']}"):
                try:
                    api_client.resolve_alert(alerta["id"])
                except api_client.ApiError as exc:
                    st.error(f"Não foi possível resolver: {exc}")
                else:
                    st.rerun()
        elif alerta.get("resolved_at"):
            st.caption(f"Resolvido em: {alerta['resolved_at']}")
