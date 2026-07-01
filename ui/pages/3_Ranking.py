"""Ranking de rotas — tabela comparativa e histórico mensal."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from components import api_client
from components.sidebar import render_sidebar

st.set_page_config(page_title="Ranking • Kairon Frete", page_icon="🚚", layout="wide")

render_sidebar()

st.title("Ranking de rotas")
st.caption("Compare rotas por frete, eficiência (R$/t·km) e volatilidade.")

PRODUTOS = ["Todos", "ureia", "MAP", "KCl", "NPK", "algodão"]

# --- Filtros --------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    produto_sel = st.selectbox("Produto", PRODUTOS, index=0)
with col2:
    corredor = st.text_input("Corredor (opcional)", placeholder="Ex.: Norte")

produto = None if produto_sel == "Todos" else produto_sel

try:
    rotas = api_client.get_routes(produto=produto, corredor=corredor or None)
except api_client.ApiError as exc:
    st.error(f"Não foi possível carregar as rotas: {exc}")
    st.stop()

if not rotas:
    st.info("Nenhuma rota encontrada para os filtros selecionados.")
    st.stop()

# --- Tabela ---------------------------------------------------------------
df = pd.DataFrame(rotas)
df["rota"] = df["origem"] + " → " + df["destino"]

tabela = df[
    [
        "rota",
        "produto",
        "corredor",
        "distancia_km",
        "frete_r_per_ton",
        "r_per_ton_km",
        "banda_p10",
        "banda_p90",
        "var_30d_pct",
        "mape",
    ]
].rename(
    columns={
        "rota": "Rota",
        "produto": "Produto",
        "corredor": "Corredor",
        "distancia_km": "Dist. (km)",
        "frete_r_per_ton": "R$/t",
        "r_per_ton_km": "R$/t·km",
        "banda_p10": "P10",
        "banda_p90": "P90",
        "var_30d_pct": "Var. 30d (%)",
        "mape": "MAPE",
    }
)
st.dataframe(tabela, hide_index=True, use_container_width=True)

# --- Histórico da rota ----------------------------------------------------
st.divider()
st.subheader("Histórico mensal")

opcoes = {row["route_id"]: row["rota"] for _, row in df.iterrows()}
route_id = st.selectbox(
    "Selecione uma rota",
    options=list(opcoes.keys()),
    format_func=lambda rid: opcoes[rid],
)

if route_id:
    try:
        historico = api_client.get_route_history(route_id)
    except api_client.ApiError as exc:
        st.error(f"Não foi possível carregar o histórico: {exc}")
        st.stop()

    points = historico.get("points", [])
    if not points:
        st.info("Sem histórico disponível para esta rota.")
    else:
        hist_df = pd.DataFrame(points)
        chart = (
            alt.Chart(hist_df)
            .mark_line(point=True)
            .encode(
                x=alt.X("month:N", title="Mês"),
                y=alt.Y("frete_r_per_ton:Q", title="Frete (R$/t)"),
                tooltip=["month", "frete_r_per_ton", "banda_p10", "banda_p90"],
            )
            .properties(height=340)
        )
        st.altair_chart(chart, use_container_width=True)

        note = historico.get("note")
        if note:
            st.caption(note)
