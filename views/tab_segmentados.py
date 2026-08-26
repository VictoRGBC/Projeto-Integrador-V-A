"""View modularizada."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

def render_segmentados(df_filtrado, data_inicio=None, data_fim=None):
            # ABA 5: KPIS SEGMENTADOS (SUPORTE E IMPLANTAÇÃO)
            # ------------------------------------------------------------------------------
    st.subheader("Indicadores Exclusivos por Setor Estratégico")
    st.caption("Métricas customizadas ajustadas ao perfil operacional de Suporte (Atendimento) e Implantação (Projetos).")

    df_suporte = df_filtrado[df_filtrado['SETOR'] == 'Suporte'].copy()
    df_implantacao = df_filtrado[df_filtrado['SETOR'] == 'Implantação'].copy()

    col_a, col_b = st.columns(2)

    # ----- BLOCO SUPORTE -----
    with col_a:
        st.markdown("### 🎧 Suporte (Atendimento & TMR)")
        if df_suporte.empty:
            st.info("Nenhuma demanda de Suporte no filtro atual.")
        else:
            tmr_suporte = df_suporte['LEAD_TIME_DIAS'].mean()
            vol_suporte = len(df_suporte)
            abertos_suporte = df_suporte['DATA_FINALIZACAO'].isnull().sum()

            sub1, sub2, sub3 = st.columns(3)
            sub1.metric("Tickets Totais", vol_suporte)
            sub2.metric("Em Aberto", int(abertos_suporte))
            sub3.metric("TMR Médio", f"{tmr_suporte:.1f} dias" if pd.notna(tmr_suporte) else "N/A")

            fig_hist_suporte = px.histogram(
                df_suporte.dropna(subset=['LEAD_TIME_DIAS']),
                x='LEAD_TIME_DIAS',
                nbins=20,
                title="Distribuição do Tempo de Resolução (Dias)",
                labels={'LEAD_TIME_DIAS': 'Dias até o Fechamento'},
                template="plotly_white"
            )
            st.plotly_chart(fig_hist_suporte, use_container_width=True)

            with st.expander("📌 **Análise de Suporte: Distribuição do TMR**"):
                st.markdown("""
                * **Histograma com concentração à esquerda (0 a 2 dias):**
                  - Operação rápida e ágil. A maioria dos tickets é resolvida no Primeiro Nível (N1).
                * **Cauda longa estendida à direita (Barra com 10+ dias):**
                  - **Atenção:** Indica tickets travados de alta complexidade ou esquecidos na fila do suporte sem escalonamento para N2/N3.
                """)

            st.divider()
            st.markdown("**📊 Análises adicionais de Suporte**")

            suporte_status = (
                df_suporte.groupby('STATUS')
                .agg(
                    Total=('ID_PROCESSO', 'count'),
                    Abertos=('DATA_FINALIZACAO', lambda x: x.isnull().sum()),
                    Concluidos=('DATA_FINALIZACAO', lambda x: x.notnull().sum()),
                    Atrasados=('ATRASADO', 'sum'),
                    LeadTime=('LEAD_TIME_DIAS', 'mean')
                )
                .reset_index()
            )
            suporte_status['Taxa_Atraso'] = np.where(
                suporte_status['Total'] > 0,
                suporte_status['Atrasados'] / suporte_status['Total'] * 100,
                0
            )

            col_sup3, col_sup4 = st.columns(2)

            with col_sup3:
                fig_sup_status = px.bar(
                    suporte_status.sort_values('Total', ascending=True),
                    x='Total', y='STATUS', orientation='h', text='Total',
                    labels={'Total': 'Demandas', 'STATUS': 'Status'},
                    title='Volume de Suporte por Status',
                    template='plotly_white'
                )
                fig_sup_status.update_traces(textposition='outside')
                st.plotly_chart(fig_sup_status, use_container_width=True)

            with col_sup4:
                fig_sup_atraso = px.bar(
                    suporte_status.sort_values('Taxa_Atraso', ascending=True),
                    x='Taxa_Atraso', y='STATUS', orientation='h',
                    text='Taxa_Atraso',
                    labels={'Taxa_Atraso': 'Taxa de Atraso (%)', 'STATUS': 'Status'},
                    title='Taxa de Atraso por Status',
                    template='plotly_white'
                )
                fig_sup_atraso.update_traces(
                    texttemplate='%{text:.1f}%', textposition='outside'
                )
                st.plotly_chart(fig_sup_atraso, use_container_width=True)

            df_sup_abertos = df_suporte[df_suporte['DATA_FINALIZACAO'].isnull()].copy()
            if not df_sup_abertos.empty:
                bins_aging = [-np.inf, 2, 5, 10, 20, np.inf]
                labels_aging = ['0-2 dias', '3-5 dias', '6-10 dias', '11-20 dias', '20+ dias']
                df_sup_abertos['FAIXA_AGING'] = pd.cut(
                    df_sup_abertos['AGING_DIAS'],
                    bins=bins_aging,
                    labels=labels_aging
                )
                aging_sup = (
                    df_sup_abertos['FAIXA_AGING']
                    .value_counts()
                    .reindex(labels_aging, fill_value=0)
                    .reset_index()
                )
                aging_sup.columns = ['Faixa', 'Quantidade']

                fig_aging_sup = px.bar(
                    aging_sup,
                    x='Faixa', y='Quantidade', text='Quantidade',
                    title='Aging da Fila de Suporte',
                    labels={'Faixa': 'Faixa de Aging', 'Quantidade': 'Demandas'},
                    template='plotly_white'
                )
                fig_aging_sup.update_traces(textposition='outside')
                st.plotly_chart(fig_aging_sup, use_container_width=True)

    # ----- BLOCO IMPLANTAÇÃO -----
    with col_b:
        st.markdown("### 🚀 Implantação (Projetos & Cumprimento de Prazo)")
        if df_implantacao.empty:
            st.info("Nenhuma demanda de Implantação no filtro atual.")
        else:
            vol_imp = len(df_implantacao)
            concluidas_imp = df_implantacao['DATA_FINALIZACAO'].notnull().sum()
            atrasadas_imp = df_implantacao['ATRASADO'].sum()
            taxa_sucesso_imp = (((concluidas_imp - atrasadas_imp) / concluidas_imp) * 100) if concluidas_imp > 0 else 0.0

            sub1, sub2, sub3 = st.columns(3)
            sub1.metric("Projetos Totais", vol_imp)
            sub2.metric("Concluídos", int(concluidas_imp))
            sub3.metric("Sucesso no Prazo", f"{taxa_sucesso_imp:.1f}%")

            df_status_imp = pd.DataFrame({
                "Situação": ["Dentro do Prazo", "Com Atraso"],
                "Quantidade": [
                    max(concluidas_imp - atrasadas_imp, 0),
                    atrasadas_imp
                ]
            })
            fig_pie_imp = px.pie(
                df_status_imp,
                names='Situação',
                values='Quantidade',
                hole=0.4,
                title="Implantações: Prazo vs. Atraso",
                color='Situação',
                color_discrete_map={"Dentro do Prazo": "#2E7D32", "Com Atraso": "#C62828"},
                template="plotly_white"
            )
            fig_pie_imp.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie_imp, use_container_width=True)

            with st.expander("📌 **Análise de Implantação: Prazo vs. Atraso**"):
                st.markdown("""
                * **Baixa Taxa de Sucesso no Prazo (< 80%):**
                  - **Impacto Financeiro e Operacional:** Projetos de implantação atrasados geram custo extra de alocação de consultores e adiam o faturamento da licença/recorrência.
                  - **Ação:** Rever cronogramas padrão de implantação e alinhar requisitos com o cliente antes de iniciar a execução.
                """)

            st.divider()
            st.markdown("**📊 Análises adicionais de Implantação**")

            imp_tipo = (
                df_implantacao.groupby('TIPO_PROCESSO')
                .agg(
                    Demandas=('ID_PROCESSO', 'count'),
                    Concluidas=('DATA_FINALIZACAO', lambda x: x.notnull().sum()),
                    LeadTime=('LEAD_TIME_DIAS', 'mean'),
                    Atrasadas=('ATRASADO', 'sum')
                )
                .reset_index()
            )
            imp_tipo['Taxa_Atraso'] = np.where(
                imp_tipo['Concluidas'] > 0,
                imp_tipo['Atrasadas'] / imp_tipo['Concluidas'] * 100,
                0
            )

            col_imp3, col_imp4 = st.columns(2)

            with col_imp3:
                fig_imp_tmr = px.bar(
                    imp_tipo.sort_values('LeadTime', ascending=True),
                    x='LeadTime', y='TIPO_PROCESSO', orientation='h',
                    text='LeadTime',
                    labels={'LeadTime': 'Lead Time Médio (dias)', 'TIPO_PROCESSO': 'Tipo de Processo'},
                    title='Lead Time Médio por Tipo de Implantação',
                    color='LeadTime',
                    color_continuous_scale='Reds',
                    template='plotly_white'
                )
                fig_imp_tmr.update_traces(
                    texttemplate='%{text:.1f} dias', textposition='outside'
                )
                fig_imp_tmr.update_layout(coloraxis_showscale=False)
                st.plotly_chart(fig_imp_tmr, use_container_width=True)

            with col_imp4:
                fig_imp_atraso = px.bar(
                    imp_tipo.sort_values('Taxa_Atraso', ascending=True),
                    x='Taxa_Atraso', y='TIPO_PROCESSO', orientation='h',
                    text='Taxa_Atraso',
                    labels={'Taxa_Atraso': 'Taxa de Atraso (%)', 'TIPO_PROCESSO': 'Tipo de Processo'},
                    title='Atraso por Tipo de Implantação',
                    color='Taxa_Atraso',
                    color_continuous_scale='Reds',
                    template='plotly_white'
                )
                fig_imp_atraso.update_traces(
                    texttemplate='%{text:.1f}%', textposition='outside'
                )
                fig_imp_atraso.update_layout(coloraxis_showscale=False)
                st.plotly_chart(fig_imp_atraso, use_container_width=True)

            df_comparativo_setor = (
                df_filtrado.groupby('SETOR')
                .agg(
                    Demandas=('ID_PROCESSO', 'count'),
                    Concluidas=('DATA_FINALIZACAO', lambda x: x.notnull().sum()),
                    WIP=('DATA_FINALIZACAO', lambda x: x.isnull().sum()),
                    LeadTime=('LEAD_TIME_DIAS', 'mean'),
                    Atrasadas=('ATRASADO', 'sum')
                )
                .reset_index()
            )
            df_comparativo_setor['Taxa_Atraso'] = np.where(
                df_comparativo_setor['Demandas'] > 0,
                df_comparativo_setor['Atrasadas'] / df_comparativo_setor['Demandas'] * 100,
                0
            )

            st.markdown("**Comparativo de Eficiência entre Macrosetores**")
            fig_setor_comp = px.bar(
                df_comparativo_setor,
                x='SETOR', y='Demandas', color='Taxa_Atraso',
                text='Demandas',
                labels={'SETOR': 'Setor', 'Demandas': 'Volume de Demandas',
                        'Taxa_Atraso': 'Taxa de Atraso (%)'},
                title='Volume por Setor com Intensidade de Atraso',
                color_continuous_scale='Reds',
                template='plotly_white'
            )
            fig_setor_comp.update_traces(textposition='outside')
            st.plotly_chart(fig_setor_comp, use_container_width=True)

            fig_maturidade = px.scatter(
                df_comparativo_setor,
                x='Demandas', y='LeadTime', size='WIP',
                color='Taxa_Atraso', text='SETOR',
                hover_data={'Demandas': True, 'Concluidas': True, 'WIP': True,
                            'LeadTime': ':.1f', 'Taxa_Atraso': ':.1f'},
                labels={'Demandas': 'Volume de Demandas',
                        'LeadTime': 'Lead Time Médio (dias)',
                        'Taxa_Atraso': 'Taxa de Atraso (%)'},
                title='Matriz de Maturidade Operacional por Setor',
                color_continuous_scale='Reds',
                template='plotly_white'
            )
            fig_maturidade.update_traces(textposition='top center')
            st.plotly_chart(fig_maturidade, use_container_width=True)

            with st.expander("📌 **Como interpretar os novos gráficos de Implantação**"):
                st.markdown("""
                * **Lead Time alto por tipo:** sinaliza tipos de projeto que exigem mais esforço, dependências ou etapas.
                * **Taxa de atraso alta:** indica onde revisar estimativas, capacidade e requisitos.
                * **Matriz de maturidade:** alto volume + alto Lead Time + alto atraso merece prioridade gerencial.
                * **WIP elevado:** representa capacidade já comprometida e pode antecipar novos atrasos.
                """)
