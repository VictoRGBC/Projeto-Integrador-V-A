"""Filtros globais da aplicação."""
import streamlit as st


def aplicar_filtros(df_base):
    setores = sorted(df_base['SETOR'].dropna().unique().tolist())
    sel = st.sidebar.multiselect("Setor:", setores, default=setores)
    df = df_base[df_base['SETOR'].isin(sel)]
    tipos = sorted(df['TIPO_PROCESSO'].dropna().unique().tolist())
    sel = st.sidebar.multiselect("Tipo de Processo:", tipos, default=tipos)
    df = df[df['TIPO_PROCESSO'].isin(sel)]
    analistas = sorted(df['RESPONSAVEL'].dropna().unique().tolist())
    sel = st.sidebar.multiselect("Responsável:", analistas, default=analistas)
    df = df[df['RESPONSAVEL'].isin(sel)]
    clientes = sorted(df['CLIENTE'].dropna().unique().tolist())
    sel = st.sidebar.multiselect("Cliente:", clientes, default=clientes)
    return df[df['CLIENTE'].isin(sel)]


def render_session_header():
    st.sidebar.title(f"Olá, {st.session_state.get('usuario_nome', 'Usuário')}!")
    st.sidebar.caption("Sessão Autenticada")
    if st.sidebar.button("🚪 Sair da Aplicação"):
        st.session_state.clear(); st.rerun()
