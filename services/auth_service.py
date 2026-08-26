"""Regras de autenticação."""
import logging
import streamlit as st
from database.connection import conectar_banco


def descriptografar_senha_xor(senha_criptografada, chave_inicial=2):
    senha_aberta = ""
    chave_atual = chave_inicial
    for char in senha_criptografada:
        senha_aberta += chr(ord(char) ^ chave_atual)
        chave_atual = (chave_atual * 2) % 256
    return senha_aberta


def autenticar_usuario(login_input, senha_input):
    if not login_input or not login_input.strip(): return False, "Informe o usuário."
    if not senha_input: return False, "Informe a senha."
    try:
        conexao = conectar_banco(); cursor = conexao.cursor()
        query = """
            SELECT CODIGO, NOME, SENHA, CHGRUPO FROM TBL_USUARIO
            WHERE UPPER(TRIM(LOGIN)) = UPPER(?) AND ATIVO = 'S'
        """
        cursor.execute(query, (login_input.strip(),)); usuario = cursor.fetchone(); conexao.close()
        if usuario:
            codigo_db, nome_db, senha_criptografada_db, grupo_db = usuario
            senha_bruta = senha_criptografada_db.rstrip(' ') if senha_criptografada_db else ""
            if senha_input == descriptografar_senha_xor(senha_bruta):
                st.session_state['autenticado'] = True
                st.session_state['usuario_id'] = codigo_db
                st.session_state['usuario_nome'] = nome_db
                return True, "Sucesso"
        return False, "Usuário ou senha incorretos."
    except Exception as e:
        logging.error(f"Erro na autenticação: {e}")
        return False, "Não foi possível conectar ao banco de dados. Contate o suporte."
