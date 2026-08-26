# Dashboard Executivo — estrutura modular

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
