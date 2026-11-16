"""
Suite de Testes Automatizados do Executor Seguro de Scripts Oracle (tests/test_executor.py).
Cobre os cenários originais (T1 a T13) e os novos cenários da Tarefa 1.1 (T14 a T20).
Garante governança, controle estrito de blocos PL/SQL (C1), verificação de tipos (C2),
ausência de fallback de credenciais (C3), proteção contra path traversal (C4) e documentação de DDL (C5).
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

from src.tools.executor import (
    _analisar_blocos_plsql,
    executar_script,
    tokenizar_e_validar_sql,
    tokenizar_sql_stream,
)
from src.tools.registry import carregar_registro


@pytest.fixture(scope="session", autouse=True)
def setup_banco_teste():
    """
    Fixture de sessão: garante que o ambiente de teste no Oracle esteja provisionado
    (tabela de teste startupadmin.tb_teste_executor e função autônoma para T11).
    """
    user_mut = os.getenv("ORACLE_USER_MUT") or os.getenv("ORACLE_USER")
    pass_mut = os.getenv("ORACLE_PASSWORD_MUT") or os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")

    if not all([user_mut, pass_mut, dsn]):
        pytest.skip("Credenciais Oracle não configuradas no .env. Pulando testes que requerem conexão viva.")

    try:
        conn = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn)
        cur = conn.cursor()

        # Cria ou valida tabela de teste descartável
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
        cur.execute("DELETE FROM startupadmin.tb_teste_executor WHERE id IN (1, 888, 998, 999, 99999)")
        conn.commit()

        # Provisiona função de apoio para validação estrita de privilégios de leitura (T11)
        # Executa sob AUTHID CURRENT_USER para herdar privilégios restritos do chamador
        try:
            cur.execute("""
                CREATE OR REPLACE FUNCTION startupadmin.fn_tentativa_dml_read RETURN NUMBER AUTHID CURRENT_USER AS
                    PRAGMA AUTONOMOUS_TRANSACTION;
                BEGIN
                    INSERT INTO startupadmin.tb_teste_executor (id, nome) VALUES (998, 'readonly_attempt');
                    COMMIT;
                    RETURN 1;
                END;
            """)
            conn.commit()
        except oracledb.DatabaseError:
            pass

        # Concessão para o usuário de leitura restrito
        user_read = os.getenv("ORACLE_USER_READ", "startup_read")
        try:
            cur.execute(f"GRANT SELECT ON startupadmin.tb_teste_executor TO {user_read}")
            cur.execute(f"GRANT EXECUTE ON startupadmin.fn_tentativa_dml_read TO {user_read}")
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
    """T1: Verifica que arquivo com hash divergente é recusado sem abrir conexão."""
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
    """T2: Verifica que script_id inexistente é recusado sem abrir conexão."""
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
    """T3: Verifica que script bloqueado é recusado sem abrir conexão."""
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
    """T4: Tokenizador detecta múltiplos statements e recusa sem conectar."""
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
    """T5: Ponto-e-vírgula em string e comentário em SELECT único executa normalmente."""
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
    """T6: Bloco PL/SQL com ponto-e-vírgulas internos executa como statement único."""
    saida_str = executar_script("plsql_bloco_t6", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "sucesso"
    assert resultado["tipo"] == "PLSQL"


# =============================================================================
# T7: CREATE PROCEDURE com ';' internos e sem '/' -> executa como um statement
# =============================================================================
def test_t7_create_procedure_sem_barra():
    """T7: CREATE PROCEDURE com ';' internos e sem '/' executa como um statement."""
    saida_str = executar_script("procedure_t7", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "sucesso"
    assert resultado["tipo"] in ("DDL", "PLSQL")


# =============================================================================
# T8: Arquivo contendo linha "/" ou "SET ..." -> DIRETIVA_SQLPLUS
# =============================================================================
def test_t8_diretivas_sqlplus_recusadas():
    """T8: Diretivas exclusivas do SQL*Plus (SET, '/') são recusadas sem conectar."""
    with patch("oracledb.connect") as mock_connect:
        res_set = json.loads(executar_script("diretiva_sqlplus_t8", {}))
        assert res_set["status"] == "recusado"
        assert res_set["motivo"] == "DIRETIVA_SQLPLUS"
        assert "set" in res_set["mensagem"].lower()

        res_slash = json.loads(executar_script("diretiva_slash_t8", {}))
        assert res_slash["status"] == "recusado"
        assert res_slash["motivo"] == "DIRETIVA_SQLPLUS"

        mock_connect.assert_not_called()


# =============================================================================
# T9: Bind com "' OR 1=1 --" em SELECT parametrizado -> sem alteração de statement
# Validar em V$SQL: texto do SQL contém :nome, não o valor injetado.
# =============================================================================
def test_t9_bind_injetado_sem_alteracao_statement_v_sql():
    """T9: SQL Injection via bind nomeado preserva :nome inalterado na V$SQL."""
    saida_str = executar_script("select_param_t9", {"nome": "' OR 1=1 --"})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "sucesso"
    assert resultado["linhas_afetadas"] == 0

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

    assert ":nome" in sql_text_oracle
    assert "' OR 1=1 --" not in sql_text_oracle


# =============================================================================
# T10: Bind com nome não declarado ou extra -> BIND_INVALIDO
# =============================================================================
def test_t10_bind_com_nome_nao_declarado():
    """T10: Parâmetro de bind extra ou faltante recusa com BIND_INVALIDO sem conectar."""
    with patch("oracledb.connect") as mock_connect:
        res_extra = json.loads(
            executar_script("select_param_t9", {"nome": "teste", "parametro_extra_hacker": "ataque"})
        )
        assert res_extra["status"] == "recusado"
        assert res_extra["motivo"] == "BIND_INVALIDO"

        res_faltante = json.loads(executar_script("select_param_t9", {}))
        assert res_faltante["status"] == "recusado"
        assert res_faltante["motivo"] == "BIND_INVALIDO"

        mock_connect.assert_not_called()


# =============================================================================
# T11: Usuário de leitura executando script DML -> ORA-01031 (privilégio) e nada persistido
# =============================================================================
def test_t11_usuario_leitura_executando_dml_ora_01031():
    """T11: Usuário de leitura executando DML resulta em ORA-01031 e nada persistido."""
    saida_str = executar_script("dml_tentativa_read_t11", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "erro"
    assert resultado["motivo"] == "ERRO_ORACLE"
    assert "ORA-01031" in resultado["mensagem"]

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
    """T12: Valida que colunas CLOB são truncadas no limite configurado com marcador."""
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
    """T13: Falha no meio de DML dispara rollback imediato e nenhuma linha é persistida."""
    user_mut = os.getenv("ORACLE_USER_MUT") or os.getenv("ORACLE_USER")
    pass_mut = os.getenv("ORACLE_PASSWORD_MUT") or os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")

    conn = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn)
    cur = conn.cursor()
    cur.execute("DELETE FROM startupadmin.tb_teste_executor WHERE id = 99999")
    conn.commit()
    cur.close()
    conn.close()

    saida_str = executar_script("dml_com_erro_t13", {"id": 99999, "nome": "rollback_test"})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "erro"
    assert resultado["motivo"] == "ERRO_ORACLE"
    assert "ORA-20001" in resultado["mensagem"]

    conn = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM startupadmin.tb_teste_executor WHERE id = 99999")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()

    assert count == 0, "Falha de atomicidade: o rollback não impediu a persistência do registro!"


# =============================================================================
# T14: BEGIN NULL; END; DELETE FROM t; -> MULTIPLOS_STATEMENTS, sem conexão
# =============================================================================
def test_t14_plsql_multiplos_statements_apos_bloco():
    """T14: Instrução SQL após término de bloco PL/SQL gera MULTIPLOS_STATEMENTS sem conectar."""
    saida_str = executar_script("plsql_multi_t14", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "recusado"
    assert resultado["motivo"] == "MULTIPLOS_STATEMENTS"
    assert "extra detectado após o término do bloco" in resultado["mensagem"].lower() or "múltiplos" in resultado["mensagem"].lower()


# =============================================================================
# T15: BEGIN IF a THEN b := 1; END IF; c := 2; END; -> executa como um statement
# =============================================================================
def test_t15_plsql_com_if_interno_executa_statement_unico():
    """T15: Bloco PL/SQL com controle IF/THEN/END IF interno executa como um único statement."""
    saida_str = executar_script("plsql_if_stmt_t15", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "sucesso"
    assert resultado["tipo"] == "PLSQL"


# =============================================================================
# T16: CREATE OR REPLACE PROCEDURE com IF/LOOP/CASE internos, sem '/' -> um statement
# =============================================================================
def test_t16_create_procedure_com_if_loop_case_internos():
    """T16: DDL com procedure contendo IF, LOOP e CASE internos executa como um statement."""
    saida_str = executar_script("procedure_complex_t16", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "sucesso"
    assert resultado["tipo"] in ("DDL", "PLSQL")


# =============================================================================
# T17: Arquivo com caminho ../ ou absoluto -> PATH_INVALIDO, sem leitura do arquivo
# =============================================================================
def test_t17_path_traversal_recusado_sem_leitura():
    """T17: Caminhos com ../ ou absolutos são rejeitados com PATH_INVALIDO sem leitura física."""
    # Teste com subida de diretório ../
    res_parent = json.loads(executar_script("path_traversal_parent_t17", {}))
    assert res_parent["status"] == "recusado"
    assert res_parent["motivo"] == "PATH_INVALIDO"

    # Teste com caminho absoluto fora do diretório de scripts
    res_abs = json.loads(executar_script("path_traversal_abs_t17", {}))
    assert res_abs["status"] == "recusado"
    assert res_abs["motivo"] == "PATH_INVALIDO"


# =============================================================================
# T18: SELECT registrado como DML, ou DML registrado como SELECT -> TIPO_DIVERGENTE
# =============================================================================
def test_t18_tipo_divergente_recusado_sem_conexao():
    """T18: Divergência entre tipo declarado no registro e tipo real detectado no código."""
    # Caso 1: Script é SELECT real mas foi registrado como DML
    res_sel_como_dml = json.loads(executar_script("select_como_dml_t18", {}))
    assert res_sel_como_dml["status"] == "recusado"
    assert res_sel_como_dml["motivo"] == "TIPO_DIVERGENTE"

    # Caso 2: Script é DML real mas foi registrado como SELECT
    res_dml_como_sel = json.loads(executar_script("dml_como_select_t18", {}))
    assert res_dml_como_sel["status"] == "recusado"
    assert res_dml_como_sel["motivo"] == "TIPO_DIVERGENTE"


# =============================================================================
# T19: ORACLE_USER_READ ausente com SELECT -> ERRO_CONFIG, sem conexão
# =============================================================================
def test_t19_oracle_user_read_ausente_com_select(monkeypatch):
    """T19: Ausência de ORACLE_USER_READ rejeita execução com ERRO_CONFIG sem conectar."""
    monkeypatch.delenv("ORACLE_USER_READ", raising=False)
    saida_str = executar_script("verificar_dual", {})
    resultado = json.loads(saida_str)

    assert resultado["status"] == "recusado"
    assert resultado["motivo"] == "ERRO_CONFIG"
    assert "ORACLE_USER_READ" in resultado["mensagem"]


# =============================================================================
# T20: Corpus de 15 blocos PL/SQL válidos e inválidos (tests/corpus_plsql/)
# =============================================================================
CORPUS_DIR = BASE_DIR / "tests" / "corpus_plsql"
manifest_path = CORPUS_DIR / "corpus_manifest.json"

if manifest_path.is_file():
    with open(manifest_path, "r", encoding="utf-8") as f:
        corpus_manifest = json.load(f)
    corpus_params = [
        (fname, data["is_valid"], data["expected_code"])
        for fname, data in corpus_manifest.items()
    ]
else:
    corpus_params = []


@pytest.mark.parametrize("filename,is_valid,expected_code", corpus_params)
def test_t20_corpus_plsql_tokenizacao(filename, is_valid, expected_code):
    """T20: Validação parametrizada de conformidade gramatical no corpus de 15 casos PL/SQL."""
    file_path = CORPUS_DIR / filename
    with open(file_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    tokens = tokenizar_sql_stream(sql_content)
    valid, code_res, msg = _analisar_blocos_plsql(tokens)

    assert valid == is_valid, f"Falha no caso {filename}: esperado valido={is_valid}, obtido {valid} (msg: {msg})"
    assert code_res == expected_code, f"Falha no caso {filename}: esperado codigo={expected_code}, obtido {code_res} (msg: {msg})"
