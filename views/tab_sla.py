"""Análises avançadas de Status e Performance de SLA."""
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


def _taxa(n, d):
    return n / d * 100 if d else 0.0


def render_sla(df_filtrado, data_inicio=None, data_fim=None):
    st.caption("Diagnóstico operacional do status, risco de SLA, qualidade dos prazos e focos de atraso.")
    if df_filtrado.empty:
        st.info("Não há dados suficientes para analisar Status e SLA com os filtros atuais.")
        return

    df_com_prazo = df_filtrado[df_filtrado["SLA_STATUS"] != "Sem Prazo"].copy()
    df_abertos = df_filtrado[df_filtrado["DATA_FINALIZACAO"].isna()].copy()
    df_wip_atrasado = df_filtrado[df_filtrado["SLA_STATUS"] == "Atrasado (WIP)"].copy()
    df_concluido_atrasado = df_filtrado[df_filtrado["SLA_STATUS"] == "Atrasado"].copy()
    total = len(df_filtrado)
    com_prazo = len(df_com_prazo)
    atrasados = int(df_com_prazo["ATRASADO"].sum()) if com_prazo else 0
    sem_prazo = int((df_filtrado["SLA_STATUS"] == "Sem Prazo").sum())
    taxa_atraso = _taxa(atrasados, com_prazo)
    taxa_risco = _taxa(len(df_wip_atrasado), len(df_abertos))
    cobertura = _taxa(com_prazo, total)
    aging = df_wip_atrasado["AGING_DIAS"].mean() if not df_wip_atrasado.empty else np.nan

    st.subheader("🚨 Resumo Executivo de SLA")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Taxa de Atraso", f"{taxa_atraso:.1f}%")
    c2.metric("Atrasados em Aberto", len(df_wip_atrasado), delta=f"{taxa_risco:.1f}% dos abertos", delta_color="inverse")
    c3.metric("Atrasos Concluídos", len(df_concluido_atrasado))
    c4.metric("Cobertura de SLA", f"{cobertura:.1f}%", delta=f"{sem_prazo} sem prazo", delta_color="inverse")
    c5.metric("Aging dos Atrasados", f"{aging:.1f} dias" if pd.notna(aging) else "N/A")

    if taxa_atraso >= 20:
        st.error("🔴 Situação crítica: mais de 20% das demandas com prazo estão atrasadas.")
    elif taxa_atraso >= 10:
        st.warning("🟠 Situação de atenção: a taxa de atraso exige acompanhamento gerencial.")
    else:
        st.success("🟢 Situação controlada: a taxa de atraso está abaixo de 10%.")

    st.markdown("---")
    a, b = st.columns(2)
    with a:
        st.subheader("Distribuição por Status Atual")
        status = df_filtrado["STATUS"].fillna("Não informado").value_counts().rename_axis("STATUS").reset_index(name="Quantidade")
        status["Percentual"] = status["Quantidade"] / total * 100
        fig = px.bar(status, x="Quantidade", y="STATUS", orientation="h", text="Quantidade", color="Percentual", color_continuous_scale="Blues", template="plotly_white", labels={"STATUS":"", "Quantidade":"Demandas", "Percentual":"% do total"})
        fig.update_layout(height=max(380, len(status) * 55), coloraxis_showscale=False, yaxis={"categoryorder":"total ascending"})
        st.plotly_chart(fig, use_container_width=True)
    with b:
        st.subheader("Composição do SLA")
        ordem = ["No Prazo", "No Prazo (WIP)", "Atrasado", "Atrasado (WIP)", "Sem Prazo"]
        sla = df_filtrado["SLA_STATUS"].value_counts().reindex(ordem, fill_value=0).rename_axis("SLA_STATUS").reset_index(name="Quantidade")
        sla = sla[sla["Quantidade"] > 0]
        fig = px.pie(sla, names="SLA_STATUS", values="Quantidade", hole=.55, color="SLA_STATUS", color_discrete_map={"No Prazo":"#2CA02C", "No Prazo (WIP)":"#1F77B4", "Atrasado":"#D62728", "Atrasado (WIP)":"#FF7F0E", "Sem Prazo":"#BDBDBD"}, template="plotly_white")
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("🎯 Principais Focos de Atraso")
    st.caption("A taxa é acompanhada do volume para evitar decisões baseadas apenas em percentuais.")
    r1, r2 = st.columns(2)
    for container, coluna, titulo in [(r1, "SETOR", "Atraso por Setor"), (r2, "TIPO_PROCESSO", "Atraso por Tipo de Processo")]:
        with container:
            if df_com_prazo.empty:
                st.info("Não há demandas com prazo.")
                continue
            rank = df_com_prazo.groupby(coluna, dropna=False).agg(Demandas=("ID_PROCESSO","count"), Atrasadas=("ATRASADO","sum"), Em_Aberto=("DATA_FINALIZACAO",lambda s:s.isna().sum())).reset_index()
            rank["Taxa_Atraso"] = rank["Atrasadas"] / rank["Demandas"] * 100
            rank = rank.sort_values(["Taxa_Atraso","Atrasadas","Demandas"], ascending=False).head(12)
            fig = px.bar(rank, x="Taxa_Atraso", y=coluna, orientation="h", text="Taxa_Atraso", color="Atrasadas", color_continuous_scale="Reds", template="plotly_white", title=titulo, hover_data=["Demandas","Atrasadas","Em_Aberto"])
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(height=450, coloraxis_showscale=False, yaxis={"categoryorder":"total ascending"})
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("🧭 Matriz de Status × Risco de SLA")
    matriz = pd.crosstab(df_filtrado["STATUS"].fillna("Não informado"), df_filtrado["SLA_STATUS"], normalize="index") * 100
    for col in ["Atrasado", "Atrasado (WIP)", "No Prazo", "No Prazo (WIP)", "Sem Prazo"]:
        if col not in matriz.columns:
            matriz[col] = 0.0
    matriz = matriz[["Atrasado", "Atrasado (WIP)", "No Prazo", "No Prazo (WIP)", "Sem Prazo"]].sort_values(["Atrasado (WIP)", "Atrasado"], ascending=False)
    if not matriz.empty:
        fig = px.imshow(matriz.round(1), text_auto=".1f", aspect="auto", color_continuous_scale="RdYlGn_r", labels={"x":"Situação de SLA", "y":"Status atual", "color":"% dentro do status"})
        fig.update_layout(height=max(420, len(matriz) * 55))
        st.plotly_chart(fig, use_container_width=True)
    st.caption("Priorize status com maior concentração de Atrasado (WIP): são demandas abertas que já ultrapassaram o prazo.")

    st.markdown("---")
    st.subheader("📈 Evolução do Risco de SLA")
    tmp = df_filtrado.copy()
    tmp["MES_ABERTURA"] = pd.to_datetime(tmp["DATA_ABERTURA"]).dt.to_period("M").astype(str)
    evo = tmp.groupby("MES_ABERTURA").agg(Demandas=("ID_PROCESSO","count"), Com_Prazo=("SLA_STATUS",lambda s:(s!="Sem Prazo").sum()), Atrasadas=("ATRASADO","sum")).reset_index()
    evo["Taxa_Atraso"] = np.where(evo["Com_Prazo"] > 0, evo["Atrasadas"] / evo["Com_Prazo"] * 100, np.nan)
    evo["Cobertura_SLA"] = np.where(evo["Demandas"] > 0, evo["Com_Prazo"] / evo["Demandas"] * 100, np.nan)
    fig = px.line(evo, x="MES_ABERTURA", y=["Taxa_Atraso","Cobertura_SLA"], markers=True, template="plotly_white", labels={"MES_ABERTURA":"Mês de abertura","value":"Percentual (%)","variable":"Indicador"})
    fig.update_layout(height=380, legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("🔥 Fila de Prioridade: Demandas Abertas e Atrasadas")
    if df_wip_atrasado.empty:
        st.success("Não existem demandas abertas e atrasadas com os filtros atuais.")
    else:
        cols = ["ID_PROCESSO","CLIENTE","SETOR","TIPO_PROCESSO","RESPONSAVEL","STATUS","DATA_ABERTURA","DATA_PREVISTA","AGING_DIAS"]
        prioridade = df_wip_atrasado[[c for c in cols if c in df_wip_atrasado.columns]].sort_values("AGING_DIAS", ascending=False)
        st.dataframe(prioridade, use_container_width=True, hide_index=True, column_config={"AGING_DIAS":st.column_config.NumberColumn("Aging (dias)", format="%.1f"), "DATA_ABERTURA":st.column_config.DateColumn("Abertura"), "DATA_PREVISTA":st.column_config.DateColumn("Prazo")})

    with st.expander("📌 Como usar esta análise para tomada de decisão"):
        st.markdown("""
        **1. Ataque o atraso em aberto primeiro.** Demandas em `Atrasado (WIP)` ainda podem ser recuperadas e devem ser priorizadas conforme Aging, cliente e impacto.

        **2. Procure concentrações.** Se um setor, tipo de processo ou status concentra atrasos, a causa provavelmente é sistêmica.

        **3. Diferencie atraso operacional de problema de cadastro.** Cobertura de SLA baixa significa que parte da operação não pode ser medida corretamente.

        **4. Observe a tendência.** Taxa de atraso crescente indica deterioração da capacidade; cobertura de SLA caindo indica perda de qualidade do planejamento.

        **5. Não use apenas percentuais.** Sempre avalie taxa + quantidade de demandas.
        """)
