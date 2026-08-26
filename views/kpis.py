"""KPIs executivos."""
import pandas as pd
import streamlit as st


def render_kpis(df_filtrado):
    st.title("📊 Painel Executivo de Gestão de Demandas & SLA")
    st.caption("Acompanhamento unificado de vazão, Lead Time, envelhecimento de fila (Aging) e conformidade de SLA.")
    st.markdown("---")
    vol_total=len(df_filtrado); abertos=df_filtrado[df_filtrado['DATA_FINALIZACAO'].isnull()]
    tmr=df_filtrado['LEAD_TIME_DIAS'].mean(); aging=abertos['AGING_DIAS'].mean()
    com_prazo=df_filtrado[df_filtrado['SLA_STATUS']!='Sem Prazo']; total=len(com_prazo)
    atrasados=com_prazo['ATRASADO'].sum(); taxa=(atrasados/total*100) if total else 0.0
    sem_prazo=vol_total-total
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric('Total de Demandas',f'{vol_total:,}')
    c2.metric('Em Andamento (WIP)',f'{len(abertos):,}')
    c3.metric('Lead Time Médio',f'{tmr:.1f} dias' if pd.notna(tmr) else 'N/A')
    c4.metric('Aging Médio (Fila)',f'{aging:.1f} dias' if pd.notna(aging) else 'N/A')
    c5.metric('Taxa de Atraso (SLA)',f'{taxa:.1f}%',delta=f'{atrasados} fora do prazo | {sem_prazo} sem prazo definido',delta_color='inverse')
    with st.expander('💡 **Guia de Interpretação dos KPIs Executivos e Tomada de Decisão**'):
        st.markdown("""
        * **Total de Demandas**: Mede o volume bruto de entrada.
        * **Em Andamento (WIP)**: Representa o trabalho acumulado e pendente.
        * **Lead Time Médio**: Tempo médio desde a abertura até o encerramento.
        * **Aging Médio (Fila)**: Idade média dos chamados abertos.
        * **Taxa de Atraso (SLA)**: Percentual de chamados estourados, considerando prazos cadastrados.
        """)
