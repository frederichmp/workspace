"""
Teste Ativo de Tentativa de Escrita com Usuário de Leitura (D4 - Sandbox Apenas).

Marcado com @pytest.mark.sandbox_only e pulado se ORACLE_SANDBOX != '1'.
Tenta INSERT via ORACLE_USER_READ, espera ORA-01031. Se obtiver sucesso por qualquer
motivo, executa rollback imediato e falha o teste com mensagem explícita.
"""

import os
from pathlib import Path
import pytest
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.is_file():
    load_dotenv(dotenv_path=env_path, override=False)

import oracledb


@pytest.mark.sandbox_only
def test_privilegio_write_insert_rejeitado_sandbox():
    """Tenta executar um INSERT direto utilizando ORACLE_USER_READ em ambiente de sandbox."""
    if os.getenv("ORACLE_SANDBOX") != "1":
        pytest.skip("Teste de escrita em banco permitido apenas em ambiente de sandbox (ORACLE_SANDBOX=1).")

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

        try:
            cursor.execute(
                "INSERT INTO startupadmin.tb_teste_executor (id, nome) VALUES (9999, 'tentativa_escrita_sandbox')"
            )
            # Se chegou aqui, o INSERT teve sucesso indevido!
            connection.rollback()
            pytest.fail(
                "FALHA CRÍTICA DE SEGURANÇA: Usuário ORACLE_USER_READ conseguiu inserir registros! "
                "Rollback imediato executado."
            )
        except oracledb.DatabaseError as exc:
            erro_str = str(exc)
            assert "ORA-01031" in erro_str, (
                f"Esperado erro ORA-01031 (insufficient privileges), mas obteve: {erro_str}"
            )

        # L5: Confirmação via conexão administrativa/mut de que nenhuma linha foi persistida
        user_mut = os.getenv("ORACLE_USER_MUT")
        pass_mut = os.getenv("ORACLE_PASSWORD_MUT")
        if user_mut and pass_mut:
            conn_mut = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn)
            cur_mut = conn_mut.cursor()
            cur_mut.execute("SELECT COUNT(*) FROM startupadmin.tb_teste_executor WHERE id = 9999")
            count = cur_mut.fetchone()[0]
            cur_mut.close()
            conn_mut.close()
            assert count == 0, "Falha de persistência: linha foi inserida indevidamente!"

    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
