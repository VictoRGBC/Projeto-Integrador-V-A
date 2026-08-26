"""View modularizada."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

def render_overview(df_filtrado, data_inicio=None, data_fim=None):
    st.subheader("Evolução Temporal: Entradas vs. Saídas (Vazão / Cumulative Flow)")
    st.caption("Compara a taxa de criação de demandas (Entradas) em relação ao volume de finalização (Saídas/Vazão) dia a dia.")

    df_entradas = df_filtrado.groupby(df_filtrado["DATA_ABERTURA"].dt.date).size().reset_index(name="Entradas")
    df_saidas = df_filtrado.dropna(subset=["DATA_FINALIZACAO"]).groupby(df_filtrado["DATA_FINALIZACAO"].dt.date).size().reset_index(name="Concluídos")

    df_timeline = pd.merge(df_entradas, df_saidas, left_on="DATA_ABERTURA", right_on="DATA_FINALIZACAO", how="outer").fillna(0)
    df_timeline["Data"] = df_timeline["DATA_ABERTURA"].combine_first(df_timeline["DATA_FINALIZACAO"])
    df_timeline = df_timeline.sort_values("Data")

    fig_linha = go.Figure()
    fig_linha.add_trace(go.Scatter(x=df_timeline["Data"], y=df_timeline["Entradas"], mode="lines+markers", name="Criados (Demandas)", line=dict(color="#1F77B4", width=2)))
    fig_linha.add_trace(go.Scatter(x=df_timeline["Data"], y=df_timeline["Concluídos"], mode="lines+markers", name="Concluídos (Vazão)", line=dict(color="#2CA02C", width=2)))

    fig_linha.update_layout(
        template="plotly_white",
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="Data",
        yaxis_title="Quantidade de Chamados",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_linha, use_container_width=True)

    st.markdown("---")
    st.subheader("📊 Análises Avançadas de Fluxo e Saldo Operacional")

    # Cálculo de Saldo Operacional e Backlog Acumulado
    df_timeline["Saldo_Diario"] = df_timeline["Entradas"] - df_timeline["Concluídos"]
    df_timeline["Backlog_Acumulado"] = df_timeline["Saldo_Diario"].cumsum()

    col_a1, col_a2 = st.columns(2)

    with col_a1:
        st.markdown("### ⚖️ Saldo Operacional Diário (Net Flow)")
        st.caption("Mede o acúmulo líquido por dia (Entradas − Concluídos). Barras vermelhas representam acúmulo de backlog.")

        cores_saldo = ["#D62728" if v > 0 else "#2CA02C" for v in df_timeline["Saldo_Diario"]]
        fig_saldo = go.Figure()
        fig_saldo.add_trace(go.Bar(
            x=df_timeline["Data"],
            y=df_timeline["Saldo_Diario"],
            marker_color=cores_saldo,
            name="Saldo Diário"
        ))
        fig_saldo.update_layout(
            template="plotly_white",
            height=350,
            xaxis_title="Data",
            yaxis_title="Saldo de Chamados",
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_saldo, use_container_width=True)

    with col_a2:
        st.markdown("### 📈 Evolução do Backlog Acumulado")
        st.caption("Tendência do volume total represado na operação ao longo do tempo.")

        fig_backlog = go.Figure()
        fig_backlog.add_trace(go.Scatter(
            x=df_timeline["Data"],
            y=df_timeline["Backlog_Acumulado"],
            mode="lines",
            fill="tozeroy",
            line=dict(color="#FF7F0E", width=2),
            name="Backlog Acumulado"
        ))
        fig_backlog.update_layout(
            template="plotly_white",
            height=350,
            xaxis_title="Data",
            yaxis_title="Volume Acumulado",
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_backlog, use_container_width=True)

    # Heatmap por Dia da Semana
    st.markdown("### 🗓️ Sazonalidade de Abertura por Dia da Semana")
    st.caption("Distribuição do volume de novas demandas ao longo dos dias úteis para apoio no planejamento de escala.")

    df_filtrado["DIA_SEMANA"] = df_filtrado["DATA_ABERTURA"].dt.day_name()
    dias_ordem = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dias_pt = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

    df_dias = df_filtrado.groupby("DIA_SEMANA").size().reindex(dias_ordem, fill_value=0).reset_index(name="Volume")
    df_dias["Dia"] = dias_pt

    fig_dias = px.bar(
        df_dias,
        x="Dia",
        y="Volume",
        text="Volume",
        color="Volume",
        color_continuous_scale="Blues",
        template="plotly_white"
    )
    fig_dias.update_traces(textposition="outside")
    fig_dias.update_layout(height=320, coloraxis_showscale=False, yaxis_title="Quantidade de Aberturas", xaxis_title="")
    st.plotly_chart(fig_dias, use_container_width=True)

    with st.expander("📌 **Pontos Importantes a Notar nas Tendências da Operação**"):
        st.markdown("""
        * **Saldo Operacional Positivo (Vermelho):** Ocorre quando a taxa de chegada supera a capacidade de atendimento. Múltiplos dias consecutivos indicam necessidade de reforço operacional ou limitação de escopo.
        * **Curva do Backlog Acumulado em Ascensão:** Aponta um gargalo estrutural contínuo na esteira de atendimento.
        * **Picos no Dia da Semana:** Permite ajustar escalas de plantão e alocação de equipes para os dias com maior volume de tickets (ex: segundas-feiras).
        """)

    st.markdown("---")
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("Volume de Demandas por Setor")
        st.caption("Identifica o volume relativo absorvido por cada macrosetor (Suporte, Implantação, Dev, etc.).")
        fig_setor = px.bar(
            df_filtrado['SETOR'].value_counts().reset_index(),
            x='count', y='SETOR', orientation='h',
            labels={'count': 'Quantidade', 'SETOR': ''},
            color='SETOR', template="plotly_white"
        )
        fig_setor.update_layout(showlegend=False)
        st.plotly_chart(fig_setor, use_container_width=True)

    with col_g2:
        st.subheader("Volume por Tipo de Processo")
        st.caption("Frequência de chamados agrupados por categorias detalhadas de atendimento.")
        fig_tipo = px.bar(
            df_filtrado['TIPO_PROCESSO'].value_counts().reset_index(),
            x='count', y='TIPO_PROCESSO', orientation='h',
            labels={'count': 'Quantidade', 'TIPO_PROCESSO': ''},
            color='TIPO_PROCESSO', template="plotly_white"
        )
        fig_tipo.update_layout(showlegend=False)
        st.plotly_chart(fig_tipo, use_container_width=True)
