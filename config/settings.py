"""Configurações da aplicação e do banco de dados."""
import os
import platform
from pathlib import Path
import streamlit as st
import fdb


def obter_config_db():
    """Lê a configuração via st.secrets, com fallback para variáveis de ambiente."""
    try:
        cfg = st.secrets["db"]
        return {
            "host": cfg["host"], "path": cfg["path"], "user": cfg["user"],
            "password": cfg["password"], "port": int(cfg.get("port", 3050)),
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
BASE_DIR = Path(__file__).resolve().parents[1]

if platform.system() == "Windows":
    DLL_PATH = BASE_DIR / "fbclient.dll"
    if DLL_PATH.exists():
        fdb.load_api(str(DLL_PATH))
