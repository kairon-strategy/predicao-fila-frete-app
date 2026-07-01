"""Sidebar compartilhada: login opcional e status da API.

Renderizada em todas as páginas para manter sessão e saúde da API visíveis.
O token fica em ``st.session_state["access_token"]``; requests sem token
resolvem para o tenant demo (papel admin).
"""

from __future__ import annotations

import streamlit as st

from components import api_client


def _load_current_user() -> dict | None:
    """Retorna os dados do usuário logado (cacheados na sessão) ou None."""
    if "access_token" not in st.session_state:
        return None
    user = st.session_state.get("current_user")
    if user is not None:
        return user
    try:
        user = api_client.me()
    except api_client.ApiError:
        # Token inválido/expirado: descarta e cai para o modo anônimo.
        st.session_state.pop("access_token", None)
        st.session_state.pop("current_user", None)
        return None
    st.session_state["current_user"] = user
    return user


def render_sidebar() -> None:
    """Desenha o bloco de autenticação e o indicador de saúde da API."""
    with st.sidebar:
        st.markdown("### Sessão")
        user = _load_current_user()

        if user:
            st.success(f"Logado: {user.get('email', '—')}")
            st.caption(f"Papel: {user.get('role', 'n/d')} · tenant: {user.get('tenant_id', 'n/d')}")
            if st.button("Sair", use_container_width=True):
                st.session_state.pop("access_token", None)
                st.session_state.pop("current_user", None)
                st.rerun()
        else:
            st.caption("Anônimo (tenant demo)")
            with st.form("login_form", clear_on_submit=False):
                email = st.text_input("E-mail", placeholder="admin@kairon.dev")
                password = st.text_input("Senha", type="password", placeholder="demo1234")
                if st.form_submit_button("Entrar", use_container_width=True):
                    _do_login(email, password)

        st.divider()
        st.caption("Status da API")
        # Degrada com elegância: health-check indisponível nunca quebra a página.
        if api_client.health():
            st.success("Online")
        else:
            st.warning("Indisponível")
        st.caption(api_client.API_URL)


def _do_login(email: str, password: str) -> None:
    if not email or not password:
        st.warning("Informe e-mail e senha.")
        return
    try:
        tokens = api_client.login(email, password)
    except api_client.ApiError as exc:
        st.error(f"Falha no login: {exc}")
        return
    st.session_state["access_token"] = tokens["access_token"]
    st.session_state.pop("current_user", None)
    st.rerun()
