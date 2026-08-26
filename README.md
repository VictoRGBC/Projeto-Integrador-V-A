# Dashboard Executivo — estrutura modular

O monólito original foi separado por responsabilidade, mantendo as cinco abas e a lógica de acesso ao Firebird.

## Camadas
- `config/`: configurações.
- `database/`: conexão Firebird.
- `services/`: autenticação, ETL e consultas.
- `views/`: Streamlit, filtros, KPIs e gráficos.
- `app.py`: composição/orquestração.

## Executar
```bash
pip install -r requirements.txt
streamlit run app.py
```

A configuração `st.secrets["db"]` continua sendo suportada.
