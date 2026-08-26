"""ETL e métricas de processos."""
import datetime
import logging
import numpy as np
import pandas as pd
import streamlit as st
from database.connection import conectar_banco

VALOR_NAO_INFORMADO = "Não informado"


def classificar_setor(tipo_processo):
    if pd.isna(tipo_processo): return "Outro"
    texto = str(tipo_processo).strip().upper()
    if any(k in texto for k in ["SUPORT", "TICKET", "CHAMADO", "ERRO", "DÚVIDA", "DUVIDA", "RESET"]): return "Suporte"
    if any(k in texto for k in ["IMPLANT", "CONFIG", "TREINAM", "MIGRA"]): return "Implantação"
    if any(k in texto for k in ["DESENV", "MELHORIA", "EVOLU", "FEATURE", "BUG", "API"]): return "Desenvolvimento"
    return "Outro"


def checar_sla(row, hoje):
    if pd.isnull(row['DATA_PREVISTA']): return "Sem Prazo"
    if pd.notnull(row['DATA_FINALIZACAO']):
        return "Atrasado" if row['DATA_FINALIZACAO'] > row['DATA_PREVISTA'] else "No Prazo"
    return "Atrasado (WIP)" if hoje > row['DATA_PREVISTA'] else "No Prazo (WIP)"


@st.cache_data(ttl=600, show_spinner=False)
def carregar_dados_processos(data_inicio, data_fim):
    conexao = conectar_banco()
    query = """
        SELECT p.CODIGO AS ID_PROCESSO, p."DATA" AS DATA_ABERTURA,
               p.DATA_FINALIZACAO, p.DATA_PREVISTA, s.DESCRICAO AS STATUS,
               tp.DESCRICAO AS TIPO_PROCESSO, c.NOME_FANTASIA AS CLIENTE,
               u.NOME AS RESPONSAVEL
        FROM TBL_PROCESSO p
        LEFT JOIN TBL_STATUS_SOLICITACAO s ON p.CHSTATUS = s.CODIGO
        LEFT JOIN TBL_TIPO_PROCESSO tp ON p.CHTIPO_PROCESSO = tp.CODIGO
        LEFT JOIN TBL_CLIENTE c ON p.CHCLIENTE = c.CODIGO
        LEFT JOIN TBL_USUARIO u ON p.CHRESPONSAVEL = u.CODIGO
        WHERE p."DATA" BETWEEN ? AND ?
    """
    try: df = pd.read_sql(query, conexao, params=(data_inicio, data_fim))
    finally: conexao.close()
    if df.empty: return df
    for col in ['DATA_ABERTURA','DATA_FINALIZACAO','DATA_PREVISTA']:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    for col in ['STATUS','TIPO_PROCESSO','CLIENTE','RESPONSAVEL']:
        df[col] = df[col].fillna(VALOR_NAO_INFORMADO)
    df['SETOR'] = df['TIPO_PROCESSO'].apply(classificar_setor)
    df['LEAD_TIME_DIAS'] = (df['DATA_FINALIZACAO'] - df['DATA_ABERTURA']).dt.total_seconds()/(24*3600)
    qtd = int((df['LEAD_TIME_DIAS'] < 0).sum())
    if qtd: logging.warning(f"{qtd} processo(s) com DATA_FINALIZACAO anterior à DATA_ABERTURA foram desconsiderados do cálculo de Lead Time.")
    df.loc[df['LEAD_TIME_DIAS'] < 0, 'LEAD_TIME_DIAS'] = np.nan
    df['LEAD_TIME_INCONSISTENTE'] = df['LEAD_TIME_DIAS'].isna() & df['DATA_FINALIZACAO'].notna()
    hoje = pd.to_datetime(datetime.date.today())
    df['AGING_DIAS'] = np.where(df['DATA_FINALIZACAO'].isnull(), (hoje-df['DATA_ABERTURA']).dt.total_seconds()/(24*3600), np.nan)
    df['SLA_STATUS'] = df.apply(lambda row: checar_sla(row, hoje), axis=1)
    df['ATRASADO'] = df['SLA_STATUS'].str.contains('Atrasado')
    return df
