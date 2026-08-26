"""Camada de conexão com o Firebird."""
import fdb
from config.settings import DB_CONFIG


def conectar_banco():
    cfg = DB_CONFIG
    dsn_conexao = f"{cfg['host']}/{cfg['port']}:{cfg['path']}"
    return fdb.connect(
        dsn=dsn_conexao, user=cfg['user'], password=cfg['password'], charset='WIN1252'
    )
