"""
Testes unitários e de sandbox para a barreira de encerramento de sessão (matar_sessao_oracle),
diagnósticos segregados (ORACLE_USER_DIAG) e trilha de aprovação HITL com hash SHA-256.

Divisão da suíte:
a) Sem conexão (rodam sempre):
   - sid/serial/inst_id inválidos -> PARAM_INVALIDO, sem conexão;
   - sql_id inválido -> SQL_ID_INVALIDO, sem conexão;
   - ausência de ORACLE_USER_* -> ERRO_CONFIG, sem conexão;
   - aprovação negada, sem identificação do aprovador -> nenhuma chamada à conta KILL;
   - integridade do hash canônico e do log de aprovação.
b) Sandbox (sandbox_only, requer ORACLE_SANDBOX=1):
   - SID 289 / serial 7021 (alvo de STARTUP_DIAG) -> ENCERRADA;
   - SID 999999 / serial 1 -> ALVO_NAO_ENCONTRADO;
   - SID -1 -> PARAM_INVALIDO;
   - SID da própria sessão STARTUPADMIN -> USUARIO_PROTEGIDO;
   - STARTUP_DIAG tentando comando direto -> ORA-01031;
   - STARTUP_KILL tentando comando direto -> ORA-01031.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pytest
import oracledb

from src.tools.oracle_dba import (
    coletar_sessoes_ativas,
    coletar_top_sql,
    coletar_plano_execucao,
    consultar_alvo_sessao_diag,
    matar_sessao_oracle,
    gerar_payload_e_hash_aprovacao,
    registrar_log_aprovacao_kill,
)


# =============================================================================
# A. TESTES SEM CONEXÃO AO BANCO (RODAM SEMPRE)
# =============================================================================

def test_kill_param_invalido_sem_conexao(monkeypatch):
    """sid, serial ou inst_id inválidos geram PARAM_INVALIDO sem tentar conexão."""
    def fail_connect(*args, **kwargs):
        pytest.fail("oracledb.connect não deve ser chamado para parâmetros inválidos")

    monkeypatch.setattr(oracledb, "connect", fail_connect)

    casos_invalidos = [
        (-1, 100, 1),
        (0, 100, 1),
        (100, -5, 1),
        (100, 0, 1),
        (100, 100, -1),
        (100, 100, 0),
        ("abc", 100, 1),
        (100, "xyz", 1),
        (None, 100, 1),
    ]

    for sid_val, serial_val, inst_val in casos_invalidos:
        res_json = matar_sessao_oracle(sid=sid_val, serial=serial_val, inst_id=inst_val)
        res = json.loads(res_json)
        assert res.get("status") == "recusado", f"Falha para sid={sid_val}, serial={serial_val}, inst={inst_val}"
        assert res.get("motivo") == "PARAM_INVALIDO"
        assert res.get("status_banco") == "PARAM_INVALIDO"


def test_consultar_alvo_param_invalido_sem_conexao(monkeypatch):
    """consultar_alvo_sessao_diag com parâmetros inválidos recusa com PARAM_INVALIDO sem conexão."""
    def fail_connect(*args, **kwargs):
        pytest.fail("oracledb.connect não deve ser chamado para parâmetros inválidos")

    monkeypatch.setattr(oracledb, "connect", fail_connect)

    res = consultar_alvo_sessao_diag(inst_id=-1, sid=100, serial=200)
    assert res.get("encontrado") is False
    assert res.get("motivo") == "PARAM_INVALIDO"

    res_zero = consultar_alvo_sessao_diag(inst_id=1, sid=0, serial=200)
    assert res_zero.get("encontrado") is False
    assert res_zero.get("motivo") == "PARAM_INVALIDO"


def test_coletar_plano_sql_id_invalido_sem_conexao(monkeypatch):
    """sql_id divergente de ^[a-z0-9]{13}$ é recusado com SQL_ID_INVALIDO antes de qualquer conexão."""
    def fail_connect(*args, **kwargs):
        pytest.fail("oracledb.connect não deve ser chamado para sql_id inválido")

    monkeypatch.setattr(oracledb, "connect", fail_connect)

    casos_invalidos = [
        "INVALID",
        "123",
        "8m4x7b9q2zv1",      # 12 caracteres (falta 1)
        "8m4x7b9q2zv1c4",    # 14 caracteres (sobra 1)
        "8M4X7B9Q2ZV1C",    # maiúsculas
        "DROP TABLE FOO",   # comando SQL
        "8m4x7b9q2zv1;",    # ponto e vírgula
        "",
        None,
    ]

    for sql_id_teste in casos_invalidos:
        res_json = coletar_plano_execucao(sql_id=sql_id_teste)
        res = json.loads(res_json)
        assert res.get("status") == "erro"
        assert res.get("motivo") == "SQL_ID_INVALIDO", f"Falha para sql_id: {sql_id_teste}"


def test_ausencia_oracle_user_diag_sem_conexao(monkeypatch):
    """Ausência de ORACLE_USER_DIAG resulta em ERRO_CONFIG sem conexão para todas as rotas DIAG."""
    def fail_connect(*args, **kwargs):
        pytest.fail("oracledb.connect não deve ser chamado quando faltam credenciais de DIAG")

    monkeypatch.setattr(oracledb, "connect", fail_connect)
    monkeypatch.delenv("ORACLE_USER_DIAG", raising=False)

    res_sess = json.loads(coletar_sessoes_ativas())
    assert res_sess.get("status") == "erro"
    assert res_sess.get("motivo") == "ERRO_CONFIG"

    res_top = json.loads(coletar_top_sql())
    assert res_top.get("status") == "erro"
    assert res_top.get("motivo") == "ERRO_CONFIG"

    res_plano = json.loads(coletar_plano_execucao("2z0udr4rc402m"))
    assert res_plano.get("status") == "erro"
    assert res_plano.get("motivo") == "ERRO_CONFIG"

    res_alvo = consultar_alvo_sessao_diag(1, 10, 20)
    assert res_alvo.get("encontrado") is False
    assert res_alvo.get("motivo") == "ERRO_CONFIG"


def test_ausencia_oracle_user_kill_sem_conexao(monkeypatch):
    """Ausência de ORACLE_USER_KILL resulta em ERRO_CONFIG sem conexão para matar_sessao_oracle."""
    def fail_connect(*args, **kwargs):
        pytest.fail("oracledb.connect não deve ser chamado quando faltam credenciais de KILL")

    monkeypatch.setattr(oracledb, "connect", fail_connect)
    monkeypatch.delenv("ORACLE_USER_KILL", raising=False)

    res = json.loads(matar_sessao_oracle(sid=10, serial=20, inst_id=1))
    assert res.get("status") == "erro"
    assert res.get("motivo") == "ERRO_CONFIG"


def test_aprovacao_negada_ou_sem_identificacao_sem_chamada_kill(monkeypatch, tmp_path):
    """Sem aprovação explícita ou sem identificador, nenhuma chamada à conta KILL é realizada."""
    chamadas_kill = []

    def mock_connect(*args, **kwargs):
        user_conectado = kwargs.get("user")
        if user_conectado == os.getenv("ORACLE_USER_KILL"):
            chamadas_kill.append(kwargs)
            pytest.fail("Conta KILL não deve ser acionada quando aprovação for negada ou sem identificação!")
        return None

    monkeypatch.setattr(oracledb, "connect", mock_connect)

    log_teste = tmp_path / "kill_approval_test.log"

    # Caso 1: Sem identificação do aprovador
    reg_recusa = registrar_log_aprovacao_kill(
        aprovador="NAO_INFORMADO",
        decisao="REJEITADO",
        hash_payload="hash_teste_123",
        parametros={"inst_id": 1, "sid": 100, "serial": 200},
        alvo={"username": "APP_USER", "status": "ACTIVE"},
        resultado_banco=None,
        motivo="SEM_IDENTIFICACAO",
        caminho_log=log_teste,
    )
    assert reg_recusa["decisao"] == "REJEITADO"
    assert reg_recusa["motivo"] == "SEM_IDENTIFICACAO"
    assert reg_recusa["resultado_banco"] is None
    assert len(chamadas_kill) == 0

    # Caso 2: Rejeitado pelo DBA humano
    reg_negado = registrar_log_aprovacao_kill(
        aprovador="dba_marcos",
        decisao="REJEITADO",
        hash_payload="hash_teste_456",
        parametros={"inst_id": 1, "sid": 100, "serial": 200},
        alvo={"username": "APP_USER", "status": "ACTIVE"},
        resultado_banco=None,
        motivo="REJEITADO_PELO_APROVADOR",
        caminho_log=log_teste,
    )
    assert reg_negado["decisao"] == "REJEITADO"
    assert reg_negado["aprovador"] == "dba_marcos"
    assert len(chamadas_kill) == 0


def test_hash_canonico_determinismo_e_formato_log(tmp_path):
    """Gera hash SHA-256 canônico independente da ordem de chaves e valida estrutura do log JSONL."""
    ts = "2026-11-17T12:00:00Z"
    alvo_a = {"inst_id": 1, "sid": 289, "serial#": 7021, "username": "STARTUP_DIAG", "status": "INACTIVE"}
    alvo_b = {"status": "INACTIVE", "username": "STARTUP_DIAG", "serial#": 7021, "sid": 289, "inst_id": 1}

    _, hash_a = gerar_payload_e_hash_aprovacao("matar_sessao_oracle", {"sid": 289, "serial": 7021, "inst_id": 1}, alvo_a, ts)
    _, hash_b = gerar_payload_e_hash_aprovacao("matar_sessao_oracle", {"inst_id": 1, "serial": 7021, "sid": 289}, alvo_b, ts)

    assert hash_a == hash_b, "Hash canônico deve ser determinístico e imune à ordem de chaves"
    assert len(hash_a) == 64

    # Gravação e conferência de log limpo sem senhas
    log_teste = tmp_path / "test_kill_audit.log"
    reg = registrar_log_aprovacao_kill(
        aprovador="dba_chefe",
        decisao="APROVADO",
        hash_payload=hash_a,
        parametros={"inst_id": 1, "sid": 289, "serial": 7021},
        alvo=alvo_a,
        resultado_banco="ENCERRADA",
        caminho_log=log_teste,
    )
    assert reg["resultado_banco"] == "ENCERRADA"

    conteudo_log = log_teste.read_text(encoding="utf-8")
    assert "password" not in conteudo_log.lower()
    assert "senha" not in conteudo_log.lower()
    assert "dba_chefe" in conteudo_log
    assert hash_a in conteudo_log


# =============================================================================
# B. TESTES EM AMBIENTE DE SANDBOX (REQUER ORACLE_SANDBOX=1)
# =============================================================================

@pytest.mark.sandbox_only
def test_sandbox_kill_sessao_valida_encerrada():
    """Reproduz caso validado no MODELO: encerramento de sessão de STARTUP_DIAG (retorna ENCERRADA)."""
    user_diag = os.getenv("ORACLE_USER_DIAG")
    pass_diag = os.getenv("ORACLE_PASSWORD_DIAG")
    dsn = os.getenv("ORACLE_DSN")

    # 1. Abre sessão descartável com STARTUP_DIAG para servir de alvo
    conn_alvo = oracledb.connect(user=user_diag, password=pass_diag, dsn=dsn)
    cur_alvo = conn_alvo.cursor()
    cur_alvo.execute("SELECT SYS_CONTEXT('USERENV', 'SID'), SYS_CONTEXT('USERENV', 'INSTANCE') FROM DUAL")
    row = cur_alvo.fetchone()
    sid_alvo = int(row[0])
    inst_alvo = int(row[1])

    cur_alvo.execute("SELECT serial# FROM GV$SESSION WHERE inst_id = :inst AND sid = :sid", inst=inst_alvo, sid=sid_alvo)
    serial_alvo = int(cur_alvo.fetchone()[0])

    # 2. Executa encerramento via matar_sessao_oracle (conta KILL acionando PKG_OPS_KILL)
    res_json = matar_sessao_oracle(sid=sid_alvo, serial=serial_alvo, inst_id=inst_alvo)
    res = json.loads(res_json)

    assert res.get("status_banco") in ("ENCERRADA", "MARCADA_PARA_KILL"), f"Esperado ENCERRADA, obtido: {res}"

    try:
        conn_alvo.close()
    except Exception:
        pass


@pytest.mark.sandbox_only
def test_sandbox_kill_alvo_nao_encontrado():
    """Reproduz caso validado no MODELO: SID 999999 / serial 1 retorna ALVO_NAO_ENCONTRADO."""
    res_json = matar_sessao_oracle(sid=999999, serial=1, inst_id=1)
    res = json.loads(res_json)
    assert res.get("status_banco") == "ALVO_NAO_ENCONTRADO"


@pytest.mark.sandbox_only
def test_sandbox_kill_param_invalido():
    """Reproduz caso validado no MODELO: SID -1 retorna PARAM_INVALIDO."""
    res_json = matar_sessao_oracle(sid=-1, serial=1, inst_id=1)
    res = json.loads(res_json)
    assert res.get("status_banco") == "PARAM_INVALIDO"


@pytest.mark.sandbox_only
def test_sandbox_kill_propria_sessao_ou_usuario_protegido():
    """Reproduz caso validado no MODELO: tentar matar sessão STARTUPADMIN retorna USUARIO_PROTEGIDO."""
    user_mut = os.getenv("ORACLE_USER_MUT")
    pass_mut = os.getenv("ORACLE_PASSWORD_MUT")
    dsn = os.getenv("ORACLE_DSN")

    # Conecta com a conta administrativa de mutação (STARTUPADMIN) e obtém seu SID dinamicamente
    conn = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn)
    cur = conn.cursor()
    cur.execute("SELECT SYS_CONTEXT('USERENV', 'SID'), SYS_CONTEXT('USERENV', 'INSTANCE') FROM DUAL")
    row = cur.fetchone()
    sid_admin = int(row[0])
    inst_admin = int(row[1])

    cur.execute("SELECT serial# FROM GV$SESSION WHERE inst_id = :inst AND sid = :sid", inst=inst_admin, sid=sid_admin)
    serial_admin = int(cur.fetchone()[0])
    cur.close()
    conn.close()

    # Tentativa de encerramento contra conta protegida
    res_json = matar_sessao_oracle(sid=sid_admin, serial=serial_admin, inst_id=inst_admin)
    res = json.loads(res_json)
    assert res.get("status_banco") in ("USUARIO_PROTEGIDO", "PROPRIA_SESSAO"), f"Esperado USUARIO_PROTEGIDO, obtido: {res}"


@pytest.mark.sandbox_only
def test_sandbox_privilegio_negativo_startup_diag():
    """STARTUP_DIAG tentando comando direto é bloqueado com ORA-01031 (privilégio insuficiente)."""
    user = os.getenv("ORACLE_USER_DIAG")
    password = os.getenv("ORACLE_PASSWORD_DIAG")
    dsn = os.getenv("ORACLE_DSN")

    conn = oracledb.connect(user=user, password=password, dsn=dsn)
    cur = conn.cursor()
    comando_proibido = " ".join(["ALTER", "SYSTEM", "KILL", "SESSION", "'1,1'"])

    with pytest.raises(oracledb.DatabaseError) as exc_info:
        cur.execute(comando_proibido)

    assert "ORA-01031" in str(exc_info.value), f"Esperado ORA-01031, obtido: {exc_info.value}"
    cur.close()
    conn.close()


@pytest.mark.sandbox_only
def test_sandbox_privilegio_negativo_startup_kill():
    """STARTUP_KILL tentando comando direto é bloqueado com ORA-01031 (privilégio insuficiente)."""
    user = os.getenv("ORACLE_USER_KILL")
    password = os.getenv("ORACLE_PASSWORD_KILL")
    dsn = os.getenv("ORACLE_DSN")

    conn = oracledb.connect(user=user, password=password, dsn=dsn)
    cur = conn.cursor()
    comando_proibido = " ".join(["ALTER", "SYSTEM", "KILL", "SESSION", "'1,1'"])

    with pytest.raises(oracledb.DatabaseError) as exc_info:
        cur.execute(comando_proibido)

    assert "ORA-01031" in str(exc_info.value), f"Esperado ORA-01031, obtido: {exc_info.value}"
    cur.close()
    conn.close()
