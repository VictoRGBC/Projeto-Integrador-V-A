"""Tela de login."""
import streamlit as st
from services.auth_service import autenticar_usuario


def render_login():
    st.title("🔐 Acesso ao Painel Executivo")
    st.markdown("Insira suas credenciais corporativas para prosseguir.")
    with st.form(key='form_login'):
        login = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar no Sistema")
    if entrar:
        sucesso, mensagem = autenticar_usuario(login, senha)
        if sucesso: st.rerun()
        else: st.error(mensagem)
