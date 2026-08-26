"""View modularizada."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from services.esteira_service import carregar_lead_time_esteira

def render_esteira(df_filtrado, data_inicio=None, data_fim=None):
    st.subheader("Jornada do Processo e Suas Derivações (Esteira Completa)")
    st.caption("Mapeamento que rastreia a vida útil completa da demanda desde o processo raiz até a última etapa vinculada.")

    df_esteira = carregar_lead_time_esteira(data_inicio, data_fim)

    if df_esteira.empty:
        st.info("Nenhuma esteira encadeada foi identificada no período.")
    else:
        df_esteira_concluida = df_esteira.dropna(subset=['LEAD_TIME_TOTAL_DIAS']).copy()

        col_est1, col_est2 = st.columns([2, 1])

        with col_est1:
            fig_esteira = px.scatter(
                df_esteira_concluida,
                x='LEAD_TIME_TOTAL_DIAS',
                y='QTD_ETAPAS',
                color='QTD_ETAPAS',
                size='LEAD_TIME_TOTAL_DIAS',
                hover_data=['PROCESSO_RAIZ', 'CLIENTE'],
                title="Identificação de Complexidade vs. Durabilidade",
                labels={
                    'LEAD_TIME_TOTAL_DIAS': 'Lead Time Total (Dias)',
                    'QTD_ETAPAS': 'Quantidade de Fases / Repasses'
                },
                template="plotly_white"
            )
            fig_esteira.add_hline(y=3, line_dash="dot", annotation_text="Limite Recomendado (3 Etapas)", annotation_position="bottom right")
            st.plotly_chart(fig_esteira, use_container_width=True)

            with st.expander("📌 **Como interpretar o Gráfico de Esteira de Produção**"):
                st.markdown("""
                * **Quadrante Superior Direito (Muitas Etapas + Alto Lead Time):**
                  - **Diagnóstico:** Processos excessivamente burocráticos. Cada repasse de etapa (*handoff*) gera tempo de espera em fila e risco de perda de contexto.
                  - **Ação:** Simplificar o fluxo de trabalho (*workflow*), unificando atribuições ou reduzindo aprovações intermediárias.
                * **Canto Inferior Direito (Poucas Etapas + Alto Lead Time):**
                  - **Diagnóstico:** A demanda trava em uma única etapa pesada. Pode indicar falta de conhecimento técnico do analista ou escopo mal formatado.
                * **Linha de Limite (3 Etapas):** Esteiras com mais de 3 etapas secundárias tendem a ter um crescimento exponencial no tempo de entrega.
                """)

        with col_est2:
            st.markdown("**Top 5 Esteiras Mais Demoradas**")
            df_top = df_esteira_concluida.sort_values(by='LEAD_TIME_TOTAL_DIAS', ascending=False).head(5)
            st.dataframe(
                df_top[['PROCESSO_RAIZ', 'CLIENTE', 'LEAD_TIME_TOTAL_DIAS']],
                column_config={
                    "PROCESSO_RAIZ": "ID Processo Raiz",
                    "CLIENTE": "Cliente",
                    "LEAD_TIME_TOTAL_DIAS": st.column_config.NumberColumn("Dias Totais", format="%.1f")
                },
                hide_index=True,
                use_container_width=True
            )
            st.caption("⚠️ **Ação Recomendada:** Realizar reuniões de 'Post-Mortem' sobre essas 5 esteiras para mapear a causa raiz da demora estendida.")

    st.divider()
    st.subheader("📊 Análises Avançadas da Esteira de Produção")
    st.caption(
        "Indicadores adicionais para identificar concentração de etapas, "
        "complexidade, dispersão e gargalos das esteiras."
    )
    # --------------------------------------------------------------------------
    # 1. DISTRIBUIÇÃO DO LEAD TIME DAS ESTEIRAS
    # --------------------------------------------------------------------------
    col_est3, col_est4 = st.columns(2)
    with col_est3:
        st.markdown("### ⏱️ Distribuição do Lead Time")
        fig_dist_lead = px.histogram(
            df_esteira_concluida,
            x="LEAD_TIME_TOTAL_DIAS",
            nbins=20,
            marginal="box",
            title="Distribuição do Lead Time das Esteiras",
            labels={
                "LEAD_TIME_TOTAL_DIAS": "Lead Time Total (Dias)",
                "count": "Quantidade de Esteiras"
            },
            template="plotly_white"
        )
        fig_dist_lead.update_layout(
            height=420,
            showlegend=False
        )
        st.plotly_chart(
            fig_dist_lead,
            use_container_width=True
        )
    # --------------------------------------------------------------------------
    # 2. QUANTIDADE DE ESTEIRAS POR NÚMERO DE ETAPAS
    # --------------------------------------------------------------------------
    with col_est4:
        st.markdown("### 🔢 Distribuição de Etapas")
        df_qtd_etapas = (
            df_esteira_concluida
            .groupby("QTD_ETAPAS")
            .size()
            .reset_index(name="QUANTIDADE_ESTEIRAS")
            .sort_values("QTD_ETAPAS")
        )
        fig_qtd_etapas = px.bar(
            df_qtd_etapas,
            x="QTD_ETAPAS",
            y="QUANTIDADE_ESTEIRAS",
            text="QUANTIDADE_ESTEIRAS",
            title="Quantidade de Esteiras por Número de Etapas",
            labels={
                "QTD_ETAPAS": "Quantidade de Etapas",
                "QUANTIDADE_ESTEIRAS": "Número de Esteiras"
            },
            template="plotly_white"
        )
        fig_qtd_etapas.update_traces(
            textposition="outside"
        )
        st.plotly_chart(
            fig_qtd_etapas,
            use_container_width=True
        )
    # --------------------------------------------------------------------------
    # 3. LEAD TIME MÉDIO POR QUANTIDADE DE ETAPAS
    # --------------------------------------------------------------------------
    st.markdown("### 📈 Relação entre Número de Etapas e Lead Time")
    df_lead_por_etapa = (
        df_esteira_concluida
        .groupby("QTD_ETAPAS")
        .agg(
            LEAD_TIME_MEDIO=("LEAD_TIME_TOTAL_DIAS", "mean"),
            MEDIANA_LEAD_TIME=("LEAD_TIME_TOTAL_DIAS", "median"),
            QUANTIDADE=("PROCESSO_RAIZ", "count")
        )
        .reset_index()
        .sort_values("QTD_ETAPAS")
    )
    fig_lead_etapas = go.Figure()
    fig_lead_etapas.add_trace(
        go.Scatter(
            x=df_lead_por_etapa["QTD_ETAPAS"],
            y=df_lead_por_etapa["LEAD_TIME_MEDIO"],
            mode="lines+markers+text",
            text=df_lead_por_etapa["QUANTIDADE"],
            textposition="top center",
            name="Lead Time Médio"
        )
    )
    fig_lead_etapas.add_trace(
        go.Scatter(
            x=df_lead_por_etapa["QTD_ETAPAS"],
            y=df_lead_por_etapa["MEDIANA_LEAD_TIME"],
            mode="lines+markers",
            name="Mediana"
        )
    )
    fig_lead_etapas.update_layout(
        title="Lead Time Médio e Mediana por Quantidade de Etapas",
        xaxis_title="Quantidade de Etapas",
        yaxis_title="Dias",
        template="plotly_white",
        height=430
    )
    st.plotly_chart(
        fig_lead_etapas,
        use_container_width=True
    )
    # --------------------------------------------------------------------------
    # 4. BOXPLOT — DISPERSÃO DO LEAD TIME
    # --------------------------------------------------------------------------
    st.markdown("### 📦 Dispersão do Lead Time por Quantidade de Etapas")
    fig_boxplot = px.box(
        df_esteira_concluida,
        x="QTD_ETAPAS",
        y="LEAD_TIME_TOTAL_DIAS",
        points="outliers",
        title="Variabilidade do Lead Time por Número de Etapas",
        labels={
            "QTD_ETAPAS": "Quantidade de Etapas",
            "LEAD_TIME_TOTAL_DIAS": "Lead Time Total (Dias)"
        },
        template="plotly_white"
    )
    fig_boxplot.update_layout(
        height=450
    )
    st.plotly_chart(
        fig_boxplot,
        use_container_width=True
    )
    # --------------------------------------------------------------------------
    # 5. TOP 10 CLIENTES COM MAIOR LEAD TIME
    # --------------------------------------------------------------------------
    st.markdown("### 🏢 Clientes com Esteiras Mais Demoradas")
    df_cliente_esteira = (
        df_esteira_concluida
        .groupby("CLIENTE")
        .agg(
            ESTEIRAS=("PROCESSO_RAIZ", "count"),
            LEAD_TIME_MEDIO=("LEAD_TIME_TOTAL_DIAS", "mean"),
            MAIOR_LEAD_TIME=("LEAD_TIME_TOTAL_DIAS", "max"),
            ETAPAS_MEDIAS=("QTD_ETAPAS", "mean")
        )
        .reset_index()
    )
    df_cliente_esteira = (
        df_cliente_esteira
        .sort_values(
            "LEAD_TIME_MEDIO",
            ascending=False
        )
        .head(10)
    )
    fig_cliente_esteira = px.bar(
        df_cliente_esteira.sort_values(
            "LEAD_TIME_MEDIO",
            ascending=True
        ),
        x="LEAD_TIME_MEDIO",
        y="CLIENTE",
        orientation="h",
        text="LEAD_TIME_MEDIO",
        title="Top 10 Clientes por Lead Time Médio da Esteira",
        labels={
            "LEAD_TIME_MEDIO": "Lead Time Médio (Dias)",
            "CLIENTE": "Cliente"
        },
        template="plotly_white"
    )
    fig_cliente_esteira.update_traces(
        texttemplate="%{text:.1f} dias",
        textposition="outside"
    )

    st.plotly_chart(
        fig_cliente_esteira,
        use_container_width=True
    )
    # --------------------------------------------------------------------------
    # 6. CLASSIFICAÇÃO DE COMPLEXIDADE
    # --------------------------------------------------------------------------
    st.markdown("### 🎯 Matriz de Complexidade das Esteiras")
    def classificar_complexidade(qtd_etapas, lead_time):
        if qtd_etapas <= 2 and lead_time <= 5:
            return "Baixa"

        if qtd_etapas <= 4 and lead_time <= 10:
            return "Média"

        return "Alta"
    df_complexidade = df_esteira_concluida.copy()
    df_complexidade["COMPLEXIDADE"] = df_complexidade.apply(
        lambda row: classificar_complexidade(
            row["QTD_ETAPAS"],
            row["LEAD_TIME_TOTAL_DIAS"]
        ),
        axis=1
    )
    df_complexidade_resumo = (
        df_complexidade
        .groupby("COMPLEXIDADE")
        .size()
        .reset_index(name="QUANTIDADE")
    )
    fig_complexidade = px.pie(
        df_complexidade_resumo,
        names="COMPLEXIDADE",
        values="QUANTIDADE",
        hole=0.45,
        title="Distribuição das Esteiras por Complexidade",
        template="plotly_white"
    )
    fig_complexidade.update_traces(
        textposition="inside",
        textinfo="percent+label"
    )
    st.plotly_chart(
        fig_complexidade,
        use_container_width=True
    )
    # --------------------------------------------------------------------------
    # 7. MATRIZ DE GARGALOS
    # --------------------------------------------------------------------------
    st.markdown("### 🚦 Matriz de Gargalos da Esteira")
    fig_gargalos = px.scatter(
        df_esteira_concluida,
        x="QTD_ETAPAS",
        y="LEAD_TIME_TOTAL_DIAS",
        size="LEAD_TIME_TOTAL_DIAS",
        hover_name="PROCESSO_RAIZ",
        hover_data=[
            "CLIENTE",
            "QTD_ETAPAS",
            "LEAD_TIME_TOTAL_DIAS"
        ],
        title="Mapa de Gargalos: Complexidade × Tempo",
        labels={
            "QTD_ETAPAS": "Quantidade de Etapas",
            "LEAD_TIME_TOTAL_DIAS": "Lead Time Total (Dias)"
        },
        template="plotly_white"
    )
    media_etapas = df_esteira_concluida["QTD_ETAPAS"].mean()
    media_lead = df_esteira_concluida["LEAD_TIME_TOTAL_DIAS"].mean()
    fig_gargalos.add_vline(
        x=media_etapas,
        line_dash="dot",
        annotation_text="Média de Etapas"
    )
    fig_gargalos.add_hline(
        y=media_lead,
        line_dash="dot",
        annotation_text="Lead Time Médio"
    )
    fig_gargalos.update_layout(
        height=500
    )
    st.plotly_chart(
        fig_gargalos,
        use_container_width=True
    )
    # --------------------------------------------------------------------------
    # 8. INDICADORES EXECUTIVOS DA ESTEIRA
    # --------------------------------------------------------------------------
    st.markdown("### 📌 Indicadores Executivos da Esteira")
    total_esteiras = len(df_esteira_concluida)
    lead_medio_esteira = (
        df_esteira_concluida["LEAD_TIME_TOTAL_DIAS"].mean()
    )
    lead_mediano_esteira = (
        df_esteira_concluida["LEAD_TIME_TOTAL_DIAS"].median()
    )
    etapas_media = (
        df_esteira_concluida["QTD_ETAPAS"].mean()
    )
    esteiras_complexas = (
        df_complexidade["COMPLEXIDADE"]
        .eq("Alta")
        .sum()
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Esteiras Analisadas",
        f"{total_esteiras:,}"
    )
    c2.metric(
        "Lead Time Médio",
        f"{lead_medio_esteira:.1f} dias"
    )
    c3.metric(
        "Etapas Médias",
        f"{etapas_media:.1f}"
    )
    c4.metric(
        "Esteiras Alta Complexidade",
        f"{esteiras_complexas:,}"
    )
            # ------------------------------------------------------------------------------
