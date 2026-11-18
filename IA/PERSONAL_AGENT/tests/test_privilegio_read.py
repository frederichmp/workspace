"""
Teste de Privilégios Somente Leitura (D4 - DAC / Menor Privilégio).

Valida via metadados do dicionário de dados do Oracle (SESSION_PRIVS, USER_SYS_PRIVS,
USER_ROLE_PRIVS e USER_TAB_PRIVS) que a conta configurada em ORACLE_USER_READ
não possui privilégios de escrita no banco de dados.
NÃO executa nenhum comando de escrita (DML/DDL).
"""

import os
import pytest

import oracledb

PRIVILEGIOS_ESCRITA_PROIBIDOS = {
    "INSERT ANY TABLE",
    "UPDATE ANY TABLE",
    "DELETE ANY TABLE",
    "CREATE ANY TABLE",
    "DROP ANY TABLE",
    "ALTER ANY TABLE",
    "CREATE TABLE",
    "EXECUTE ANY PROCEDURE",
    "DBA",
}


@pytest.mark.sandbox_only
def test_privilegio_read_sem_permissoes_de_escrita():
    """Valida que o usuário de leitura possui apenas permissões de leitura."""
    user = os.getenv("ORACLE_USER_READ")
    password = os.getenv("ORACLE_PASSWORD_READ")
    dsn = os.getenv("ORACLE_DSN")

    assert user, "Variável ORACLE_USER_READ deve estar configurada no .env"
    assert password, "Variável ORACLE_PASSWORD_READ deve estar configurada no .env"
    assert dsn, "Variável ORACLE_DSN deve estar configurada no .env"

    connection = None
    try:
        connection = oracledb.connect(user=user, password=password, dsn=dsn)
        cursor = connection.cursor()

        # 1. Consulta SESSION_PRIVS
        cursor.execute("SELECT privilege FROM session_privs")
        session_privs = {row[0].upper() for row in cursor.fetchall()}
        privs_escrita_sessao = session_privs.intersection(PRIVILEGIOS_ESCRITA_PROIBIDOS)
        assert not privs_escrita_sessao, (
            f"Privilégios de escrita proibidos encontrados em SESSION_PRIVS: {privs_escrita_sessao}"
        )

        # 2. Consulta USER_SYS_PRIVS
        cursor.execute("SELECT privilege FROM user_sys_privs")
        user_sys_privs = {row[0].upper() for row in cursor.fetchall()}
        privs_escrita_sys = user_sys_privs.intersection(PRIVILEGIOS_ESCRITA_PROIBIDOS)
        assert not privs_escrita_sys, (
            f"Privilégios de escrita proibidos encontrados em USER_SYS_PRIVS: {privs_escrita_sys}"
        )

        # 3. Consulta USER_ROLE_PRIVS
        cursor.execute("SELECT granted_role FROM user_role_privs")
        user_roles = {row[0].upper() for row in cursor.fetchall()}
        for role in user_roles:
            assert "DBA" not in role, f"Role DBA proibida atribuída a usuário de leitura: {role}"
            if "CONNECT" in role:
                # Verifica se CONNECT tem algo além de básico
                pass

        # 4. Consulta USER_TAB_PRIVS sobre tb_teste_executor
        cursor.execute("""
            SELECT privilege 
            FROM user_tab_privs 
            WHERE UPPER(table_name) = 'TB_TESTE_EXECUTOR'
        """)
        tab_privs = {row[0].upper() for row in cursor.fetchall()}
        tab_privs_escrita = tab_privs.intersection({"INSERT", "UPDATE", "DELETE", "ALTER"})
        assert not tab_privs_escrita, (
            f"Privilégios de escrita na tabela de teste encontrados em USER_TAB_PRIVS: {tab_privs_escrita}"
        )

    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
