"""View modularizada."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

def render_equipe(df_filtrado, data_inicio=None, data_fim=None):
    st.subheader("Produtividade e Velocidade por Analista")
    st.caption("Visão individualizada do volume de entregas, tamanho do backlog e velocidade média de execução por responsável.")

    df_perf = df_filtrado.groupby('RESPONSAVEL').agg(
        TOTAL_DEMANDAS=('ID_PROCESSO', 'count'),
        EM_ANDAMENTO=('DATA_FINALIZACAO', lambda x: x.isnull().sum()),
        CONCLUIDAS=('DATA_FINALIZACAO', lambda x: x.notnull().sum()),
        ATRASADAS=('ATRASADO', 'sum'),
        TMR_MEDIO_DIAS=('LEAD_TIME_DIAS', 'mean')
    ).reset_index()

    # Antes o `dropna(subset=['RESPONSAVEL'])` descartava demandas sem
    # responsável; agora elas aparecem sob "Não informado" (ver
    # fillna aplicado em carregar_dados_processos), tornando visível
    # o volume de demandas sem atribuição.
    df_perf = df_perf[df_perf['TOTAL_DEMANDAS'] > 0]
    df_perf['TMR_MEDIO_DIAS'] = df_perf['TMR_MEDIO_DIAS'].round(1)

    st.dataframe(
        df_perf.sort_values('TOTAL_DEMANDAS', ascending=False),
        column_config={
            "RESPONSAVEL": "Analista / Responsável",
            "TOTAL_DEMANDAS": "Total Atribuído",
            "EM_ANDAMENTO": "Fila Atual (WIP)",
            "CONCLUIDAS": "Entregas Realizadas",
            "ATRASADAS": "Demandas em Atraso",
            "TMR_MEDIO_DIAS": st.column_config.NumberColumn("Lead Time Médio (Dias)", format="%.1f")
        },
        hide_index=True,
        use_container_width=True
    )

    st.divider()
    col_perf1, col_perf2 = st.columns(2)

    with col_perf1:
        st.markdown("**Volume de Entregas por Analista**")
        fig_entregas = px.bar(
            df_perf.sort_values('CONCLUIDAS', ascending=True),
            x='CONCLUIDAS', y='RESPONSAVEL', orientation='h',
            labels={'CONCLUIDAS': 'Processos Finalizados', 'RESPONSAVEL': ''},
            template='plotly_white'
        )
        st.plotly_chart(fig_entregas, use_container_width=True)

    with col_perf2:
        st.markdown("**Tempo Médio de Resolução (Lead Time) por Analista**")
        fig_tmr = px.bar(
            df_perf.sort_values('TMR_MEDIO_DIAS', ascending=True),
            x='TMR_MEDIO_DIAS', y='RESPONSAVEL', orientation='h',
            labels={'TMR_MEDIO_DIAS': 'Média de Dias', 'RESPONSAVEL': ''},
            color='TMR_MEDIO_DIAS',
            color_continuous_scale='Reds',
            template='plotly_white'
        )
        fig_tmr.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_tmr, use_container_width=True)

    # ------------------------------------------------------------------
    # ANÁLISES ADICIONAIS DE PRODUTIVIDADE
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("📊 Análises Avançadas de Capacidade e Performance")

    df_perf['TAXA_CONCLUSAO'] = np.where(
        df_perf['TOTAL_DEMANDAS'] > 0,
        (df_perf['CONCLUIDAS'] / df_perf['TOTAL_DEMANDAS']) * 100,
        0
    )
    df_perf['TAXA_ATRASO'] = np.where(
        df_perf['TOTAL_DEMANDAS'] > 0,
        (df_perf['ATRASADAS'] / df_perf['TOTAL_DEMANDAS']) * 100,
        0
    )

    col_perf3, col_perf4 = st.columns(2)

    with col_perf3:
        st.markdown("**Taxa de Conclusão por Analista**")
        df_conclusao = df_perf.sort_values('TAXA_CONCLUSAO', ascending=True)
        fig_conclusao = px.bar(
            df_conclusao, x='TAXA_CONCLUSAO', y='RESPONSAVEL',
            orientation='h', text='TAXA_CONCLUSAO',
            labels={'TAXA_CONCLUSAO': 'Taxa de Conclusão (%)', 'RESPONSAVEL': ''},
            template='plotly_white'
        )
        fig_conclusao.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_conclusao.update_xaxes(range=[0, max(100, float(df_conclusao['TAXA_CONCLUSAO'].max()) + 5)])
        st.plotly_chart(fig_conclusao, use_container_width=True)

    with col_perf4:
        st.markdown("**Taxa de Atraso por Analista**")
        df_atraso = df_perf.sort_values('TAXA_ATRASO', ascending=True)
        fig_atraso = px.bar(
            df_atraso, x='TAXA_ATRASO', y='RESPONSAVEL',
            orientation='h', text='TAXA_ATRASO',
            labels={'TAXA_ATRASO': 'Taxa de Atraso (%)', 'RESPONSAVEL': ''},
            template='plotly_white'
        )
        fig_atraso.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_atraso.update_xaxes(range=[0, max(100, float(df_atraso['TAXA_ATRASO'].max()) + 5)])
        st.plotly_chart(fig_atraso, use_container_width=True)

    col_perf5, col_perf6 = st.columns(2)

    with col_perf5:
        st.markdown("**Carga de Trabalho: WIP vs. Entregas**")
        fig_wip_entregas = px.scatter(
            df_perf,
            x='EM_ANDAMENTO', y='CONCLUIDAS', size='TOTAL_DEMANDAS',
            color='TAXA_ATRASO', hover_name='RESPONSAVEL',
            hover_data={'TOTAL_DEMANDAS': True, 'TAXA_CONCLUSAO': ':.1f',
                        'TAXA_ATRASO': ':.1f', 'TMR_MEDIO_DIAS': ':.1f'},
            labels={'EM_ANDAMENTO': 'Demandas em Andamento (WIP)',
                    'CONCLUIDAS': 'Demandas Concluídas',
                    'TAXA_ATRASO': 'Taxa de Atraso (%)'},
            color_continuous_scale='RdYlGn_r',
            template='plotly_white'
        )
        fig_wip_entregas.add_hline(
            y=df_perf['CONCLUIDAS'].mean(),
            line_dash='dot',
            annotation_text='Média de conclusões'
        )
        fig_wip_entregas.add_vline(
            x=df_perf['EM_ANDAMENTO'].mean(),
            line_dash='dot',
            annotation_text='Média de WIP'
        )
        st.plotly_chart(fig_wip_entregas, use_container_width=True)

    with col_perf6:
        st.markdown("**Volume Atribuído x Lead Time Médio**")
        fig_volume_tmr = px.scatter(
            df_perf,
            x='TOTAL_DEMANDAS', y='TMR_MEDIO_DIAS', size='CONCLUIDAS',
            color='TAXA_ATRASO', hover_name='RESPONSAVEL',
            hover_data={'TOTAL_DEMANDAS': True, 'CONCLUIDAS': True,
                        'EM_ANDAMENTO': True, 'TAXA_CONCLUSAO': ':.1f',
                        'TAXA_ATRASO': ':.1f'},
            labels={'TOTAL_DEMANDAS': 'Demandas Atribuídas',
                    'TMR_MEDIO_DIAS': 'Lead Time Médio (dias)',
                    'TAXA_ATRASO': 'Taxa de Atraso (%)'},
            color_continuous_scale='Reds',
            template='plotly_white'
        )
        fig_volume_tmr.add_hline(
            y=df_perf['TMR_MEDIO_DIAS'].mean(),
            line_dash='dot',
            annotation_text='Lead Time médio da equipe'
        )
        st.plotly_chart(fig_volume_tmr, use_container_width=True)

    df_perf['INDICE_EQUILIBRIO'] = df_perf['TAXA_CONCLUSAO'] - df_perf['TAXA_ATRASO']
    df_ranking = df_perf.sort_values(
        ['INDICE_EQUILIBRIO', 'CONCLUIDAS'],
        ascending=[False, False]
    )

    st.markdown("**Ranking de Equilíbrio Operacional**")
    fig_ranking = px.bar(
        df_ranking, x='INDICE_EQUILIBRIO', y='RESPONSAVEL',
        orientation='h', text='INDICE_EQUILIBRIO',
        labels={'INDICE_EQUILIBRIO': 'Conclusão - Atraso (p.p.)', 'RESPONSAVEL': ''},
        color='INDICE_EQUILIBRIO',
        color_continuous_scale='RdYlGn',
        template='plotly_white'
    )
    fig_ranking.update_traces(texttemplate='%{text:.1f}', textposition='outside')
    fig_ranking.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig_ranking, use_container_width=True)

    with st.expander("📌 **Como interpretar as análises avançadas da equipe**"):
        st.markdown("""
        * **Taxa de Conclusão:** percentual da carteira atribuída que foi finalizada.
        * **Taxa de Atraso:** percentual da carteira classificada como atrasada.
        * **WIP vs. Entregas:** WIP alto combinado com poucas entregas pode indicar sobrecarga ou bloqueios.
        * **Volume x Lead Time:** ajuda a separar alta carga operacional de baixa velocidade ou maior complexidade.
        * **Ranking de Equilíbrio:** combina conclusão e atraso e deve ser usado como apoio gerencial.
        """)

    with st.expander("📌 **Pontos Importantes sobre a Produtividade da Equipe**"):
        st.markdown("""
        * **Alto Volume de Entregas + Lead Time Baixo:**
          - Indica analistas de alta performance ou atrabalhados em demandas de baixa complexidade. Devem servir como referência operacional para a equipe.
        * **Alto Volume em Andamento (WIP) + Muitas Demandas em Atraso:**
          - **Risco:** O analista está sobrecarregado ou acumulando tarefas sem concluir o que começou.
          - **Ação de Gestão:** Limitar a quantidade de chamados simultâneos por analista (*WIP Limit*) e redistribuir chamados.
        * **Lead Time desproporcionalmente alto em relação à média dos colegas:**
          - Investigar se o analista está pegando os chamados mais complexos (ex: bugs de arquitetura) ou se necessita de auxílio/treinamento específico.
        * **Volume alto em "Não informado":**
          - Sinal de falha de processo na triagem/atribuição de responsável — deve ser tratado como gargalo administrativo, não de execução.
        """)

            # ------------------------------------------------------------------------------
