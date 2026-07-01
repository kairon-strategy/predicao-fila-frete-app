"""Simulação de cenários — Monte Carlo simples sobre um frete-base."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from components import api_client
from components.sidebar import render_sidebar

st.set_page_config(page_title="Simulação • Kairon Frete", page_icon="🚚", layout="wide")

render_sidebar()

st.title("Simulação de cenários")
st.caption(
    "Rode uma simulação Monte Carlo sobre um frete-base e veja a distribuição "
    "de resultados (média e quantis P10/P50/P90)."
)

# --- Formulário -----------------------------------------------------------
with st.form("simulacao"):
    col1, col2 = st.columns(2)
    with col1:
        base_freight = st.number_input(
            "Frete-base (R$/t)",
            min_value=0.0,
            value=150.0,
            step=1.0,
        )
    with col2:
        iterations = st.slider(
            "Nº de iterações",
            min_value=100,
            max_value=10_000,
            value=1_000,
            step=100,
        )

    rodar = st.form_submit_button("Rodar", type="primary")

if rodar:
    try:
        resultado = api_client.simulate(float(base_freight), int(iterations))
    except api_client.ApiError as exc:
        st.error(f"Não foi possível rodar a simulação: {exc}")
    else:
        st.session_state["simulation"] = resultado

# --- Resultado ------------------------------------------------------------
resultado = st.session_state.get("simulation")
if resultado:
    st.divider()

    col_mean, col_p10, col_p50, col_p90 = st.columns(4)
    col_mean.metric("Média", f"R$ {resultado['mean']:,.2f} /t")
    col_p10.metric("P10", f"R$ {resultado['p10']:,.2f} /t")
    col_p50.metric("P50", f"R$ {resultado['p50']:,.2f} /t")
    col_p90.metric("P90", f"R$ {resultado['p90']:,.2f} /t")

    st.caption(f"Iterações: {resultado.get('iterations', '—')}")

    df = pd.DataFrame(
        {
            "quantil": ["P10", "P50", "P90", "Média"],
            "valor": [
                resultado["p10"],
                resultado["p50"],
                resultado["p90"],
                resultado["mean"],
            ],
        }
    )
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("quantil:N", sort=["P10", "P50", "P90", "Média"], title="Quantil"),
            y=alt.Y("valor:Q", title="Frete (R$/t)"),
            tooltip=["quantil", "valor"],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)

    note = resultado.get("note")
    if note:
        st.caption(note)
