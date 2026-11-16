"""
Suite de Testes Automatizados do Executor Seguro de Scripts Oracle (tests/test_executor.py).
Cobre os 13 cenários obrigatórios (T1 a T13) com validação de governança, tokenização,
segurança contra SQL Injection, segregação de privilégios e integridade transacional.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import oracledb
import pytest
from dotenv import load_dotenv

# Adiciona o diretório raiz do projeto PERSONAL_AGENT ao PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Carrega variáveis de ambiente
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

from src.tools.executor import executar_script
from src.tools.registry import carregar_registro


@pytest.fixture(scope="session", autouse=True)
def setup_banco_teste():
    """
    Fixture de sessão: garante que o ambiente de teste no Oracle esteja provisionado
    (tabela de teste startupadmin.tb_teste_executor e permissões para startup_read).
    """
    user_mut = os.getenv("ORACLE_USER_MUT") or os.getenv("ORACLE_USER")
    pass_mut = os.getenv("ORACLE_PASSWORD_MUT") or os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")

    if not all([user_mut, pass_mut, dsn]):
        pytest.skip("Credenciais Oracle não configuradas no .env. Pulando testes que requerem conexão viva.")

    try:
        conn = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn)
        cur = conn.cursor()

        # Cria ou limpa tabela de teste descartável
        try:
            cur.execute("""
                CREATE TABLE startupadmin.tb_teste_executor (
                    id NUMBER PRIMARY KEY,
                    nome VARCHAR2(100),
                    conteudo_lob CLOB
                )
            """)
        except oracledb.DatabaseError as e:
            if "ORA-00955" not in str(e):
                raise

        # Limpa dados de testes anteriores
        cur.execute("DELETE FROM startupadmin.tb_teste_executor WHERE id IN (1, 998, 999, 99999)")
        conn.commit()

        # Garante concessão de SELECT para startup_read
        user_read = os.getenv("ORACLE_USER_READ", "startup_read")
        try:
            cur.execute(f"GRANT SELECT ON startupadmin.tb_teste_executor TO {user_read}")
            conn.commit()
        except oracledb.DatabaseError:
            pass

        cur.close()
        conn.close()
    except Exception as e:
        pytest.skip(f"Não foi possível conectar ao banco Oracle para setup: {e}")


# =============================================================================
# T1: Hash alterado -> HASH_DIVERGENTE e NENHUMA conexão aberta
# =============================================================================
def test_t1_hash_alterado_sem_conexao():
    """
    T1: Verifica que arquivo com hash divergente do homologado é recusado
    com HASH_DIVERGENTE e oracledb.connect NÃO é invocado (sem conexão aberta).
    """
    with patch("oracledb.connect") as mock_connect:
        saida_str = executar_script("script_hash_divergente", {})
        resultado = json.loads(saida_str)

        assert resultado["status"] == "recusado"
        assert resultado["motivo"] == "HASH_DIVERGENTE"
        assert "diverge" in resultado["mensagem"].lower()
        mock_connect.assert_not_called()


# =============================================================================
# T2: script_id inexistente -> NAO_EXISTE, sem conexão
# =============================================================================
def test_t2_script_id_inexistente_sem_conexao():
    """
    T2: Verifica que script_id inexistente é recusado com NAO_EXISTE
    e nenhuma conexão é aberta no Oracle.
    """
    with patch("oracledb.connect") as mock_connect:
        saida_str = executar_script("script_id_inexistente_totalmente_aleatorio", {})
        resultado = json.loads(saida_str)

        assert resultado["status"] == "recusado"
        assert resultado["motivo"] == "NAO_EXISTE"
        mock_connect.assert_not_called()


# =============================================================================
# T3: Status bloqueado -> BLOQUEADO, sem conexão
# =============================================================================
def test_t3_status_bloqueado_sem_conexao():
    """
    T3: Verifica que script homologado com status != 'homologado' (bloqueado)
    é recusado com BLOQUEADO e nenhuma conexão é aberta.
    """
    with patch("oracledb.connect") as mock_connect:
        saida_str = executar_script("script_bloqueado", {})
        resultado = json.loads(saida_str)

        assert resultado["status"] == "recusado"
        assert resultado["motivo"] == "BLOQUEADO"
        assert "bloqueado" in resultado["mensagem"].lower()
        mock_connect.assert_not_called()


# =============================================================================
# T4: Dois SELECTs separados por ';' -> MULTIPLOS_STATEMENTS
# =============================================================================
def test_t4_multiplos_statements_rejeitados():
    """
    T4: Tokenizador detecta mais de um statement SQL e recusa com MULTIPLOS_STATEMENTS,
    sem conectar ao banco.
    """
    with patch("oracledb.connect") as mock_connect:
        saida_str = executar_script("multiplos_statements_t4", {})
        resultado = json.loads(saida_str)

        assert resultado["status"] == "recusado"
        assert resultado["motivo"] == "MULTIPLOS_STATEMENTS"
        mock_connect.assert_not_called()


# =============================================================================
# T5: ';' dentro de string literal e comentário, um único SELECT -> executa
# =============================================================================
def test_t5_ponto_e_virgula_em_literal_e_comentario():
    """
    T5: Um único SELECT com ponto-e-vírgula em literais e comentários é tokenizado
    corretamente como statement único e executado normalmente no Oracle.
    """
    saida_str = executar_script("select_t5_complexo", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "sucesso"
    assert resultado["tipo"] == "SELECT"
    assert len(resultado["saida"]) == 1
    assert resultado["saida"][0]["col1"] == "valor;com;ponto_e_virgula"
    assert resultado["saida"][0]["col2"] == "literal;q"


# =============================================================================
# T6: Bloco BEGIN...END com ';' internos -> executa como um statement
# =============================================================================
def test_t6_bloco_plsql_com_pontos_e_virgulas_internos():
    """
    T6: Bloco PL/SQL com ponto-e-vírgulas internos é reconhecido como statement único
    e executado com sucesso no Oracle.
    """
    saida_str = executar_script("plsql_bloco_t6", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "sucesso"
    assert resultado["tipo"] == "PLSQL"


# =============================================================================
# T7: CREATE PROCEDURE com ';' internos e sem '/' -> executa como um statement
# =============================================================================
def test_t7_create_procedure_sem_barra():
    """
    T7: Instrução DDL/PLSQL CREATE PROCEDURE com ponto-e-vírgulas internos
    e sem '/' final executa normalmente como um único statement.
    """
    saida_str = executar_script("procedure_t7", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "sucesso"
    assert resultado["tipo"] in ("DDL", "PLSQL")


# =============================================================================
# T8: Arquivo contendo linha "/" ou "SET ..." -> DIRETIVA_SQLPLUS
# =============================================================================
def test_t8_diretivas_sqlplus_recusadas():
    """
    T8: Valida que diretivas exclusivas do SQL*Plus (SET, /, etc.) são recusadas
    com o motivo DIRETIVA_SQLPLUS sem conectar ao banco e sem remoção silenciosa.
    """
    with patch("oracledb.connect") as mock_connect:
        # Teste 1: Arquivo com SET SERVEROUTPUT ON
        res_set = json.loads(executar_script("diretiva_sqlplus_t8", {}))
        assert res_set["status"] == "recusado"
        assert res_set["motivo"] == "DIRETIVA_SQLPLUS"
        assert "set" in res_set["mensagem"].lower()

        # Teste 2: Arquivo com barra '/' isolada
        res_slash = json.loads(executar_script("diretiva_slash_t8", {}))
        assert res_slash["status"] == "recusado"
        assert res_slash["motivo"] == "DIRETIVA_SQLPLUS"
        assert "barra" in res_slash["mensagem"].lower() or "/" in res_slash["mensagem"]

        mock_connect.assert_not_called()


# =============================================================================
# T9: Bind com "' OR 1=1 --" em SELECT parametrizado -> sem alteração de statement
# Validar em V$SQL: texto do SQL contém :nome, não o valor injetado.
# =============================================================================
def test_t9_bind_injetado_sem_alteracao_statement_v_sql():
    """
    T9: Tentativa de SQL Injection via bind nomeado.
    Executa a query com o valor "' OR 1=1 --".
    Valida diretamente na GV$SQL / V$SQL que o texto da instrução preserva :nome
    e não contém a string maliciosa injetada.
    """
    saida_str = executar_script("select_param_t9", {"nome": "' OR 1=1 --"})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "sucesso"
    # A consulta deve retornar zero linhas porque procurou literalmente pelo valor
    assert resultado["linhas_afetadas"] == 0

    # Validação rigorosa na V$SQL do Oracle
    user_mut = os.getenv("ORACLE_USER_MUT") or os.getenv("ORACLE_USER")
    pass_mut = os.getenv("ORACLE_PASSWORD_MUT") or os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")

    conn = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn)
    cur = conn.cursor()
    cur.execute("""
        SELECT sql_text
        FROM v$sql
        WHERE sql_text LIKE '%T9_VALIDACAO_INJECTION_PARAM%'
          AND sql_text NOT LIKE '%v$sql%'
    """)
    linhas_vsql = cur.fetchall()
    cur.close()
    conn.close()

    assert len(linhas_vsql) > 0, "Instrução não foi localizada na V$SQL do Oracle."
    sql_text_oracle = linhas_vsql[0][0]

    # Evidência técnica inquestionável: o texto compilado possui o bind :nome
    assert ":nome" in sql_text_oracle
    # E a string injetada NÃO foi interpolada no texto do comando
    assert "' OR 1=1 --" not in sql_text_oracle


# =============================================================================
# T10: Bind com nome não declarado ou extra -> BIND_INVALIDO
# =============================================================================
def test_t10_bind_com_nome_nao_declarado():
    """
    T10: Passar parâmetro de bind extra ou faltante recusa com BIND_INVALIDO
    sem abrir conexão com o banco de dados.
    """
    with patch("oracledb.connect") as mock_connect:
        # Caso 1: Bind extra não declarado
        res_extra = json.loads(
            executar_script("select_param_t9", {"nome": "teste", "parametro_extra_hacker": "ataque"})
        )
        assert res_extra["status"] == "recusado"
        assert res_extra["motivo"] == "BIND_INVALIDO"

        # Caso 2: Bind obrigatório faltante
        res_faltante = json.loads(executar_script("select_param_t9", {}))
        assert res_faltante["status"] == "recusado"
        assert res_faltante["motivo"] == "BIND_INVALIDO"

        mock_connect.assert_not_called()


# =============================================================================
# T11: Usuário de leitura executando script DML -> ORA-01031 (privilégio) e nada persistido
# =============================================================================
def test_t11_usuario_leitura_executando_dml_ora_01031():
    """
    T11: Um script classificado como SELECT (que conecta com ORACLE_USER_READ / startup_read)
    tentando executar DML no banco resulta em ORA-01031 (insufficient privileges),
    sendo capturado com ERRO_ORACLE e sem persistir nenhuma linha.
    """
    saida_str = executar_script("dml_tentativa_read_t11", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "erro"
    assert resultado["motivo"] == "ERRO_ORACLE"
    assert "ORA-01031" in resultado["mensagem"]

    # Valida diretamente no banco que nenhuma linha foi persistida
    user_mut = os.getenv("ORACLE_USER_MUT") or os.getenv("ORACLE_USER")
    pass_mut = os.getenv("ORACLE_PASSWORD_MUT") or os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")

    conn = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM startupadmin.tb_teste_executor WHERE id = 998")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()

    assert count == 0, "Falha de isolamento: registro foi persistido indevidamente pelo usuário de leitura!"


# =============================================================================
# T12: SELECT com LOB -> truncado conforme limite
# =============================================================================
def test_t12_select_com_lob_truncado():
    """
    T12: Valida que colunas do tipo CLOB são truncadas no limite seguro configurado
    (500 caracteres) acompanhadas do marcador de truncamento.
    """
    saida_str = executar_script("select_lob_t12", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "sucesso"
    assert len(resultado["saida"]) == 1
    lob_texto = resultado["saida"][0]["grande_lob"]

    assert "[LOB TRUNCADO]" in lob_texto
    assert len(lob_texto) <= 550


# =============================================================================
# T13: Falha no meio de DML -> rollback, sem linhas persistidas
# =============================================================================
def test_t13_falha_no_meio_de_dml_rollback():
    """
    T13: Script DML que insere registro e falha no meio do processamento (RAISE_APPLICATION_ERROR).
    Garante que o executor executa rollback imediato e nenhuma linha é persistida.
    """
    # Garante que o ID de teste não existe previamente
    user_mut = os.getenv("ORACLE_USER_MUT") or os.getenv("ORACLE_USER")
    pass_mut = os.getenv("ORACLE_PASSWORD_MUT") or os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")

    conn = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn)
    cur = conn.cursor()
    cur.execute("DELETE FROM startupadmin.tb_teste_executor WHERE id = 99999")
    conn.commit()
    cur.close()
    conn.close()

    # Executa o script que provocará erro no meio da transação
    saida_str = executar_script("dml_com_erro_t13", {"id": 99999, "nome": "rollback_test"})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "erro"
    assert resultado["motivo"] == "ERRO_ORACLE"
    assert "ORA-20001" in resultado["mensagem"]

    # Confirmação no banco que o rollback funcionou e nenhuma linha permaneceu
    conn = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM startupadmin.tb_teste_executor WHERE id = 99999")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()

    assert count == 0, "Falha de atomicidade: o rollback não impediu a persistência do registro!"
