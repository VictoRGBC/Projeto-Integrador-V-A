"""
PROJETO INTEGRADOR V - A
Curso: Big Data e Inteligência Artificial
Autor: Victor Gabriel Barros
Contexto: Aplicação Analítica para gestão de processos e implantações na Integra Engenharia de Sistemas.
"""

import streamlit as st
import pandas as pd
import numpy as np
import fdb
import plotly.express as px
import plotly.graph_objects as go
import os
import datetime
import platform
import logging

# Configuração básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Dashboard Executivo | Gestão de Processos & SLA",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. CONFIGURAÇÃO DO BANCO DE DADOS FIREBIRD & DLL
# ==============================================================================
def obter_config_db():
    """Lê a configuração do banco a partir do st.secrets, com fallback para variáveis de ambiente."""
    try:
        cfg = st.secrets["db"]
        return {
            "host": cfg["host"],
            "path": cfg["path"],
            "user": cfg["user"],
            "password": cfg["password"],
            "port": int(cfg.get("port", 3050)),
        }
    except Exception:
        return {
            "host": os.environ.get("SGFA_DB_HOST", "SRV-SGFA"),
            "path": os.environ.get("SGFA_DB_PATH", ""),
            "user": os.environ.get("SGFA_DB_USER", ""),
            "password": os.environ.get("SGFA_DB_PASSWORD", ""),
            "port": int(os.environ.get("SGFA_DB_PORT", 3050)),
        }

DB_CONFIG = obter_config_db()

# Carrega a biblioteca do cliente Firebird no Windows se disponível
DIR_ATUAL = os.path.dirname(os.path.abspath(__file__))
if platform.system() == "Windows":
    DLL_PATH = os.path.join(DIR_ATUAL, "fbclient.dll")
    if os.path.exists(DLL_PATH):
        fdb.load_api(DLL_PATH)

def conectar_banco():
    """Estabelece a conexão com o banco Firebird definindo o charset WIN1252."""
    cfg = DB_CONFIG
    dsn_conexao = f"{cfg['host']}/{cfg['port']}:{cfg['path']}"
    return fdb.connect(
        dsn=dsn_conexao,
        user=cfg['user'],
        password=cfg['password'],
        charset='WIN1252'
    )

# ==============================================================================
# 3. SEGURANÇA E AUTENTICAÇÃO
# ==============================================================================
def descriptografar_senha_xor(senha_criptografada, chave_inicial=2):
    """Reverte a ofuscação XOR da senha gravada no banco."""
    senha_aberta = ""
    chave_atual = chave_inicial

    for char in senha_criptografada:
        char_desc = chr(ord(char) ^ chave_atual)
        senha_aberta += char_desc
        chave_atual = (chave_atual * 2) % 256

    return senha_aberta

def autenticar_usuario(login_input, senha_input):
    """Valida as credenciais do usuário diretamente no banco Firebird."""
    if not login_input or not login_input.strip():
        return False, "Informe o usuário."
    if not senha_input:
        return False, "Informe a senha."

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()

        query = """
            SELECT CODIGO, NOME, SENHA, CHGRUPO
            FROM TBL_USUARIO
            WHERE UPPER(TRIM(LOGIN)) = UPPER(?) AND ATIVO = 'S'
        """
        cursor.execute(query, (login_input.strip(),))
        usuario = cursor.fetchone()
        conexao.close()

        if usuario:
            codigo_db, nome_db, senha_criptografada_db, grupo_db = usuario
            senha_bruta = senha_criptografada_db.rstrip(' ') if senha_criptografada_db else ""
            senha_descriptografada = descriptografar_senha_xor(senha_bruta)

            if senha_input == senha_descriptografada:
                st.session_state['autenticado'] = True
                st.session_state['usuario_id'] = codigo_db
                st.session_state['usuario_nome'] = nome_db
                return True, "Sucesso"
            else:
                return False, "Usuário ou senha incorretos."
        else:
            return False, "Usuário ou senha incorretos."

    except Exception as e:
        logging.error(f"Erro na autenticação: {e}")
        return False, "Não foi possível conectar ao banco de dados. Contate o suporte."

# ==============================================================================
# 4. EXTRAÇÃO E TRATAMENTO DE DADOS (ETL + MÉTRICAS)
# ==============================================================================

# Valor padrão usado para preencher dimensões nulas vindas dos LEFT JOIN.
# Mantém os registros visíveis nos KPIs e filtros em vez de descartá-los
# silenciosamente (ver item 1 da revisão).
VALOR_NAO_INFORMADO = "Não informado"

def classificar_setor(tipo_processo):
    """Agrupa tipos de processos em macrossetores funcionais.

    OBS (melhoria estrutural sugerida, não aplicada aqui): a classificação por
    substring é sensível à ordem de verificação — um tipo como
    "TREINAMENTO DE SUPORTE" cai em Suporte por conter "SUPORT", mesmo tendo
    "TREINAM" (palavra-chave de Implantação). O ideal a médio prazo é migrar
    esse mapeamento para uma coluna SETOR na própria TBL_TIPO_PROCESSO.
    """
    if pd.isna(tipo_processo):
        return "Outro"

    texto = str(tipo_processo).strip().upper()
    if any(k in texto for k in ["SUPORT", "TICKET", "CHAMADO", "ERRO", "DÚVIDA", "DUVIDA", "RESET"]):
        return "Suporte"
    if any(k in texto for k in ["IMPLANT", "CONFIG", "TREINAM", "MIGRA"]):
        return "Implantação"
    if any(k in texto for k in ["DESENV", "MELHORIA", "EVOLU", "FEATURE", "BUG", "API"]):
        return "Desenvolvimento"
    return "Outro"

def checar_sla(row, hoje):
    """Classifica o cumprimento de SLA de uma demanda.

    Correção: antes, uma DATA_PREVISTA nula fazia a comparação
    `DATA_FINALIZACAO > DATA_PREVISTA` retornar False silenciosamente,
    classificando a demanda como "No Prazo" mesmo sem prazo definido — o que
    inflava artificialmente a Taxa de Cumprimento de SLA. Agora esse caso vira
    uma categoria própria, "Sem Prazo", que fica de fora do cálculo de atraso.
    """
    if pd.isnull(row['DATA_PREVISTA']):
        return "Sem Prazo"
    if pd.notnull(row['DATA_FINALIZACAO']):
        return "Atrasado" if row['DATA_FINALIZACAO'] > row['DATA_PREVISTA'] else "No Prazo"
    return "Atrasado (WIP)" if hoje > row['DATA_PREVISTA'] else "No Prazo (WIP)"

@st.cache_data(ttl=600, show_spinner=False)
def carregar_dados_processos(data_inicio, data_fim):
    """Busca as demandas no Firebird e gera métricas avançadas (Lead Time, Aging, SLA)."""
    conexao = conectar_banco()

    query = """
        SELECT
            p.CODIGO AS ID_PROCESSO,
            p."DATA" AS DATA_ABERTURA,
            p.DATA_FINALIZACAO,
            p.DATA_PREVISTA,
            s.DESCRICAO AS STATUS,
            tp.DESCRICAO AS TIPO_PROCESSO,
            c.NOME_FANTASIA AS CLIENTE,
            u.NOME AS RESPONSAVEL
        FROM TBL_PROCESSO p
        LEFT JOIN TBL_STATUS_SOLICITACAO s ON p.CHSTATUS = s.CODIGO
        LEFT JOIN TBL_TIPO_PROCESSO tp ON p.CHTIPO_PROCESSO = tp.CODIGO
        LEFT JOIN TBL_CLIENTE c ON p.CHCLIENTE = c.CODIGO
        LEFT JOIN TBL_USUARIO u ON p.CHRESPONSAVEL = u.CODIGO
        WHERE p."DATA" BETWEEN ? AND ?
    """

    df = pd.read_sql(query, conexao, params=(data_inicio, data_fim))
    conexao.close()

    if df.empty:
        return df

    # Conversão de Datas
    df['DATA_ABERTURA'] = pd.to_datetime(df['DATA_ABERTURA'], errors='coerce')
    df['DATA_FINALIZACAO'] = pd.to_datetime(df['DATA_FINALIZACAO'], errors='coerce')
    df['DATA_PREVISTA'] = pd.to_datetime(df['DATA_PREVISTA'], errors='coerce')

    # --- Tratamento de nulos nas dimensões (item 1 da revisão) ---
    # Em vez de deixar STATUS/TIPO_PROCESSO/CLIENTE/RESPONSAVEL nulos (o que os
    # fazia desaparecer dos multiselects e, por consequência, dos KPIs), eles
    # viram uma categoria explícita e visível. Um volume alto de
    # "Não informado" em RESPONSAVEL, por exemplo, já é em si um indicador de
    # gargalo de atribuição de demandas.
    for coluna in ['STATUS', 'TIPO_PROCESSO', 'CLIENTE', 'RESPONSAVEL']:
        df[coluna] = df[coluna].fillna(VALOR_NAO_INFORMADO)

    # Classificação por Setor
    df['SETOR'] = df['TIPO_PROCESSO'].apply(classificar_setor)

    # Cálculo do Lead Time (dias corridos para concluídos)
    df['LEAD_TIME_DIAS'] = (df['DATA_FINALIZACAO'] - df['DATA_ABERTURA']).dt.total_seconds() / (24 * 3600)

    # --- Validação de consistência do Lead Time (item 4 da revisão) ---
    # Datas de origem inconsistentes (finalização anterior à abertura) geram
    # Lead Time negativo, que puxa a média para baixo e mascara atrasos reais.
    # Aqui o valor é descartado (vira NaN) e a quantidade de casos é logada
    # para dar visibilidade à qualidade dos dados de origem.
    qtd_inconsistentes = int((df['LEAD_TIME_DIAS'] < 0).sum())
    if qtd_inconsistentes > 0:
        logging.warning(
            f"{qtd_inconsistentes} processo(s) com DATA_FINALIZACAO anterior à "
            f"DATA_ABERTURA foram desconsiderados do cálculo de Lead Time."
        )
    df.loc[df['LEAD_TIME_DIAS'] < 0, 'LEAD_TIME_DIAS'] = np.nan
    df['LEAD_TIME_INCONSISTENTE'] = df['LEAD_TIME_DIAS'].isna() & df['DATA_FINALIZACAO'].notna()

    # Cálculo do Aging (tempo em aberto para pendentes)
    hoje = pd.to_datetime(datetime.date.today())
    df['AGING_DIAS'] = np.where(
        df['DATA_FINALIZACAO'].isnull(),
        (hoje - df['DATA_ABERTURA']).dt.total_seconds() / (24 * 3600),
        np.nan
    )

    # Análise de Cumprimento de SLA (agora com categoria "Sem Prazo")
    df['SLA_STATUS'] = df.apply(lambda row: checar_sla(row, hoje), axis=1)
    df['ATRASADO'] = df['SLA_STATUS'].str.contains("Atrasado")

    return df

@st.cache_data(ttl=600, show_spinner=False)
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

# ==============================================================================
# 5. FLUXO PRINCIPAL DA APLICAÇÃO
# ==============================================================================

# Controle de Sessão de Autenticação
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    # --- TELA DE LOGIN ---
    st.title("🔐 Acesso ao Painel Executivo")
    st.markdown("Insira suas credenciais corporativas para prosseguir.")

    with st.form(key='form_login'):
        login = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar no Sistema")

    if entrar:
        sucesso, mensagem = autenticar_usuario(login, senha)
        if sucesso:
            st.rerun()
        else:
            st.error(mensagem)

else:
    # --- APLICAÇÃO AUTENTICADA ---

    # --- BARRA LATERAL (FILTROS CENTRALIZADOS) ---
    st.sidebar.title(f"Olá, {st.session_state.get('usuario_nome', 'Usuário')}!")
    st.sidebar.caption("Sessão Autenticada")

    if st.sidebar.button("🚪 Sair da Aplicação"):
        st.session_state.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Período de Abertura")

    hoje = datetime.date.today()
    trinta_dias_atras = hoje - datetime.timedelta(days=30)

    data_inicio = st.sidebar.date_input("Data Inicial", trinta_dias_atras)
    data_fim = st.sidebar.date_input("Data Final", hoje)

    # Carregamento primário com base nas datas
    with st.spinner("Consultando banco Firebird..."):
        df_base = carregar_dados_processos(data_inicio, data_fim)

    if df_base.empty:
        st.warning("Nenhum processo foi localizado no banco de dados para o intervalo selecionado.")
    else:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 Dimensões de Negócio")

        # --- Correção do bug de filtro vazio (item 2 da revisão) ---
        # Antes, `if selecao: df = df[...]` fazia com que deselecionar todas as
        # opções de um multiselect fosse ignorado (mostrando tudo), quando o
        # esperado é mostrar zero registros — o usuário ficava sem entender
        # por que o filtro "não funcionava". Agora o filtro é sempre aplicado;
        # lista vazia = resultado vazio, de forma explícita e previsível.

        # Filtro 1: Setor
        setores_disp = sorted(df_base["SETOR"].dropna().unique().tolist())
        setores_sel = st.sidebar.multiselect("Setor:", options=setores_disp, default=setores_disp)
        df_filtrado = df_base[df_base["SETOR"].isin(setores_sel)]

        # Filtro 2: Tipo de Processo (dinâmico em relação ao Setor)
        tipos_disp = sorted(df_filtrado["TIPO_PROCESSO"].dropna().unique().tolist())
        tipos_sel = st.sidebar.multiselect("Tipo de Processo:", options=tipos_disp, default=tipos_disp)
        df_filtrado = df_filtrado[df_filtrado["TIPO_PROCESSO"].isin(tipos_sel)]

        # Filtro 3: Responsável / Analista
        analistas_disp = sorted(df_filtrado["RESPONSAVEL"].dropna().unique().tolist())
        analistas_sel = st.sidebar.multiselect("Responsável:", options=analistas_disp, default=analistas_disp)
        df_filtrado = df_filtrado[df_filtrado["RESPONSAVEL"].isin(analistas_sel)]

        # Filtro 4: Cliente
        clientes_disp = sorted(df_filtrado["CLIENTE"].dropna().unique().tolist())
        clientes_sel = st.sidebar.multiselect("Cliente:", options=clientes_disp, default=clientes_disp)
        df_filtrado = df_filtrado[df_filtrado["CLIENTE"].isin(clientes_sel)]

        if df_filtrado.empty:
            st.info("Nenhum registro corresponde à combinação de filtros selecionada. Ajuste os filtros na barra lateral.")

        # ==============================================================================
        # 6. PAINEL PRINCIPAL (HEADER E KPIS EXECUTIVOS)
        # ==============================================================================
        st.title("📊 Painel Executivo de Gestão de Demandas & SLA")
        st.caption("Acompanhamento unificado de vazão, Lead Time, envelhecimento de fila (Aging) e conformidade de SLA.")
        st.markdown("---")

        # Métricas Calculadas
        vol_total = len(df_filtrado)
        df_abertos = df_filtrado[df_filtrado["DATA_FINALIZACAO"].isnull()]
        vol_abertos = len(df_abertos)

        tmr_medio = df_filtrado["LEAD_TIME_DIAS"].mean()
        aging_medio = df_abertos["AGING_DIAS"].mean()

        # --- Taxa de Atraso agora exclui explicitamente "Sem Prazo" do denominador ---
        # (ver checar_sla). Antes, um registro sem DATA_PREVISTA entrava como
        # "No Prazo" no denominador; agora ele só entra no total geral, mas não
        # é contado nem como atrasado nem como no prazo — evitando distorcer o
        # percentual de cumprimento de SLA.
        df_com_prazo = df_filtrado[df_filtrado["SLA_STATUS"] != "Sem Prazo"]
        total_com_prazo = len(df_com_prazo)
        total_atrasados = df_com_prazo["ATRASADO"].sum()
        taxa_atraso = (total_atrasados / total_com_prazo * 100) if total_com_prazo > 0 else 0.0
        qtd_sem_prazo = vol_total - total_com_prazo

        # Cartões em 5 colunas
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total de Demandas", f"{vol_total:,}", help="Volume total de demandas abertas no período selecionado.")
        col2.metric("Em Andamento (WIP)", f"{vol_abertos:,}", help="Demandas ativas que ainda não foram finalizadas.")
        col3.metric("Lead Time Médio", f"{tmr_medio:.1f} dias" if pd.notna(tmr_medio) else "N/A", help="Média de dias decorridos para os chamados já encerrados (exclui registros com datas inconsistentes).")
        col4.metric("Aging Médio (Fila)", f"{aging_medio:.1f} dias" if pd.notna(aging_medio) else "N/A", help="Tempo médio em que as demandas em aberto permanecem na fila.")
        col5.metric(
            "Taxa de Atraso (SLA)",
            f"{taxa_atraso:.1f}%",
            delta=f"{total_atrasados} fora do prazo | {qtd_sem_prazo} sem prazo definido",
            delta_color="inverse",
            help="Percentual de chamados com encerramento ou fila além do SLA previsto, calculado apenas sobre demandas com DATA_PREVISTA cadastrada."
        )

        # Guia de Interpretação dos KPIs Executivos
        with st.expander("💡 **Guia de Interpretação dos KPIs Executivos e Tomada de Decisão**", expanded=False):
            st.markdown("""
            * **Total de Demandas**: Mede o volume bruto de entrada. *Ponto de Atenção:* Um crescimento abrupto no volume indica gargalos externos, aumento de erros em entregas recentes ou sazonalidade.
            * **Em Andamento (WIP - Work In Progress)**: Representa o trabalho acumulado e pendente de conclusão. *Ponto de Atenção:* Se o WIP estiver muito elevado, ocorre perda de foco, aumento de troca de contexto (*context switching*) e dilatação nos prazos.
            * **Lead Time Médio**: Tempo médio decorrido desde a abertura até o encerramento das demandas concluídas. *Ponto de Atenção:* Um Lead Time alto aponta burocracia, gargalos em etapas intermediárias ou excesso de pendências de aprovação.
            * **Aging Médio (Fila)**: Idade média dos chamados que continuam abertos. *Ponto de Atenção:* Se o **Aging Médio for superior ao Lead Time Médio**, significa que a equipe está resolvendo os chamados mais novos/fáceis e acumulando um passivo antigo de demandas esquecidas na fila.
            * **Taxa de Atraso (SLA)**: Percentual de chamados estourados (já encerrados fora do prazo ou ativos e vencidos), considerando apenas demandas com prazo cadastrado. *Ponto de Atenção:* Taxas acima de 10-15% exigem intervenção imediata para repactuação de prazos com clientes ou reavaliação da capacidade de entrega (*capacity*). Um número alto de "sem prazo definido" é, por si só, um problema de qualidade de cadastro a ser corrigido.
            """)

        st.markdown("---")

        # ==============================================================================
        # 7. ABAS DE VISUALIZAÇÃO DE DADOS
        # ==============================================================================
        aba1, aba2, aba3, aba4, aba5 = st.tabs([
            "📈 Visão Geral & Tendências",
            "🚨 Status & Performance de SLA",
            "🔗 Esteira de Produção",
            "👥 Produtividade da Equipe",
            "🎯 KPIs Segmentados"
        ])

        # ------------------------------------------------------------------------------
        # ABA 1: TENDÊNCIAS TEMPORAIS E DISTRIBUIÇÃO POR ÁREA
        # ------------------------------------------------------------------------------
        with aba1:
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

        # ------------------------------------------------------------------------------
        # ABA 2: STATUS & PERFORMANCE DE SLA — ANÁLISE AVANÇADA
        # ------------------------------------------------------------------------------
        with aba2:
            st.subheader("🚨 Status & Performance de SLA")
            st.caption(
                "Diagnóstico operacional do status das demandas, risco atual de SLA, "
                "qualidade do cadastro de prazos e principais focos de atraso."
            )

            if df_filtrado.empty:
                st.info("Não há dados suficientes para analisar Status e SLA com os filtros atuais.")
            else:
                # ==============================================================
                # 1. RESUMO EXECUTIVO
                # ==============================================================
                df_com_prazo = df_filtrado[df_filtrado["SLA_STATUS"] != "Sem Prazo"].copy()
                df_abertos_sla = df_filtrado[df_filtrado["DATA_FINALIZACAO"].isnull()].copy()
                df_atrasados_wip = df_filtrado[
                    df_filtrado["SLA_STATUS"] == "Atrasado (WIP)"
                ].copy()
                df_atrasados_concluidos = df_filtrado[
                    df_filtrado["SLA_STATUS"] == "Atrasado"
                ].copy()

                total_sla = len(df_filtrado)
                total_com_prazo_sla = len(df_com_prazo)
                atrasados_total_sla = int(df_com_prazo["ATRASADO"].sum())
                atrasados_wip_sla = len(df_atrasados_wip)
                sem_prazo_sla = int(
                    (df_filtrado["SLA_STATUS"] == "Sem Prazo").sum()
                )

                taxa_atraso_sla = (
                    atrasados_total_sla / total_com_prazo_sla * 100
                    if total_com_prazo_sla > 0 else 0.0
                )
                taxa_risco_aberto_sla = (
                    atrasados_wip_sla / len(df_abertos_sla) * 100
                    if len(df_abertos_sla) > 0 else 0.0
                )
                taxa_cobertura_sla = (
                    total_com_prazo_sla / total_sla * 100
                    if total_sla > 0 else 0.0
                )
                aging_atrasados_wip = (
                    df_atrasados_wip["AGING_DIAS"].mean()
                    if not df_atrasados_wip.empty else np.nan
                )

                st.markdown("### 🚨 Resumo Executivo de SLA")
                sla_k1, sla_k2, sla_k3, sla_k4, sla_k5 = st.columns(5)

                sla_k1.metric(
                    "Taxa de Atraso",
                    f"{taxa_atraso_sla:.1f}%",
                    help=(
                        "Percentual de demandas atrasadas entre aquelas que "
                        "possuem prazo cadastrado."
                    )
                )
                sla_k2.metric(
                    "Atrasados em Aberto",
                    f"{atrasados_wip_sla:,}",
                    delta=f"{taxa_risco_aberto_sla:.1f}% dos chamados abertos",
                    delta_color="inverse",
                    help="Demandas abertas cujo prazo já foi ultrapassado."
                )
                sla_k3.metric(
                    "Atrasos Concluídos",
                    f"{len(df_atrasados_concluidos):,}",
                    help="Demandas encerradas depois da data prevista."
                )
                sla_k4.metric(
                    "Cobertura de SLA",
                    f"{taxa_cobertura_sla:.1f}%",
                    delta=f"{sem_prazo_sla} sem prazo",
                    delta_color="inverse",
                    help="Percentual de demandas com DATA_PREVISTA cadastrada."
                )
                sla_k5.metric(
                    "Aging dos Atrasados",
                    (
                        f"{aging_atrasados_wip:.1f} dias"
                        if pd.notna(aging_atrasados_wip) else "N/A"
                    ),
                    help=(
                        "Tempo médio em fila das demandas abertas que já "
                        "estão atrasadas."
                    )
                )

                st.markdown("---")

                # ==============================================================
                # 2. STATUS ATUAL + COMPOSIÇÃO DO SLA
                # ==============================================================
                col_s1, col_s2 = st.columns(2)

                with col_s1:
                    st.subheader("Distribuição por Status Atual")

                    status_df = (
                        df_filtrado["STATUS"]
                        .fillna("Não informado")
                        .value_counts()
                        .rename_axis("STATUS")
                        .reset_index(name="Quantidade")
                    )
                    status_df["Percentual"] = (
                        status_df["Quantidade"] / total_sla * 100
                    )

                    fig_status = px.bar(
                        status_df,
                        x="Quantidade",
                        y="STATUS",
                        orientation="h",
                        text="Quantidade",
                        color="Percentual",
                        color_continuous_scale="Blues",
                        template="plotly_white",
                        labels={
                            "STATUS": "",
                            "Quantidade": "Demandas",
                            "Percentual": "% do total"
                        }
                    )
                    fig_status.update_traces(
                        texttemplate="%{text}",
                        textposition="outside",
                        hovertemplate=(
                            "<b>%{y}</b><br>"
                            "Demandas: %{x}<br>"
                            "Participação: %{marker.color:.1f}%<extra></extra>"
                        )
                    )
                    fig_status.update_layout(
                        height=max(380, len(status_df) * 55),
                        coloraxis_showscale=False,
                        yaxis={"categoryorder": "total ascending"}
                    )
                    st.plotly_chart(fig_status, use_container_width=True)

                    with st.expander("📌 Diagnóstico do Status Atual"):
                        st.markdown(
                            """
                            * **Status de dependência externa:** podem inflar o Lead Time
                              e indicam necessidade de política de pausa, follow-up ou
                              escalonamento.
                            * **Acúmulo em validação/testes:** pode indicar gargalo na
                              etapa final antes da entrega.
                            * **Status com grande volume + alta taxa de atraso:** devem
                              ser tratados como candidatos prioritários a análise de
                              causa raiz.
                            """
                        )

                with col_s2:
                    st.subheader("Composição do SLA")

                    ordem_sla = [
                        "No Prazo",
                        "No Prazo (WIP)",
                        "Atrasado",
                        "Atrasado (WIP)",
                        "Sem Prazo"
                    ]

                    sla_df = (
                        df_filtrado["SLA_STATUS"]
                        .value_counts()
                        .reindex(ordem_sla, fill_value=0)
                        .rename_axis("SLA_STATUS")
                        .reset_index(name="Quantidade")
                    )
                    sla_df = sla_df[sla_df["Quantidade"] > 0]

                    fig_sla = px.pie(
                        sla_df,
                        names="SLA_STATUS",
                        values="Quantidade",
                        hole=0.55,
                        color="SLA_STATUS",
                        color_discrete_map={
                            "No Prazo": "#2CA02C",
                            "No Prazo (WIP)": "#1F77B4",
                            "Atrasado": "#D62728",
                            "Atrasado (WIP)": "#FF7F0E",
                            "Sem Prazo": "#BDBDBD"
                        },
                        template="plotly_white"
                    )
                    fig_sla.update_traces(
                        textposition="inside",
                        textinfo="percent+label",
                        hovertemplate=(
                            "<b>%{label}</b><br>"
                            "Quantidade: %{value}<br>"
                            "Participação: %{percent}<extra></extra>"
                        )
                    )
                    fig_sla.update_layout(height=430)
                    st.plotly_chart(fig_sla, use_container_width=True)

                    if taxa_atraso_sla >= 20:
                        st.error(
                            "🔴 **Situação crítica:** mais de 20% das demandas "
                            "com prazo estão atrasadas."
                        )
                    elif taxa_atraso_sla >= 10:
                        st.warning(
                            "🟠 **Situação de atenção:** a taxa de atraso exige "
                            "acompanhamento gerencial."
                        )
                    else:
                        st.success(
                            "🟢 **Situação controlada:** a taxa de atraso está "
                            "abaixo de 10%."
                        )

                    with st.expander("📌 Pontos Críticos sobre o SLA"):
                        st.markdown(
                            """
                            * **Atrasado (WIP):** alerta máximo — trabalho ainda aberto
                              que já ultrapassou o prazo e pode gerar impacto imediato.
                            * **Atrasado:** demanda concluída fora do prazo; deve ser
                              analisada para entender falha de estimativa, capacidade
                              ou execução.
                            * **Sem Prazo:** problema de qualidade de cadastro. Essas
                              demandas não entram no denominador da taxa de atraso.
                            * **No Prazo / No Prazo (WIP):** indicam operação dentro
                              do prazo previsto.
                            """
                        )

                st.markdown("---")

                # ==============================================================
                # 3. ONDE O SLA ESTÁ PIORANDO
                # ==============================================================
                st.subheader("🎯 Onde estão os principais riscos de SLA?")
                st.caption(
                    "Ranking por taxa de atraso, acompanhado do volume absoluto "
                    "para evitar conclusões baseadas somente em percentuais."
                )

                col_r1, col_r2 = st.columns(2)

                def _ranking_sla_segmento(coluna, titulo, container):
                    base = df_com_prazo.copy()

                    if base.empty:
                        container.info(
                            "Não há demandas com prazo para calcular este ranking."
                        )
                        return

                    ranking = (
                        base.groupby(coluna, dropna=False)
                        .agg(
                            Demandas=("ID_PROCESSO", "count"),
                            Atrasadas=("ATRASADO", "sum"),
                            Em_Aberto=(
                                "DATA_FINALIZACAO",
                                lambda x: x.isnull().sum()
                            ),
                            Lead_Time_Medio=("LEAD_TIME_DIAS", "mean")
                        )
                        .reset_index()
                    )

                    ranking["Taxa_Atraso"] = np.where(
                        ranking["Demandas"] > 0,
                        ranking["Atrasadas"] / ranking["Demandas"] * 100,
                        0
                    )

                    ranking = ranking.sort_values(
                        ["Taxa_Atraso", "Atrasadas", "Demandas"],
                        ascending=[False, False, False]
                    )

                    fig = px.bar(
                        ranking.head(12),
                        x="Taxa_Atraso",
                        y=coluna,
                        orientation="h",
                        text="Taxa_Atraso",
                        color="Atrasadas",
                        color_continuous_scale="Reds",
                        template="plotly_white",
                        labels={
                            coluna: "",
                            "Taxa_Atraso": "Taxa de atraso (%)",
                            "Atrasadas": "Qtd. atrasada"
                        },
                        title=titulo,
                        hover_data={
                            "Demandas": True,
                            "Atrasadas": True,
                            "Em_Aberto": True,
                            "Lead_Time_Medio": ":.1f",
                            "Taxa_Atraso": ":.1f"
                        }
                    )
                    fig.update_traces(
                        texttemplate="%{text:.1f}%",
                        textposition="outside"
                    )
                    fig.update_layout(
                        height=450,
                        coloraxis_showscale=False,
                        xaxis_range=[
                            0,
                            max(
                                100,
                                float(ranking["Taxa_Atraso"].max()) * 1.15
                            )
                        ],
                        yaxis={"categoryorder": "total ascending"}
                    )
                    container.plotly_chart(
                        fig,
                        use_container_width=True
                    )

                with col_r1:
                    _ranking_sla_segmento(
                        "SETOR",
                        "Atraso por Setor",
                        st
                    )

                with col_r2:
                    _ranking_sla_segmento(
                        "TIPO_PROCESSO",
                        "Atraso por Tipo de Processo",
                        st
                    )

                st.markdown("---")

                # ==============================================================
                # 4. MATRIZ STATUS x SLA
                # ==============================================================
                st.subheader("🧭 Matriz de Status x Risco de SLA")

                matriz_sla = pd.crosstab(
                    df_filtrado["STATUS"].fillna("Não informado"),
                    df_filtrado["SLA_STATUS"],
                    normalize="index"
                ) * 100

                for coluna in [
                    "Atrasado",
                    "Atrasado (WIP)",
                    "No Prazo",
                    "No Prazo (WIP)",
                    "Sem Prazo"
                ]:
                    if coluna not in matriz_sla.columns:
                        matriz_sla[coluna] = 0.0

                matriz_sla = matriz_sla[
                    [
                        "Atrasado",
                        "Atrasado (WIP)",
                        "No Prazo",
                        "No Prazo (WIP)",
                        "Sem Prazo"
                    ]
                ].sort_values(
                    ["Atrasado (WIP)", "Atrasado"],
                    ascending=False
                )

                if not matriz_sla.empty:
                    fig_matriz_sla = px.imshow(
                        matriz_sla.round(1),
                        text_auto=".1f",
                        aspect="auto",
                        color_continuous_scale="RdYlGn_r",
                        labels={
                            "x": "Situação de SLA",
                            "y": "Status atual",
                            "color": "% dentro do status"
                        }
                    )
                    fig_matriz_sla.update_layout(
                        height=max(420, len(matriz_sla) * 55)
                    )
                    st.plotly_chart(
                        fig_matriz_sla,
                        use_container_width=True
                    )

                st.caption(
                    "Priorize os status com maior concentração de "
                    "**Atrasado (WIP)**: são demandas abertas que já ultrapassaram "
                    "o prazo."
                )

                st.markdown("---")

                # ==============================================================
                # 5. EVOLUÇÃO TEMPORAL DO RISCO
                # ==============================================================
                st.subheader("📈 Evolução do Risco de SLA")

                df_temporal_sla = df_filtrado.copy()
                df_temporal_sla["MES_ABERTURA"] = (
                    pd.to_datetime(
                        df_temporal_sla["DATA_ABERTURA"],
                        errors="coerce"
                    )
                    .dt.to_period("M")
                    .astype(str)
                )

                evolucao_sla = (
                    df_temporal_sla
                    .groupby("MES_ABERTURA")
                    .agg(
                        Demandas=("ID_PROCESSO", "count"),
                        Com_Prazo=(
                            "SLA_STATUS",
                            lambda s: (s != "Sem Prazo").sum()
                        ),
                        Atrasadas=("ATRASADO", "sum"),
                        Sem_Prazo=(
                            "SLA_STATUS",
                            lambda s: (s == "Sem Prazo").sum()
                        )
                    )
                    .reset_index()
                )

                evolucao_sla["Taxa_Atraso"] = np.where(
                    evolucao_sla["Com_Prazo"] > 0,
                    evolucao_sla["Atrasadas"]
                    / evolucao_sla["Com_Prazo"] * 100,
                    np.nan
                )

                evolucao_sla["Cobertura_SLA"] = np.where(
                    evolucao_sla["Demandas"] > 0,
                    evolucao_sla["Com_Prazo"]
                    / evolucao_sla["Demandas"] * 100,
                    np.nan
                )

                if not evolucao_sla.empty:
                    fig_evolucao_sla = px.line(
                        evolucao_sla,
                        x="MES_ABERTURA",
                        y=["Taxa_Atraso", "Cobertura_SLA"],
                        markers=True,
                        template="plotly_white",
                        labels={
                            "MES_ABERTURA": "Mês de abertura",
                            "value": "Percentual (%)",
                            "variable": "Indicador"
                        }
                    )
                    fig_evolucao_sla.update_layout(
                        height=380,
                        legend_title_text=""
                    )
                    st.plotly_chart(
                        fig_evolucao_sla,
                        use_container_width=True
                    )

                st.markdown("---")

                # ==============================================================
                # 6. FILA DE PRIORIDADE
                # ==============================================================
                st.subheader(
                    "🔥 Fila de Prioridade: Demandas Abertas e Atrasadas"
                )

                if df_atrasados_wip.empty:
                    st.success(
                        "Não existem demandas abertas e atrasadas com os filtros atuais."
                    )
                else:
                    prioridade_sla = df_atrasados_wip.copy()

                    colunas_prioridade = [
                        "ID_PROCESSO",
                        "CLIENTE",
                        "SETOR",
                        "TIPO_PROCESSO",
                        "RESPONSAVEL",
                        "STATUS",
                        "DATA_ABERTURA",
                        "DATA_PREVISTA",
                        "AGING_DIAS"
                    ]

                    prioridade_sla = prioridade_sla[
                        [
                            c for c in colunas_prioridade
                            if c in prioridade_sla.columns
                        ]
                    ].sort_values(
                        "AGING_DIAS",
                        ascending=False
                    )

                    st.dataframe(
                        prioridade_sla,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "AGING_DIAS": st.column_config.NumberColumn(
                                "Aging (dias)",
                                format="%.1f"
                            ),
                            "DATA_ABERTURA": st.column_config.DateColumn(
                                "Abertura"
                            ),
                            "DATA_PREVISTA": st.column_config.DateColumn(
                                "Prazo"
                            )
                        }
                    )

                # ==============================================================
                # 7. GUIA GERENCIAL
                # ==============================================================
                with st.expander(
                    "📌 Como usar esta análise para tomada de decisão",
                    expanded=False
                ):
                    st.markdown(
                        """
                        **1. Ataque o atraso em aberto primeiro.** Demandas em
                        `Atrasado (WIP)` ainda podem ser recuperadas e devem ser
                        priorizadas conforme Aging, cliente e impacto.

                        **2. Procure concentrações.** Se um setor, tipo de processo
                        ou status concentra atrasos, a causa provavelmente é
                        sistêmica — não apenas casos isolados.

                        **3. Diferencie atraso operacional de problema de cadastro.**
                        Uma cobertura de SLA baixa significa que parte da operação
                        nem pode ser medida corretamente.

                        **4. Observe a tendência.** Taxa de atraso subindo mês a mês
                        indica deterioração da capacidade; cobertura de SLA caindo
                        indica perda de qualidade do planejamento.

                        **5. Não use apenas percentuais.** Sempre avalie taxa +
                        quantidade de demandas para evitar conclusões baseadas em
                        grupos muito pequenos.
                        """
                    )

        # ------------------------------------------------------------------------------
        # ABA 3: ESTEIRA DE PROCESSOS RECURSIVA (PAI / FILHO)
        # ------------------------------------------------------------------------------
        with aba3:
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
        # ABA 4: PERFORMANCE DA EQUIPE DE ANALISTAS
        # ------------------------------------------------------------------------------
        with aba4:
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
        # ABA 5: KPIS SEGMENTADOS (SUPORTE E IMPLANTAÇÃO)
        # ------------------------------------------------------------------------------
        with aba5:
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