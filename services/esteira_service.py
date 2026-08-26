"""Consulta recursiva da esteira Pai/Filho."""

import logging
import numpy as np
import pandas as pd
import streamlit as st
from database.connection import conectar_banco

def carregar_lead_time_esteira(data_inicio, data_fim):
    """Mapeia a esteira de processos (hierarquia Pai-Filho) utilizando CTE Recursiva."""
    conexao = conectar_banco()

    query = """
        WITH RECURSIVE ArvoreProcessos AS (
            SELECT
                p.CODIGO AS PROCESSO_RAIZ,
                p.CODIGO AS PROCESSO_ATUAL,
                p."DATA" AS DATA_INICIAL_ESTEIRA,
                p.DATA_FINALIZACAO AS DATA_FIM_ETAPA,
                p.CHPROCESSO,
                1 AS NIVEL_ESTEIRA,
                p.CHCLIENTE
            FROM TBL_PROCESSO p
            WHERE p.CHPROCESSO IS NULL
              AND p."DATA" BETWEEN ? AND ?

            UNION ALL

            SELECT
                ap.PROCESSO_RAIZ,
                f.CODIGO AS PROCESSO_ATUAL,
                ap.DATA_INICIAL_ESTEIRA,
                f.DATA_FINALIZACAO AS DATA_FIM_ETAPA,
                f.CHPROCESSO,
                ap.NIVEL_ESTEIRA + 1 AS NIVEL_ESTEIRA,
                f.CHCLIENTE
            FROM TBL_PROCESSO f
            INNER JOIN ArvoreProcessos ap ON f.CHPROCESSO = ap.PROCESSO_ATUAL
            WHERE ap.NIVEL_ESTEIRA < 50
        )
        SELECT
            ap.PROCESSO_RAIZ,
            c.NOME_FANTASIA AS CLIENTE,
            ap.DATA_INICIAL_ESTEIRA,
            MAX(ap.DATA_FIM_ETAPA) AS DATA_FINAL_ESTEIRA,
            MAX(ap.NIVEL_ESTEIRA) AS QTD_ETAPAS
        FROM ArvoreProcessos ap
        LEFT JOIN TBL_CLIENTE c ON ap.CHCLIENTE = c.CODIGO
        GROUP BY
            ap.PROCESSO_RAIZ,
            c.NOME_FANTASIA,
            ap.DATA_INICIAL_ESTEIRA
    """

    df_esteira = pd.read_sql(query, conexao, params=(data_inicio, data_fim))
    conexao.close()

    if not df_esteira.empty:
        df_esteira['DATA_INICIAL_ESTEIRA'] = pd.to_datetime(df_esteira['DATA_INICIAL_ESTEIRA'], errors='coerce')
        df_esteira['DATA_FINAL_ESTEIRA'] = pd.to_datetime(df_esteira['DATA_FINAL_ESTEIRA'], errors='coerce')
        df_esteira['LEAD_TIME_TOTAL_DIAS'] = (df_esteira['DATA_FINAL_ESTEIRA'] - df_esteira['DATA_INICIAL_ESTEIRA']).dt.total_seconds() / (24 * 3600)

        # --- Guarda contra duplicação (item 6 da revisão) ---
        # Se CHPROCESSO não formar uma árvore estrita (ex.: cadastro que
        # aponte mais de um "pai" por engano), a CTE recursiva pode gerar
        # múltiplas linhas para a mesma PROCESSO_RAIZ e inflar QTD_ETAPAS /
        # LEAD_TIME_TOTAL_DIAS. Mantemos apenas a ocorrência de maior
        # QTD_ETAPAS por raiz (o caminho mais completo) e descartamos negativos.
        antes = len(df_esteira)
        df_esteira = (
            df_esteira.sort_values('QTD_ETAPAS', ascending=False)
                      .drop_duplicates(subset=['PROCESSO_RAIZ'], keep='first')
        )
        depois = len(df_esteira)
        if antes != depois:
            logging.warning(
                f"{antes - depois} linha(s) duplicada(s) de PROCESSO_RAIZ foram "
                f"removidas na esteira de produção (possível estrutura não-árvore)."
            )
        df_esteira.loc[df_esteira['LEAD_TIME_TOTAL_DIAS'] < 0, 'LEAD_TIME_TOTAL_DIAS'] = np.nan

    return df_esteira
