"""Consulta de frete — formulário de predição e explicação."""

from __future__ import annotations

from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from components import api_client
from components.sidebar import render_sidebar

st.set_page_config(page_title="Consulta • Kairon Frete", page_icon="🚚", layout="wide")

render_sidebar()

st.title("Consulta de frete")
st.caption("Informe a rota e a carga para estimar o frete com banda de incerteza.")

PRODUTOS = ["ureia", "MAP", "KCl", "NPK", "algodão"]

# --- Formulário -----------------------------------------------------------
with st.form("consulta_frete"):
    col1, col2 = st.columns(2)
    with col1:
        origem = st.text_input("Origem", value="Sinop-MT")
        produto = st.selectbox("Produto", PRODUTOS, index=0)
        carga_ton = st.number_input("Carga (toneladas)", min_value=0.0, value=30.0, step=1.0)
    with col2:
        destino = st.text_input("Destino", value="Sorriso-MT")
        data = st.date_input("Data", value=date.today() + timedelta(days=30))

    enviado = st.form_submit_button("Consultar frete", type="primary")

if enviado:
    payload = {
        "origem": origem,
        "destino": destino,
        "produto": produto,
        "data": data.isoformat(),
        "carga_ton": float(carga_ton) if carga_ton else None,
    }
    try:
        resultado = api_client.predict(payload)
    except api_client.ApiError as exc:
        if exc.status_code == 403:
            st.error(
                "Seu perfil (viewer) não tem permissão para gerar predições. "
                "Faça login com um perfil analyst/admin ou use o modo anônimo."
            )
        else:
            st.error(f"Não foi possível consultar o frete: {exc}")
    else:
        # Guarda para permitir a explicação sem refazer a predição.
        st.session_state["prediction"] = resultado
        st.session_state["prediction_id"] = resultado["prediction_id"]
        # Nova predição invalida explicação anterior.
        st.session_state.pop("explanation", None)

# --- Resultado ------------------------------------------------------------
resultado = st.session_state.get("prediction")
if resultado:
    st.divider()

    frete = resultado["frete_r_per_ton"]
    p10 = resultado["banda_p10"]
    p90 = resultado["banda_p90"]

    col_metric, col_banda = st.columns([1, 2])
    with col_metric:
        st.metric("Frete estimado", f"R$ {frete:,.2f} /t")
    with col_banda:
        st.metric("Banda de incerteza (P10–P90)", f"R$ {p10:,.2f} — R$ {p90:,.2f} /t")

    st.caption(f"Versão do modelo: {resultado.get('model_version', 'n/d')}")

    # --- Drivers (SHAP) ---------------------------------------------------
    drivers = resultado.get("drivers", [])
    if drivers:
        st.subheader("Fatores que influenciam a predição")
        df = pd.DataFrame(drivers)

        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("shap_value:Q", title="Impacto (SHAP)"),
                y=alt.Y("feature:N", sort="-x", title="Fator"),
                color=alt.Color(
                    "direction:N",
                    title="Direção",
                    scale=alt.Scale(
                        domain=["up", "down"],
                        range=["#d62728", "#2ca02c"],
                    ),
                ),
                tooltip=["feature", "shap_value", "direction"],
            )
            .properties(height=max(120, 40 * len(df)))
        )
        st.altair_chart(chart, use_container_width=True)

        st.dataframe(
            df[["feature", "shap_value", "direction"]],
            hide_index=True,
            use_container_width=True,
        )

    # --- Explicação com copiloto -----------------------------------------
    st.divider()
    st.subheader("Copiloto")
    st.caption("Peça uma explicação em linguagem natural ou faça uma pergunta sobre a predição.")

    pergunta = st.text_input(
        "Pergunte ao copiloto",
        placeholder="Ex.: por que o frete está acima da média nesta rota?",
    )
    if st.button("Explicar com copiloto"):
        try:
            explicacao = api_client.explain(
                st.session_state["prediction_id"],
                question=pergunta or None,
            )
        except api_client.ApiError as exc:
            if exc.status_code == 403:
                st.error("Seu perfil não tem permissão para usar o copiloto.")
            else:
                st.error(f"Não foi possível gerar a explicação: {exc}")
        else:
            st.session_state["explanation"] = explicacao

    explicacao = st.session_state.get("explanation")
    if explicacao:
        st.write(explicacao["explanation"])
        fonte = "LLM" if explicacao.get("source") == "llm" else "modelo de template"
        st.caption(f"Fonte: {fonte}")
