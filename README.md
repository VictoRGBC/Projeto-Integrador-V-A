# Dashboard Analítico Executivo - Integra Engenharia de Sistemas

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white"/>
  <img src="https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white"/>
  <img src="https://img.shields.io/badge/Plotly-239120?style=for-the-badge&logo=plotly&logoColor=white"/>
  <img src="https://img.shields.io/badge/Firebird-E2241C?style=for-the-badge&logo=Firebird&logoColor=white"/>
</p>

## Sobre o Projeto
Este repositório contém o código-fonte e a documentação da solução analítica desenvolvida para a disciplina de **Projeto Integrador V - A**, do curso de **Big Data e Inteligência Artificial** da **PUC Goiás**.

O projeto possui caráter **extensionista** e foi desenvolvido em parceria com a **Integra Engenharia de Sistemas**. O objetivo principal foi solucionar a falta de visibilidade centralizada de SLA e gargalos operacionais por meio do desenvolvimento de uma aplicação web analítica interativa (Dashboard Executivo), integrada diretamente ao banco de dados relacional legado (Firebird) da empresa.

## Objetivos
- **Geral:** Desenvolver e implementar uma aplicação analítica web interativa para monitoramento em tempo real de KPIs de processos, conformidade de SLA e análise de gargalos operacionais.
- **Específicos:**
  - Estruturar uma arquitetura modular em Python (config, database, services, views).
  - Desenvolver um pipeline ETL via consultas SQL parametrizadas.
  - Implementar Consultas Avançadas (CTE Recursivas) para medir Lead Time consolidado.
  - Construir módulo de autenticação próprio e seguro integrado ao banco de dados (Criptografia XOR).
  - Aplicar conceitos de *Data Storytelling* e Design de Informação na interface visual.

## Arquitetura de Dados
A solução foi arquitetada em três camadas principais:
1. **Banco de Dados (Origem):** Firebird DB (Esquema estrela/floco de neve centrado na `TBL_PROCESSO`).
2. **Processamento ETL (Meio):** Python e Pandas, encarregados da conexão (via `fdb`), extração parametrizada, limpeza e tratamento de dados nulos/tipagem.
3. **Dashboard Web (Visualização):** Streamlit e Plotly, encarregados da renderização interativa e redução de ruído gráfico.

## Indicadores-Chave de Desempenho (KPIs)
O dashboard monitora os seguintes indicadores críticos de negócio:
* **Volume Total de Processos:** Chamados abertos/processados.
* **Lead Time Operacional:** Tempo médio em dias entre abertura e conclusão.
* **Índice de Conformidade e Taxa de Atraso (SLA):** Percentual de processos dentro do prazo vs. fora do prazo/WIP atrasado.
* **Média de Repasses por Esteira:** Trocas de setor/fases durante o ciclo de vida da demanda.
* **Produtividade por Analista/Setor:** Volume de demandas concluídas por usuário.

## Navegação e Data Storytelling
A aplicação foi desenhada de forma descendente (do macro para o micro), dividida em 5 abas principais para guiar a tomada de decisão:
1. **Visão Geral & Tendências:** Panorama macro da operação e entradas vs. saídas.
2. **Status & Performance de SLA:** Foco na saúde dos prazos e identificação de chamados em risco.
3. **Esteira de Produção:** Rastreamento de processos, gráficos de dispersão (complexidade vs durabilidade) e ranking de gargalos.
4. **Produtividade da Equipe:** Performance individual e distribuição da carga de trabalho.
5. **KPIs Segmentados:** Cruzamentos específicos e análises granulares.

## Como Executar o Projeto

### Pré-requisitos
- Python 3.9+
- Driver nativo Firebird (`fbclient.dll` ou equivalente configurado no SO)
- Credenciais de acesso ao banco de dados da organização (arquivo `.env`)

### Instalação
1. Clone este repositório:
   ```bash
   git clone https://github.com/VictoRGBC/Projeto-Integrador-V-A.git
   ```
2. Acesse a pasta do projeto:
   ```bash
   cd Projeto-Integrador-V-A
   ```
3. Crie um ambiente virtual (recomendado):
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate  # Windows
   ```
4. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
5. Execute a aplicação:
   ```bash
   streamlit run app.py
   ```

## 👥 Autores
* **Victor Gabriel Barros Moreira**
* **Rairon Braga**

**Instituição:** Pontifícia Universidade Católica de Goiás (PUC Goiás)  
**Ano:** 2026
