"""Ponto de entrada e composição do dashboard."""
import datetime
import logging
import streamlit as st
from services.process_service import carregar_dados_processos
from views.login import render_login
from views.sidebar import aplicar_filtros, render_session_header
from views.kpis import render_kpis
from views.tab_overview import render_overview
from views.tab_sla import render_sla
from views.tab_esteira import render_esteira
from views.tab_equipe import render_equipe
from views.tab_segmentados import render_segmentados

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
st.set_page_config(page_title='Dashboard Executivo | Gestão de Processos & SLA', page_icon='📊', layout='wide', initial_sidebar_state='expanded')


def main():
    if 'autenticado' not in st.session_state: st.session_state['autenticado']=False
    if not st.session_state['autenticado']:
        render_login(); return
    render_session_header()
    st.sidebar.markdown('---'); st.sidebar.subheader('📅 Período de Abertura')
    hoje=datetime.date.today(); inicio_padrao=hoje-datetime.timedelta(days=30)
    data_inicio=st.sidebar.date_input('Data Inicial',inicio_padrao)
    data_fim=st.sidebar.date_input('Data Final',hoje)
    with st.spinner('Consultando banco Firebird...'):
        df_base=carregar_dados_processos(data_inicio,data_fim)
    if df_base.empty:
        st.warning('Nenhum processo foi localizado no banco de dados para o intervalo selecionado.'); return
    st.sidebar.markdown('---'); st.sidebar.subheader('🎯 Dimensões de Negócio')
    df_filtrado=aplicar_filtros(df_base)
    if df_filtrado.empty:
        st.info('Nenhum registro corresponde à combinação de filtros selecionada. Ajuste os filtros na barra lateral.')
    render_kpis(df_filtrado)
    aba1,aba2,aba3,aba4,aba5=st.tabs(['📈 Visão Geral & Tendências','🚨 Status & Performance de SLA','🔗 Esteira de Produção','👥 Produtividade da Equipe','🎯 KPIs Segmentados'])
    with aba1: render_overview(df_filtrado,data_inicio,data_fim)
    with aba2: render_sla(df_filtrado,data_inicio,data_fim)
    with aba3: render_esteira(df_filtrado,data_inicio,data_fim)
    with aba4: render_equipe(df_filtrado,data_inicio,data_fim)
    with aba5: render_segmentados(df_filtrado,data_inicio,data_fim)

if __name__ == '__main__': main()
