"""Kairon Frete — página inicial da UI Streamlit."""

from __future__ import annotations

import streamlit as st

from components.sidebar import render_sidebar

st.set_page_config(
    page_title="Kairon Frete",
    page_icon="🚚",
    layout="wide",
)

render_sidebar()

st.title("🚚 Kairon Frete")
st.subheader("Predição de frete rodoviário para o agronegócio")

st.markdown(
    """
    O **Kairon Frete** estima o valor do frete rodoviário agro (R$/tonelada)
    com **banda de incerteza** (P10–P90) e **explicabilidade** dos fatores que
    influenciam cada predição. Assim, times comerciais e de logística negociam
    com mais previsibilidade e transparência.
    """
)

st.info(
    "👈 Use o menu lateral para navegar: **Consulta**, **Simulação**, "
    "**Ranking** e **Alertas**. O login é opcional — sem login você navega "
    "no tenant demo. Dica: `admin@kairon.dev` / `demo1234`."
)

st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("#### 🔎 Consulta")
    st.caption("Estime o frete de uma rota com banda de incerteza e explicação.")
with col2:
    st.markdown("#### 🎲 Simulação")
    st.caption("Rode uma simulação Monte Carlo sobre um frete-base.")
with col3:
    st.markdown("#### 🏁 Ranking")
    st.caption("Compare rotas e veja a série histórica mensal.")
with col4:
    st.markdown("#### 🚨 Alertas")
    st.caption("Monitore desvios e resolva alertas por severidade.")
