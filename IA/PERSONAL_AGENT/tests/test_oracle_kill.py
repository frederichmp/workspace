"""
Testes unitários e de sandbox para a barreira de encerramento de sessão (matar_sessao_oracle),
diagnósticos segregados (ORACLE_USER_DIAG) e trilha de aprovação HITL com hash SHA-256.

Divisão da suíte:
a) Sem conexão (rodam sempre):
   - sid/serial/inst_id inválidos -> PARAM_INVALIDO, sem conexão;
   - sql_id inválido -> SQL_ID_INVALIDO, sem conexão;
   - ausência de ORACLE_USER_* -> ERRO_CONFIG, sem conexão;
   - aprovação negada, sem identificação do aprovador -> nenhuma chamada à conta KILL;
   - integridade do hash canônico e do log de aprovação;
   - (1.9) alvo de background -> NAO_USUARIO, sem prompt de aprovação (cursor mockado);
   - (1.9) usuário protegido -> USUARIO_PROTEGIDO, sem prompt; lista alinhada a PKG_OPS_KILL;
   - (1.9) hash divergente na reconsulta -> ALVO_ALTERADO, sem connect da conta KILL;
   - (1.9) inst_id ausente -> PARAM_INVALIDO, sem conexão;
   - (1.9) resultado NAO_USUARIO com decisão APROVADO -> e-mail sem assunto de aprovada;
   - (1.9) registro de log com decisao e resultado_banco separados.
b) Sandbox (sandbox_only, requer ORACLE_SANDBOX=1):
   - SID 289 / serial 7021 (alvo de STARTUP_DIAG) -> ENCERRADA;
   - SID 999999 / serial 1 -> ALVO_NAO_ENCONTRADO;
   - SID -1 -> PARAM_INVALIDO;
   - SID da própria sessão STARTUPADMIN -> USUARIO_PROTEGIDO;
   - STARTUP_DIAG tentando comando direto -> ORA-01031;
   - STARTUP_KILL tentando comando direto -> ORA-01031.
"""
import ast
from datetime import date, datetime, timedelta, timezone
import inspect
import json
import os
from pathlib import Path
import pytest
import oracledb

import logging
import re

from src.tools import oracle_dba
from src.tools.oracle_dba import (
    USUARIOS_PROTEGIDOS,
    calcular_hash_identidade,
    coletar_sessoes_ativas,
    coletar_top_sql,
    coletar_plano_execucao,
    conduzir_kill_hitl,
    consultar_alvo_sessao_diag,
    matar_sessao_oracle,
    gerar_payload_e_hash_aprovacao,
    oracle_tools_schema,
    registrar_decisao_kill,
    registrar_log_aprovacao_kill,
)

ROOT_DIR_TESTE = Path(__file__).resolve().parent.parent

# Identidade esperada e ref de aprovação válidos (kill v2, item 6): valores só de teste.
IDENTIDADE_VALIDA = {
    "username": "APP_USER",
    "program": "app.exe",
    "machine": "srv-app01",
    "logon_time": datetime(2026, 11, 23, 10, 0, 0),
}
REF_VALIDO = "0123456789abcdef0123456789abcdef"


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
        res_json = matar_sessao_oracle(
            sid=sid_val, serial=serial_val, inst_id=inst_val,
            identidade_esperada=dict(IDENTIDADE_VALIDA), ref_aprovacao=REF_VALIDO,
        )
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

    def fail_host(*args, **kwargs):
        pytest.fail("verificar_acessibilidade_host não deve ser chamado quando falta ORACLE_USER_DIAG")

    monkeypatch.setattr(oracledb, "connect", fail_connect)
    monkeypatch.setattr(oracle_dba, "verificar_acessibilidade_host", fail_host)
    # D3: só o usuário falta; senha e DSN fictícios (sem o .env real, o teste não passa "por acaso")
    monkeypatch.setenv("ORACLE_PASSWORD_DIAG", "senha-fake")
    monkeypatch.setenv("ORACLE_DSN", "host-teste:1521/TESTE")
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

    def fail_host(*args, **kwargs):
        pytest.fail("verificar_acessibilidade_host não deve ser chamado quando falta ORACLE_USER_KILL")

    monkeypatch.setattr(oracledb, "connect", fail_connect)
    monkeypatch.setattr(oracle_dba, "verificar_acessibilidade_host", fail_host)
    # D3: só o usuário falta; senha e DSN fictícios (sem o .env real, o teste não passa "por acaso")
    monkeypatch.setenv("ORACLE_PASSWORD_KILL", "senha-fake")
    monkeypatch.setenv("ORACLE_DSN", "host-teste:1521/TESTE")
    monkeypatch.delenv("ORACLE_USER_KILL", raising=False)

    res = json.loads(matar_sessao_oracle(
        sid=10, serial=20, inst_id=1, identidade_esperada=dict(IDENTIDADE_VALIDA), ref_aprovacao=REF_VALIDO,
    ))
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
        fase="RESULTADO",
        id_intervencao="0" * 32,
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
        fase="RESULTADO",
        id_intervencao="0" * 32,
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
        fase="RESULTADO",
        id_intervencao="0" * 32,
    )
    assert reg["resultado_banco"] == "ENCERRADA"

    conteudo_log = log_teste.read_text(encoding="utf-8")
    assert "password" not in conteudo_log.lower()
    assert "senha" not in conteudo_log.lower()
    assert "dba_chefe" in conteudo_log
    assert hash_a in conteudo_log


# =============================================================================
# A2. TAREFA 1.9 — PRÉ-CONSULTA, INTEGRIDADE E DECISÃO (SEM CONEXÃO, MOCKS)
# =============================================================================
# Credenciais fictícias definidas só no processo de teste (nenhum valor do .env é usado
# nem impresso). oracledb.connect é substituído por um falso que separa DIAG e KILL.

from tests.fakes_oracle import (  # noqa: E402
    COLUNAS_ALVO,
    USER_DIAG_FAKE,
    USER_KILL_FAKE,
    _OracleFake,
    _linha_alvo,
)


@pytest.fixture
def ambiente_fake(monkeypatch):
    """Credenciais fictícias, rede sempre acessível e e-mail capturado (enviar_alerta_email mockado)."""
    monkeypatch.setenv("ORACLE_USER_DIAG", USER_DIAG_FAKE)
    monkeypatch.setenv("ORACLE_PASSWORD_DIAG", "senha-fake")
    monkeypatch.setenv("ORACLE_USER_KILL", USER_KILL_FAKE)
    monkeypatch.setenv("ORACLE_PASSWORD_KILL", "senha-fake")
    monkeypatch.setenv("ORACLE_DSN", "host-teste:1521/TESTE")
    monkeypatch.setattr(
        oracle_dba,
        "verificar_acessibilidade_host",
        lambda dsn, timeout=3.0: {"acessivel": True, "host": "host-teste", "porta": 1521, "latencia_ms": 0.1},
    )
    emails = []

    def enviar_alerta_email_mock(assunto, corpo):
        emails.append({"assunto": assunto, "corpo": corpo})
        return True, "mock"

    monkeypatch.setattr(oracle_dba, "enviar_alerta_email", enviar_alerta_email_mock)
    return emails


def _instalar_oracle(monkeypatch, oracle_fake):
    monkeypatch.setattr(oracledb, "connect", oracle_fake.connect)
    return oracle_fake


def _prompt_proibido(prep):
    pytest.fail("Prompt de aprovação não deve ser exibido para alvo recusado na pré-consulta")


def _aprovar(aprovador="dba_teste"):
    def _solicitar(prep):
        return "APROVADO", aprovador, None
    return _solicitar


ARGS_ALVO = {"inst_id": 1, "sid": 101, "serial": 202}


def test_alvo_background_retorna_nao_usuario_sem_prompt(monkeypatch, tmp_path, ambiente_fake):
    """Sessão com TYPE='BACKGROUND' -> NAO_USUARIO, sem prompt, sem conta KILL, sem e-mail."""
    oracle_fake = _instalar_oracle(
        monkeypatch,
        _OracleFake([_linha_alvo(username=None, program="oracle@db (PMON)", tipo="BACKGROUND")], kill_permitido=False),
    )

    res_alvo = consultar_alvo_sessao_diag(inst_id=1, sid=101, serial=202)
    assert res_alvo["encontrado"] is True
    assert res_alvo["elegivel"] is False
    assert res_alvo["motivo"] == "NAO_USUARIO"
    sql_diag = oracle_fake.sql_executado[0][1].lower()
    assert re.search(r"\btype\b", sql_diag), "Pré-consulta deve selecionar TYPE da GV$SESSION"

    oracle_fake.linhas_diag.append(_linha_alvo(username=None, program="oracle@db (PMON)", tipo="BACKGROUND"))
    desfecho = conduzir_kill_hitl(
        dict(ARGS_ALVO), solicitar_aprovacao=_prompt_proibido, canal="TESTE", caminho_log=tmp_path / "kill.log"
    )
    assert desfecho["prompt_exibido"] is False
    assert desfecho["motivo"] == "NAO_USUARIO"
    assert json.loads(desfecho["resultado_tool"])["status_banco"] == "NAO_USUARIO"
    assert oracle_fake.conexoes_kill == []
    assert ambiente_fake == []


@pytest.mark.parametrize("usuario", list(USUARIOS_PROTEGIDOS) + ["sys", "Startupadmin"])
def test_usuario_protegido_retorna_usuario_protegido_sem_prompt(monkeypatch, tmp_path, ambiente_fake, usuario):
    """Usuário da lista protegida (qualquer caixa) -> USUARIO_PROTEGIDO, sem prompt e sem conta KILL."""
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo(username=usuario)], kill_permitido=False))

    desfecho = conduzir_kill_hitl(
        dict(ARGS_ALVO), solicitar_aprovacao=_prompt_proibido, canal="TESTE", caminho_log=tmp_path / "kill.log"
    )
    assert desfecho["prompt_exibido"] is False
    assert desfecho["motivo"] == "USUARIO_PROTEGIDO"
    assert oracle_fake.conexoes_kill == []
    assert ambiente_fake == []


def test_usuario_nulo_tipo_user_retorna_usuario_protegido(monkeypatch, ambiente_fake):
    """Mesma regra do pacote: TYPE='USER' com username nulo é tratado como USUARIO_PROTEGIDO."""
    _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo(username=None)], kill_permitido=False))
    res = consultar_alvo_sessao_diag(inst_id=1, sid=101, serial=202)
    assert res["elegivel"] is False
    assert res["motivo"] == "USUARIO_PROTEGIDO"


def test_lista_protegida_alinhada_ao_pacote():
    """USUARIOS_PROTEGIDOS é idêntica à constante c_protegidos de PKG_OPS_KILL (db/ops_kill.sql, só leitura)."""
    assert set(USUARIOS_PROTEGIDOS) == {"SYS", "SYSTEM", "DBSNMP", "SYSMAN", "OUTLN", "STARTUPADMIN", "OPS_OWNER"}
    sql = (ROOT_DIR_TESTE / "db" / "ops_kill.sql").read_text(encoding="utf-8")
    m = re.search(r"c_protegidos\s+CONSTANT\s+VARCHAR2\(\d+\)\s*:=\s*'([^']*)'", sql, re.IGNORECASE)
    assert m, "Constante c_protegidos não encontrada em db/ops_kill.sql"
    lista_pacote = {u for u in m.group(1).split(",") if u}
    assert set(USUARIOS_PROTEGIDOS) == lista_pacote


def test_hash_divergente_na_reconsulta_retorna_alvo_alterado_sem_conta_kill(
    monkeypatch, tmp_path, ambiente_fake, caplog
):
    """Identidade muda entre aprovação e execução -> ALVO_ALTERADO, sem connect KILL, ocorrência no log."""
    linha_aprovada = _linha_alvo(program="app.exe")
    linha_reconsulta = _linha_alvo(program="outro_programa.exe")  # mesmo inst_id/sid/serial, outro programa
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([linha_aprovada, linha_reconsulta], kill_permitido=False))
    log_aprovacao = tmp_path / "kill.log"

    with caplog.at_level(logging.WARNING, logger=oracle_dba.logger.name):
        desfecho = conduzir_kill_hitl(
            dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=log_aprovacao
        )

    assert desfecho["prompt_exibido"] is True
    assert desfecho["decisao"] == "APROVADO"
    assert desfecho["resultado_banco"] == "ALVO_ALTERADO"
    assert desfecho["executado"] is False
    assert oracle_fake.conexoes_kill == [], "Conta KILL não pode ser conectada com hash divergente"
    assert oracle_fake.conexoes.count(USER_DIAG_FAKE) == 2, "Esperadas pré-consulta e reconsulta pela DIAG"
    assert any("ALVO_ALTERADO" in r.getMessage() for r in caplog.records)

    registro = json.loads(log_aprovacao.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert registro["decisao"] == "APROVADO"
    assert registro["resultado_banco"] == "ALVO_ALTERADO"

    assert len(ambiente_fake) == 1
    assert "Aprovada" not in ambiente_fake[0]["assunto"]
    assert "NÃO executada" in ambiente_fake[0]["assunto"]


def test_hash_identidade_ignora_campos_volateis():
    """status, event, sql_id e timestamp não entram no hash; program sim."""
    base = dict(zip([c.lower() for c in COLUNAS_ALVO], _linha_alvo()))
    volatil = dict(base, status="INACTIVE", event="db file sequential read", sql_id="aaaaaaaaaaaaa")
    assert calcular_hash_identidade(base) == calcular_hash_identidade(volatil)
    assert calcular_hash_identidade(base) != calcular_hash_identidade(dict(base, program="outro.exe"))

    _, h1 = gerar_payload_e_hash_aprovacao("matar_sessao_oracle", ARGS_ALVO, base, "2026-11-17T12:00:00Z")
    _, h2 = gerar_payload_e_hash_aprovacao("matar_sessao_oracle", ARGS_ALVO, volatil, "2026-11-17T13:00:00Z")
    assert h1 == h2


def test_inst_id_ausente_param_invalido_sem_conexao(monkeypatch, tmp_path):
    """inst_id ausente -> PARAM_INVALIDO sem consulta nem conexão; schema sem default e com inst_id obrigatório."""
    def fail_connect(*args, **kwargs):
        pytest.fail("oracledb.connect não deve ser chamado sem inst_id")

    monkeypatch.setattr(oracledb, "connect", fail_connect)

    with pytest.raises(TypeError):
        matar_sessao_oracle(
            sid=10, serial=20, identidade_esperada=dict(IDENTIDADE_VALIDA), ref_aprovacao=REF_VALIDO,
        )

    for inst_invalido in (None, True, 1.5, "1a", "", 0, -3):
        res_inv = json.loads(matar_sessao_oracle(
            sid=10, serial=20, inst_id=inst_invalido,
            identidade_esperada=dict(IDENTIDADE_VALIDA), ref_aprovacao=REF_VALIDO,
        ))
        assert res_inv["motivo"] == "PARAM_INVALIDO", f"inst_id={inst_invalido!r} deveria ser recusado"

    desfecho = conduzir_kill_hitl(
        {"sid": 10, "serial": 20}, solicitar_aprovacao=_prompt_proibido, canal="TESTE", caminho_log=tmp_path / "k.log"
    )
    assert desfecho["prompt_exibido"] is False
    assert desfecho["motivo"] == "PARAM_INVALIDO"

    schema_kill = next(t for t in oracle_tools_schema if t["function"]["name"] == "matar_sessao_oracle")
    props = schema_kill["function"]["parameters"]
    assert "inst_id" in props["required"]
    assert "default" not in props["properties"]["inst_id"]


def test_assinatura_sem_default_para_inst_id():
    """Nenhuma função pública definida em oracle_dba tem parâmetro inst_id com default."""
    com_default = []
    for nome, obj in vars(oracle_dba).items():
        if nome.startswith("_") or not inspect.isfunction(obj) or obj.__module__ != oracle_dba.__name__:
            continue
        param = inspect.signature(obj).parameters.get("inst_id")
        if param is not None and param.default is not inspect.Parameter.empty:
            com_default.append(nome)
    assert not com_default, f"inst_id com default em: {com_default}"


def _solicitar_capturando(captura, decisao="APROVADO", aprovador="dba_teste", motivo=None):
    """Prompt falso que guarda timestamp e hash do preparo e devolve a decisão pedida."""
    def _solicitar(prep):
        captura["ts"] = prep["timestamp"]
        captura["hash"] = prep["hash_identidade"]
        return decisao, aprovador, motivo
    return _solicitar


def _relogio_relativo(captura, delta):
    """Relógio injetado: instante da preparação (capturado no prompt) + delta."""
    return lambda: datetime.fromisoformat(captura["ts"]) + delta


@pytest.mark.parametrize(
    "delta",
    [timedelta(seconds=300), timedelta(seconds=301), timedelta(days=1), timedelta(seconds=-1)],
    ids=["fronteira_300s", "301s", "1_dia", "futuro"],
)
def test_aprovacao_expirada_vira_timeout(monkeypatch, tmp_path, ambiente_fake, delta):
    """APROVADO fora de [0, TTL) -> TIMEOUT/APROVACAO_EXPIRADA, sem reconsulta, 0 KILL, 0 e-mail."""
    assert oracle_dba.APROVACAO_TTL_SEGUNDOS == 300
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo()], kill_permitido=False))
    log = tmp_path / "kill.log"
    cap = {}

    desfecho = conduzir_kill_hitl(
        dict(ARGS_ALVO),
        solicitar_aprovacao=_solicitar_capturando(cap),
        canal="TESTE",
        caminho_log=log,
        agora=_relogio_relativo(cap, delta),
    )

    assert desfecho["prompt_exibido"] is True
    assert desfecho["decisao"] == "TIMEOUT"
    assert desfecho["motivo"] == "APROVACAO_EXPIRADA"
    assert desfecho["executado"] is False
    assert desfecho["resultado_banco"] is None
    assert desfecho["assunto_email"] is None
    assert oracle_fake.conexoes_kill == []
    assert oracle_fake.conexoes.count(USER_DIAG_FAKE) == 1, "não deve haver reconsulta DIAG após expirar"
    assert ambiente_fake == []

    tool = json.loads(desfecho["resultado_tool"])
    assert tool["decisao"] == "TIMEOUT"
    assert tool["executado"] is False
    assert tool["motivo"] == "APROVACAO_EXPIRADA"

    registros = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert len(registros) == 1
    reg = registros[0]
    assert reg["fase"] == "RESULTADO"
    assert reg["decisao"] == "TIMEOUT"
    assert reg["motivo"] == "APROVACAO_EXPIRADA"
    assert reg["resultado_banco"] is None
    assert reg["aprovador"] == "dba_teste"
    assert reg["hash_payload"] == cap["hash"]
    assert "status_banco" not in reg

    # Fail-closed: preparado_em ausente, vazio, inválido ou sem fuso -> TIMEOUT, 0 KILL
    instante = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    for preparado_em in (None, "", "lixo", "2026-11-17T12:00:00"):
        res = registrar_decisao_kill(
            decisao="APROVADO", aprovador="dba_teste", inst_id=1, sid=101, serial=202,
            alvo={}, hash_aprovado="hash-fake", canal="TESTE", preparado_em=preparado_em,
            caminho_log=log, agora=lambda: instante,
        )
        assert res["decisao"] == "TIMEOUT", f"preparado_em={preparado_em!r}"
        assert res["motivo"] == "APROVACAO_EXPIRADA"
        assert res["executado"] is False
    assert oracle_fake.conexoes_kill == []
    assert ambiente_fake == []

    # Só APROVADO é convertido: REJEITADO após o TTL continua REJEITADO
    oracle_fake.linhas_diag.append(_linha_alvo())
    cap_rej = {}
    desfecho_rej = conduzir_kill_hitl(
        dict(ARGS_ALVO),
        solicitar_aprovacao=_solicitar_capturando(cap_rej, decisao="REJEITADO", motivo="REJEITADO_PELO_APROVADOR"),
        canal="TESTE",
        caminho_log=log,
        agora=_relogio_relativo(cap_rej, timedelta(seconds=301)),
    )
    assert desfecho_rej["decisao"] == "REJEITADO"
    assert desfecho_rej["motivo"] == "REJEITADO_PELO_APROVADOR"
    assert oracle_fake.conexoes_kill == []


@pytest.mark.parametrize(
    "delta",
    [timedelta(0), timedelta(seconds=299, microseconds=999999)],
    ids=["0s", "299_999999s"],
)
def test_aprovacao_dentro_do_ttl_executa(monkeypatch, tmp_path, ambiente_fake, delta):
    """APROVADO dentro de [0, TTL) segue o fluxo normal: reconsulta, 1 KILL, e-mail de aprovada."""
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo(), _linha_alvo()], status_pkg="ENCERRADA"))
    log = tmp_path / "kill.log"
    cap = {}

    desfecho = conduzir_kill_hitl(
        dict(ARGS_ALVO),
        solicitar_aprovacao=_solicitar_capturando(cap),
        canal="TESTE",
        caminho_log=log,
        agora=_relogio_relativo(cap, delta),
    )

    assert desfecho["decisao"] == "APROVADO"
    assert desfecho["executado"] is True
    assert desfecho["resultado_banco"] == "ENCERRADA"
    assert oracle_fake.conexoes_kill == [USER_KILL_FAKE]
    assert oracle_fake.conexoes.count(USER_DIAG_FAKE) == 2
    assert len(ambiente_fake) == 1
    assert ambiente_fake[0]["assunto"].startswith("[AGENTE DBA] Intervenção Aprovada por dba_teste")

    registros = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert len(registros) == 2  # decisão 1: INTENCAO + RESULTADO
    intencao, resultado = registros
    assert intencao["fase"] == "INTENCAO"
    assert intencao["decisao"] == "APROVADO"
    assert intencao["resultado_banco"] is None
    assert resultado["fase"] == "RESULTADO"
    assert intencao["id_intervencao"] == resultado["id_intervencao"]
    assert re.fullmatch(r"[0-9a-f]{32}", resultado["id_intervencao"])
    assert resultado["decisao"] == "APROVADO"
    assert resultado["motivo"] is None


def test_resultado_nao_usuario_com_aprovacao_nao_envia_email_de_aprovada(monkeypatch, tmp_path, ambiente_fake):
    """APROVADO + PKG retornando NAO_USUARIO -> e-mail "NÃO executada", nunca assunto de aprovada."""
    linha = _linha_alvo()
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([linha, linha], status_pkg="NAO_USUARIO"))

    desfecho = conduzir_kill_hitl(
        dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=tmp_path / "kill.log"
    )

    assert oracle_fake.conexoes_kill == [USER_KILL_FAKE]
    assert any("PKG_OPS_KILL.KILL_SESSION" in sql for conta, sql, _ in oracle_fake.sql_executado if conta == "KILL")
    assert desfecho["decisao"] == "APROVADO"
    assert desfecho["resultado_banco"] == "NAO_USUARIO"
    assert desfecho["executado"] is False
    assert len(ambiente_fake) == 1
    assunto = ambiente_fake[0]["assunto"]
    assert "Aprovada" not in assunto
    assert "NÃO executada" in assunto
    assert "NAO_USUARIO" in assunto
    assert "NAO_USUARIO" in ambiente_fake[0]["corpo"]


def test_registro_log_contem_decisao_e_resultado_banco_separados(monkeypatch, tmp_path, ambiente_fake):
    """Registro JSONL grava decisao e resultado_banco em campos distintos (aprovado-executado e rejeitado)."""
    linha = _linha_alvo()
    _instalar_oracle(monkeypatch, _OracleFake([linha, linha], status_pkg="ENCERRADA"))
    log_aprovacao = tmp_path / "kill.log"

    desfecho = conduzir_kill_hitl(
        dict(ARGS_ALVO), solicitar_aprovacao=_aprovar("dba_chefe"), canal="TESTE", caminho_log=log_aprovacao
    )
    assert desfecho["executado"] is True

    _instalar_oracle(monkeypatch, _OracleFake([linha], kill_permitido=False))
    conduzir_kill_hitl(
        dict(ARGS_ALVO),
        solicitar_aprovacao=lambda prep: ("REJEITADO", "dba_chefe", "REJEITADO_PELO_APROVADOR"),
        canal="TESTE",
        caminho_log=log_aprovacao,
    )

    registros = [json.loads(l) for l in log_aprovacao.read_text(encoding="utf-8").splitlines()]
    assert len(registros) == 3  # decisão 1: INTENCAO + RESULTADO do aprovado, mais o REJEITADO
    intencao, aprovado, rejeitado = registros
    for reg in registros:
        assert "decisao" in reg and "resultado_banco" in reg
        assert "status_banco" not in reg

    assert intencao["fase"] == "INTENCAO"
    assert intencao["decisao"] == "APROVADO"
    assert intencao["resultado_banco"] is None
    assert aprovado["fase"] == "RESULTADO"
    assert intencao["id_intervencao"] == aprovado["id_intervencao"]
    assert re.fullmatch(r"[0-9a-f]{32}", aprovado["id_intervencao"])
    assert rejeitado["fase"] == "RESULTADO"
    assert aprovado["decisao"] == "APROVADO"
    assert aprovado["resultado_banco"] == "ENCERRADA"
    assert rejeitado["decisao"] == "REJEITADO"
    assert rejeitado["resultado_banco"] is None
    assert rejeitado["motivo"] == "REJEITADO_PELO_APROVADOR"

    assert len(ambiente_fake) == 1
    assert ambiente_fake[0]["assunto"].startswith("[AGENTE DBA] Intervenção Aprovada por dba_chefe")

    conteudo = log_aprovacao.read_text(encoding="utf-8")
    assert "senha-fake" not in conteudo


def test_log_real_de_aprovacao_intacto(snapshot_log_real_inicio):
    """O log real de aprovação (stat apenas) não mudou desde o início da sessão."""
    real = Path(__file__).resolve().parent.parent / "data" / "logs" / "kill_approval.log"
    try:
        st = real.stat()
        atual = (True, st.st_size, st.st_mtime_ns)
    except FileNotFoundError:
        atual = (False, None, None)
    assert atual == snapshot_log_real_inicio


def test_caminho_padrao_redirecionado(isolar_log_aprovacao):
    """registrar_log_aprovacao_kill sem caminho_log grava no tmp redirecionado, não no real."""
    real = Path(__file__).resolve().parent.parent / "data" / "logs" / "kill_approval.log"
    assert oracle_dba.CAMINHO_LOG_APROVACAO_PADRAO == isolar_log_aprovacao
    assert oracle_dba._caminho_log_efetivo(None) == isolar_log_aprovacao
    assert isolar_log_aprovacao != real
    assert not isolar_log_aprovacao.exists()

    registrar_log_aprovacao_kill(
        "dba_teste", "REJEITADO", "hash-fake", {"sid": 1}, motivo="TESTE",
        fase="RESULTADO", id_intervencao="0" * 32,
    )

    assert isolar_log_aprovacao.exists()
    registro = json.loads(isolar_log_aprovacao.read_text(encoding="utf-8").splitlines()[0])
    assert registro["aprovador"] == "dba_teste"


# =============================================================================
# A3. ITEM 6 v2 (1.11-V2-item6, passo 5a) — IDENTIDADE E REF NO KILL (SÓ MOCK, SEM ORACLE_SANDBOX)
# =============================================================================
# Especificação: docs/entregas/1.11/v2_refeito/decisao.md §7 (D6) e §9 (T1-T10; T6 fica de fora deste passo).
# O mock prova binds, formais, ordem, valores, tipo e tratamento de p_status; NÃO prova a comparação no
# servidor, o PLS-00306 real nem o NLS (isso é do ensaio sandbox 4.1).

ORDEM_V2 = [
    "p_inst_id", "p_sid", "p_serial", "p_username_esperado", "p_program_esperado", "p_machine_esperado",
    "p_logon_time_esperado", "p_ref_aprovacao", "p_status",
]
LOGON_TIME_PADRAO = datetime(2026, 11, 23, 10, 0, 0)


def _binds_kill(oracle_fake):
    """Os (sql, binds) de cada execute da conta KILL, na ordem."""
    return [(sql, binds) for conta, sql, binds in oracle_fake.sql_executado if conta == "KILL"]


def _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake, argumentos=None):
    """Roda o fluxo completo (preparar -> aprovar -> reconsulta -> kill) com o fake; devolve (desfecho, log)."""
    _instalar_oracle(monkeypatch, oracle_fake)
    log = tmp_path / "kill.log"
    desfecho = conduzir_kill_hitl(
        dict(argumentos or ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=log
    )
    registros = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    return desfecho, registros


# ---- T1: assinaturas (D4) ----------------------------------------------------

@pytest.mark.parametrize(
    "funcao, nomes",
    [
        (matar_sessao_oracle, ("identidade_esperada", "ref_aprovacao")),
        (oracle_dba.executar_kill_verificado, ("aprovacao_expirada", "ref_aprovacao")),
    ],
    ids=["matar_sessao_oracle", "executar_kill_verificado"],
)
def test_t1_assinatura_keyword_only_sem_default(funcao, nomes):
    """T1: identidade_esperada/ref_aprovacao (e aprovacao_expirada) são KEYWORD_ONLY, sem default."""
    params = inspect.signature(funcao).parameters
    for nome in nomes:
        assert nome in params, f"{funcao.__name__} sem o parâmetro {nome}"
        assert params[nome].kind is inspect.Parameter.KEYWORD_ONLY, f"{nome} deve ser keyword-only"
        assert params[nome].default is inspect.Parameter.empty, f"{nome} não pode ter default"


# ---- T2: validação local antes do getenv (D1, D5) -----------------------------

def _ident(**sobrescritas):
    ident = dict(IDENTIDADE_VALIDA)
    ident.update(sobrescritas)
    return ident


def _ident_sem(chave):
    ident = dict(IDENTIDADE_VALIDA)
    del ident[chave]
    return ident


_SENT = "SENTINELA_NAO_ECOAR"

CASOS_IDENTIDADE_INVALIDA = [
    pytest.param(None, REF_VALIDO, (), id="identidade_none"),
    pytest.param([("username", "APP_USER")], REF_VALIDO, (), id="identidade_lista"),
    pytest.param(_ident_sem("machine"), REF_VALIDO, (), id="chave_faltando"),
    pytest.param(dict(IDENTIDADE_VALIDA, extra=_SENT), REF_VALIDO, (_SENT,), id="chave_extra"),
    pytest.param(_ident(username=""), REF_VALIDO, (), id="username_vazio"),
    pytest.param(_ident(username=None), REF_VALIDO, (), id="username_none"),
    pytest.param(_ident(username=123), REF_VALIDO, (), id="username_int"),
    pytest.param(_ident(program=123), REF_VALIDO, (), id="program_int"),
    pytest.param(_ident(machine=123), REF_VALIDO, (), id="machine_int"),
    pytest.param(_ident(logon_time=None), REF_VALIDO, (), id="logon_none"),
    pytest.param(_ident(logon_time="2026-11-23 10:00:00"), REF_VALIDO, ("2026-11-23 10:00:00",), id="logon_str"),
    pytest.param(_ident(logon_time=date(2026, 11, 23)), REF_VALIDO, (), id="logon_date"),
    pytest.param(
        _ident(logon_time=datetime(2026, 11, 23, 10, 0, 0, tzinfo=timezone.utc)), REF_VALIDO, ("+00:00",),
        id="logon_tz_aware",
    ),
    pytest.param(_ident(logon_time=datetime(2026, 11, 23, 10, 0, 0, 1)), REF_VALIDO, (), id="logon_microsecond"),
    pytest.param(dict(IDENTIDADE_VALIDA), None, (), id="ref_none"),
    pytest.param(dict(IDENTIDADE_VALIDA), REF_VALIDO.encode("ascii"), (), id="ref_bytes"),
    pytest.param(dict(IDENTIDADE_VALIDA), "f" * 31, ("f" * 31,), id="ref_31_hex"),
    pytest.param(dict(IDENTIDADE_VALIDA), "F" * 32, ("F" * 32,), id="ref_maiusculo"),
    pytest.param(dict(IDENTIDADE_VALIDA), "f" * 33, ("f" * 33,), id="ref_33_hex"),
    pytest.param(dict(IDENTIDADE_VALIDA), "g" * 32, ("g" * 32,), id="ref_32_nao_hex"),
    pytest.param(dict(IDENTIDADE_VALIDA), REF_VALIDO + "\n", (), id="ref_hex_newline"),
    pytest.param(_ident(username="u" * 129), REF_VALIDO, ("u" * 129,), id="username_129_caracteres"),
    pytest.param(_ident(program="p" * 129), REF_VALIDO, ("p" * 129,), id="program_129_caracteres"),
    pytest.param(_ident(machine="m" * 129), REF_VALIDO, ("m" * 129,), id="machine_129_caracteres"),
    # K4/A10 parte 1 (mata m25): "" é inválido também onde None é aceito (no Oracle '' é NULL)
    pytest.param(_ident(program=""), REF_VALIDO, (), id="program_vazio"),
    pytest.param(_ident(machine=""), REF_VALIDO, (), id="machine_vazio"),
]


@pytest.mark.parametrize("identidade, ref, sentinelas", CASOS_IDENTIDADE_INVALIDA)
def test_t2_identidade_obrigatoria_param_invalido(monkeypatch, identidade, ref, sentinelas):
    """T2: identidade/ref inválidos -> PARAM_INVALIDO, sem connect, com credenciais KILL AUSENTES (a validação
    vem antes do getenv: ERRO_CONFIG indicaria a ordem errada); a mensagem só nomeia campos."""
    def fail_connect(*args, **kwargs):
        pytest.fail("oracledb.connect não deve ser chamado para identidade/ref inválidos")

    def fail_host(*args, **kwargs):
        pytest.fail("verificar_acessibilidade_host não deve ser chamado para identidade/ref inválidos")

    monkeypatch.setattr(oracledb, "connect", fail_connect)
    monkeypatch.setattr(oracle_dba, "verificar_acessibilidade_host", fail_host)
    for nome in ("ORACLE_USER_KILL", "ORACLE_PASSWORD_KILL", "ORACLE_DSN"):
        monkeypatch.delenv(nome, raising=False)

    bruto = matar_sessao_oracle(sid=10, serial=20, inst_id=1, identidade_esperada=identidade, ref_aprovacao=ref)
    res = json.loads(bruto)
    assert res["motivo"] == "PARAM_INVALIDO", f"obtido {res.get('motivo')!r}: a validação deve vir antes do getenv"
    assert res["status"] == "recusado"
    assert res["status_banco"] == "PARAM_INVALIDO"
    for sentinela in sentinelas:
        assert sentinela not in bruto, "a mensagem não pode ecoar valores recebidos"
    assert "BEGIN" not in bruto and "=>" not in bruto


# ---- T3: os 9 binds com valores exatos (D1) ----------------------------------

@pytest.mark.parametrize(
    "program, machine",
    [(None, "SRV-App01 "), ("App.EXE ", None)],
    ids=["program_none", "machine_none"],
)
def test_t3_nove_binds_valores_exatos(monkeypatch, ambiente_fake, program, machine):
    """T3: 9 binds nomeados, na ordem da spec; None vai como None; maiúsculas e espaço final idênticos (sem
    strip/upper/str); logon_time vai numa var DATE; exatamente 1 execute na conta KILL."""
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([], status_pkg="ENCERRADA"))
    ident = {"username": "App_User ", "program": program, "machine": machine, "logon_time": LOGON_TIME_PADRAO}

    res = json.loads(
        matar_sessao_oracle(sid=101, serial=202, inst_id=3, identidade_esperada=ident, ref_aprovacao=REF_VALIDO)
    )
    assert res["status_banco"] == "ENCERRADA"

    execucoes = _binds_kill(oracle_fake)
    assert len(execucoes) == 1, "exatamente 1 execute na conta KILL"
    sql, binds = execucoes[0]
    assert list(binds) == ORDEM_V2
    assert re.findall(r"\b(p_\w+)\s*=>", sql) == ORDEM_V2
    assert re.findall(r"\b(p_\w+)\s*=>\s*:(\w+)\b", sql) == [(n, n) for n in ORDEM_V2]
    assert binds["p_inst_id"] == 3 and binds["p_sid"] == 101 and binds["p_serial"] == 202
    assert binds["p_username_esperado"] == "App_User " and type(binds["p_username_esperado"]) is str
    assert binds["p_program_esperado"] == program and (program is None) == (binds["p_program_esperado"] is None)
    assert binds["p_machine_esperado"] == machine and (machine is None) == (binds["p_machine_esperado"] is None)
    assert binds["p_ref_aprovacao"] == REF_VALIDO
    assert binds["p_logon_time_esperado"].tipo is oracledb.DB_TYPE_DATE
    assert binds["p_logon_time_esperado"].getvalue() == LOGON_TIME_PADRAO
    assert type(binds["p_logon_time_esperado"].getvalue()) is datetime
    assert binds["p_status"].tipo is oracledb.DB_TYPE_VARCHAR


# ---- K3 (correcao/decisao_c1.md §10; plano 8.2 e 8.5): limite em caracteres x bytes, erro antes do execute,
#      chave ausente na reconsulta e identidade de 1 caractere ----

CAMPOS_TEXTO_IDENTIDADE = ["username", "program", "machine"]


@pytest.mark.parametrize("campo", CAMPOS_TEXTO_IDENTIDADE)
@pytest.mark.parametrize(
    "valor, status_esperado",
    [
        ("é" * 128, "PARAM_INVALIDO"),  # 128 caracteres = 256 bytes: o limite local (caracteres) aceita; o PKG não
        ("é" * 64, "ENCERRADA"),  # 128 bytes: passa nos dois
        ("a" * 128, "ENCERRADA"),  # exatamente no limite: passa (>= 128 seria erro de fronteira)
    ],
    ids=["e_128_caracteres_256_bytes", "e_64_caracteres_128_bytes", "a_128_caracteres"],
)
def test_k3_a44_limite_local_em_caracteres_e_limite_do_pkg_em_bytes(monkeypatch, ambiente_fake, campo, valor, status_esperado):
    """K3 (A4.4; mata M_LIMITE_GE_128 e m27): o valor passa pela validação local (1 execute na conta KILL, bind
    idêntico ao valor) e o status vem do fake, que simula o LENGTHB > 128 do PKG com a premissa de charset
    AL32UTF8 (NÃO VERIFICADA, L7). O caso "é"*128 é recusa do PKG: desconhecido False e nada executado."""
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([], status_pkg="ENCERRADA"))
    ident = _ident(**{campo: valor})

    res = json.loads(
        matar_sessao_oracle(sid=101, serial=202, inst_id=1, identidade_esperada=ident, ref_aprovacao=REF_VALIDO)
    )

    execucoes = _binds_kill(oracle_fake)
    assert len(execucoes) == 1, "a validação local deve aceitar o valor (limite em caracteres): 1 execute KILL"
    assert execucoes[0][1][f"p_{campo}_esperado"] == valor
    assert res["status_banco"] == status_esperado
    assert res["resultado_desconhecido"] is False
    if status_esperado == "PARAM_INVALIDO":
        assert "executado para" not in res["mensagem"]


@pytest.mark.parametrize("erro_fake", ["erro_var_kill", "erro_setvalue"])
@pytest.mark.parametrize(
    "excecao, motivo_esperado",
    [
        (oracledb.DatabaseError("ORA-00600: erro fake antes do execute"), "ERRO_ORACLE"),
        (RuntimeError("falha fake antes do execute"), "RuntimeError"),
    ],
    ids=["oracle_error", "excecao_generica"],
)
def test_k3_a7a_erro_antes_do_execute_nao_e_desconhecido_e_nao_executa(
    monkeypatch, ambiente_fake, erro_fake, excecao, motivo_esperado
):
    """K3 (A7a; mata M_EXEC_INICIADO_ANTES_VAR): erro no cursor.var ou no setvalue, antes do execute, prova que o
    PKG não rodou: resultado_desconhecido False e 0 execute na conta KILL."""
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([], status_pkg="ENCERRADA", **{erro_fake: excecao}))

    res = json.loads(
        matar_sessao_oracle(
            sid=101, serial=202, inst_id=1, identidade_esperada=dict(IDENTIDADE_VALIDA), ref_aprovacao=REF_VALIDO,
        )
    )

    assert oracle_fake.conexoes_kill == [USER_KILL_FAKE], "a conexão KILL abriu e o erro veio depois dela"
    assert _binds_kill(oracle_fake) == [], "0 execute na conta KILL"
    assert res["motivo"] == motivo_esperado
    assert res["resultado_desconhecido"] is False
    assert oracle_dba.MENSAGEM_RESULTADO_DESCONHECIDO not in res["mensagem"]


def _reconsulta_diag(**sobrescritas):
    """Retorno de consultar_alvo_sessao_diag com o alvo completo e program/machine None (valores aceitos)."""
    alvo = {
        "inst_id": 1, "sid": 101, "serial#": 202, "username": "APP_USER", "program": None, "machine": None,
        "logon_time": LOGON_TIME_PADRAO,
    }
    alvo.update(sobrescritas)
    return {"encontrado": True, "elegivel": True, "alvo": alvo}


def _executar_verificado(hash_aprovado):
    return oracle_dba.executar_kill_verificado(
        inst_id=1, sid=101, serial=202, hash_aprovado=hash_aprovado,
        aprovacao_expirada=lambda: False, ref_aprovacao=REF_VALIDO,
    )


@pytest.mark.parametrize(
    "chaves_ausentes", [("program",), ("machine",), ("program", "machine")],
    ids=["sem_program", "sem_machine", "sem_program_nem_machine"],
)
def test_k3_a7b_reconsulta_sem_a_chave_com_hash_igual_e_param_invalido_sem_conexao_kill(
    monkeypatch, ambiente_fake, chaves_ausentes
):
    """K3 (A7b; mata M_EXEC_KILL_GET_DEFAULT): a reconsulta não traz a chave program/machine e o hash bate (o hash
    lê a falta como None). A identidade enviada ao PKG só leva as chaves presentes; a falta de chave vira
    PARAM_INVALIDO na validação local, sem conexão KILL (um .get(c) a transformaria em None, que é aceito)."""
    hash_aprovado = oracle_dba.calcular_hash_identidade(_reconsulta_diag()["alvo"])
    reconsulta = _reconsulta_diag()
    for chave in chaves_ausentes:
        del reconsulta["alvo"][chave]
    assert oracle_dba.calcular_hash_identidade(reconsulta["alvo"]) == hash_aprovado
    monkeypatch.setattr(oracle_dba, "consultar_alvo_sessao_diag", lambda **kwargs: reconsulta)
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([], status_pkg="ENCERRADA", kill_permitido=False))

    res = json.loads(_executar_verificado(hash_aprovado))

    assert res["motivo"] == "PARAM_INVALIDO" and res["status"] == "recusado"
    assert res["resultado_desconhecido"] is False
    assert oracle_fake.conexoes_kill == [], "sem conexão KILL"
    assert _binds_kill(oracle_fake) == []


def test_k3_a7b_controle_reconsulta_com_as_chaves_none_executa(monkeypatch, ambiente_fake):
    """K3 (A7b, controle): com as chaves presentes (valor None) a mesma reconsulta executa. Sem isto, o teste
    acima passaria também se qualquer reconsulta fosse recusada."""
    reconsulta = _reconsulta_diag()
    hash_aprovado = oracle_dba.calcular_hash_identidade(reconsulta["alvo"])
    monkeypatch.setattr(oracle_dba, "consultar_alvo_sessao_diag", lambda **kwargs: reconsulta)
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([], status_pkg="ENCERRADA"))

    res = json.loads(_executar_verificado(hash_aprovado))

    assert res["status_banco"] == "ENCERRADA"
    assert len(_binds_kill(oracle_fake)) == 1


@pytest.mark.parametrize("campo", CAMPOS_TEXTO_IDENTIDADE)
def test_k3_a7d_texto_de_identidade_de_1_caractere_e_aceito(monkeypatch, ambiente_fake, campo):
    """K3 (A7d): len 1 é o mínimo aceito (A10 recusa só o vazio) nos 3 campos de texto."""
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([], status_pkg="ENCERRADA"))

    res = json.loads(
        matar_sessao_oracle(
            sid=101, serial=202, inst_id=1, identidade_esperada=_ident(**{campo: "x"}), ref_aprovacao=REF_VALIDO,
        )
    )

    assert res["status_banco"] == "ENCERRADA"
    assert len(_binds_kill(oracle_fake)) == 1


# ---- T4: logon_time entra no hash (D3) ---------------------------------------

def test_t4_logon_time_diferente_na_reconsulta_alvo_alterado(monkeypatch, tmp_path, ambiente_fake):
    """T4: só o logon_time muda entre aprovação e reconsulta -> ALVO_ALTERADO, 0 conexões KILL, RESULTADO gravada."""
    aprovada = _linha_alvo(logon_time=datetime(2026, 11, 23, 10, 0, 0))
    reconsulta = _linha_alvo(logon_time=datetime(2026, 11, 23, 10, 0, 1))
    oracle_fake = _OracleFake([aprovada, reconsulta], kill_permitido=False)

    desfecho, registros = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)

    assert desfecho["decisao"] == "APROVADO"
    assert desfecho["resultado_banco"] == "ALVO_ALTERADO"
    assert desfecho["executado"] is False
    assert oracle_fake.conexoes_kill == []
    assert [r["fase"] for r in registros] == ["INTENCAO", "RESULTADO"]
    assert registros[1]["resultado_banco"] == "ALVO_ALTERADO"
    assert registros[0]["id_intervencao"] == registros[1]["id_intervencao"]


# ---- T5: ALVO_DIVERGENTE não é execução (D5) ---------------------------------

def test_t5_alvo_divergente_nao_executado(monkeypatch, tmp_path, ambiente_fake):
    """T5: p_status=ALVO_DIVERGENTE -> executado False, e-mail 'NÃO executada', mensagem sem 'executado para',
    RESULTADO gravada. (A tela CLI/Web cai no ramo 'NÃO EXECUTADA' já existente: tests/test_fluxo_cli.py e
    tests/test_fluxo_web.py; este arquivo não importa main/app.)"""
    assert "ALVO_DIVERGENTE" not in oracle_dba.RESULTADOS_KILL_EXECUTADO
    oracle_fake = _OracleFake([_linha_alvo(), _linha_alvo()], status_pkg="ALVO_DIVERGENTE")

    desfecho, registros = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)

    assert oracle_fake.conexoes_kill == [USER_KILL_FAKE]
    assert desfecho["resultado_banco"] == "ALVO_DIVERGENTE"
    assert desfecho["executado"] is False
    assert desfecho["resultado_desconhecido"] is False
    assert len(ambiente_fake) == 1
    assunto = ambiente_fake[0]["assunto"]
    assert "NÃO executada" in assunto and "Aprovada" not in assunto and "ALVO_DIVERGENTE" in assunto
    tool = json.loads(desfecho["resultado_tool"])
    assert tool["executado"] is False
    assert "executado para" not in tool["mensagem"]
    assert "NÃO executado" in tool["mensagem"]
    assert registros[-1]["fase"] == "RESULTADO" and registros[-1]["resultado_banco"] == "ALVO_DIVERGENTE"


# ---- T7: o resultado_tool do LLM não vaza ref, credenciais, identidade nem SQL (D5) ----

def _casos_t7():
    base = [_linha_alvo(), _linha_alvo()]
    micro = _linha_alvo(logon_time=datetime(2026, 11, 23, 10, 0, 0, 1))
    return [
        pytest.param(dict(linhas=base, fake=dict(status_pkg="ENCERRADA")), "ENCERRADA", id="encerrada"),
        pytest.param(dict(linhas=base, fake=dict(status_pkg="ALVO_DIVERGENTE")), "ALVO_DIVERGENTE", id="divergente"),
        # logon_time com microssegundo na DIAG: desde a correção A10 (parte 2) a recusa é antes do prompt HITL
        pytest.param(dict(linhas=[micro, micro], fake=dict(kill_permitido=False)), "PARAM_INVALIDO", id="param_invalido"),
        pytest.param(
            dict(linhas=base, fake=dict(erro_kill=oracledb.DatabaseError("ORA-00600: erro interno"))),
            "ERRO_ORACLE", id="erro_oracle",
        ),
        # A5 (só :935, ramo D8): o DSN fictício também não pode ir ao LLM
        pytest.param(
            dict(
                linhas=base, fake=dict(status_pkg="ENCERRADA", erro_getvalue_status=RuntimeError("falha simulada")),
                proibidos_extra=["host-teste:1521/TESTE", "instancia"],
            ),
            "RuntimeError", id="d8",
        ),
    ]


@pytest.mark.parametrize("cenario_t7, esperado", _casos_t7())
def test_t7_resultado_tool_sem_ref_credenciais_identidade_nem_sql(
    monkeypatch, tmp_path, ambiente_fake, cenario_t7, esperado
):
    """T7: o JSON que volta ao LLM não traz id_intervencao/ref, senha ou usuário, valores de identidade nem SQL."""
    oracle_fake = _OracleFake(cenario_t7["linhas"], **cenario_t7["fake"])
    desfecho, registros = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)

    if esperado == "PARAM_INVALIDO":
        # Expectativa alterada, declarada (plano 8.10.2; correcao/decisao_c1.md ponto 5): a identidade inválida
        # da DIAG é recusada antes do prompt, sem KILL; o JSONL só tem o evento RECUSA_PRE_HITL, e o id dele
        # é o que não pode ir ao LLM. A cobertura do PARAM_INVALIDO de matar_sessao_oracle fica no T2.
        assert desfecho["prompt_exibido"] is False and desfecho["motivo"] == "PARAM_INVALIDO"
        assert oracle_fake.conexoes_kill == []
        assert [r["fase"] for r in registros] == ["RECUSA_PRE_HITL"]
        id_proibido = registros[0]["id_intervencao"]
    else:
        assert desfecho["resultado_banco"] == esperado
        id_proibido = desfecho["id_intervencao"]
    tool = desfecho["resultado_tool"]
    assert re.fullmatch(r"[0-9a-f]{32}", id_proibido)
    proibidos = [
        id_proibido, "senha-fake", USER_KILL_FAKE, USER_DIAG_FAKE,
        "APP_USER", "app.exe", "srv-app01", "2026-11-23 10:00:00", "2026-11-23T10:00:00",
        "BEGIN", "=>", "p_ref_aprovacao", "ref_aprovacao",
    ] + cenario_t7.get("proibidos_extra", [])
    for texto in proibidos:
        assert texto not in tool, f"resultado_tool de {esperado} traz {texto!r}"


# ---- K4 (A10 parte 2): identidade inválida da DIAG -> recusa antes do prompt, evento RECUSA_PRE_HITL ----
# decisao_c1.md ponto 5 e secao 10 (linha A10-2). O logon_time vai no ano 2001 para nunca coincidir com o
# timestamp (2026) do evento; os textos de identidade levam sentinelas que não são hexadecimais.

_USR_K4, _PROG_K4, _MACH_K4 = "USR_K4_SENT", "prog_k4_sent.exe", "mach-k4-sent"
_LOGON_MICRO_2001 = datetime(2001, 3, 4, 5, 6, 7, 123456)
_CHAVES_RECUSA_PRE_HITL = {"timestamp", "fase", "id_intervencao", "motivo", "campos_invalidos", "parametros"}

CASOS_RECUSA_PRE_HITL = [
    pytest.param(dict(logon_time=_LOGON_MICRO_2001), ["logon_time"], id="logon_microsecond"),
    pytest.param(dict(program=""), ["program"], id="program_vazio"),
    pytest.param(dict(machine=""), ["machine"], id="machine_vazio"),
    pytest.param(
        dict(program="", machine="", logon_time=_LOGON_MICRO_2001), ["program", "machine", "logon_time"],
        id="tres_campos_na_ordem_da_funcao",
    ),
]


def _linha_diag_k4(**sobrescritas):
    campos = dict(username=_USR_K4, program=_PROG_K4, machine=_MACH_K4, logon_time=datetime(2001, 3, 4, 5, 6, 7))
    campos.update(sobrescritas)
    return _linha_alvo(**campos)


def _sem_valores_de_identidade(texto):
    for proibido in (_USR_K4, _PROG_K4, _MACH_K4, "2001", "123456"):
        assert proibido not in texto, f"valor de identidade {proibido!r} no texto"


@pytest.mark.parametrize("sobrescritas, campos_esperados", CASOS_RECUSA_PRE_HITL)
def test_k4_a10_2_identidade_invalida_na_diag_recusa_antes_do_prompt_so_com_o_evento_recusa_pre_hitl(
    monkeypatch, tmp_path, ambiente_fake, caplog, sobrescritas, campos_esperados
):
    """K4/A10-2 (mata m31): µs ou '' na GV$SESSION -> sem prompt, sem KILL, sem e-mail; o JSONL só tem a linha
    RECUSA_PRE_HITL, com as chaves exatas e sem valores de identidade; o reconciliador a ignora."""
    linha = _linha_diag_k4(**sobrescritas)
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([linha, linha], kill_permitido=False))
    log = tmp_path / "kill.log"

    with caplog.at_level(logging.WARNING, logger=oracle_dba.logger.name):
        desfecho = conduzir_kill_hitl(
            dict(ARGS_ALVO), solicitar_aprovacao=_prompt_proibido, canal="TESTE", caminho_log=log
        )

    assert desfecho["prompt_exibido"] is False and desfecho["motivo"] == "PARAM_INVALIDO"
    assert desfecho["id_intervencao"] is None
    assert oracle_fake.conexoes_kill == [] and all(conta == "DIAG" for conta, _, _ in oracle_fake.sql_executado)
    assert ambiente_fake == [], "recusa local não envia e-mail"
    tool = json.loads(desfecho["resultado_tool"])
    assert tool["status"] == "recusado" and tool["motivo"] == "PARAM_INVALIDO"
    assert all(c in tool["mensagem"] for c in campos_esperados)

    bruto = log.read_bytes()
    registros = [json.loads(l) for l in bruto.decode("utf-8").splitlines()]
    assert len(registros) == 1, "só a linha RECUSA_PRE_HITL (nenhuma INTENCAO nem RESULTADO)"
    reg = registros[0]
    assert set(reg) == _CHAVES_RECUSA_PRE_HITL
    assert reg["fase"] == "RECUSA_PRE_HITL" and reg["motivo"] == "PARAM_INVALIDO"
    assert reg["campos_invalidos"] == campos_esperados
    assert reg["parametros"] == {"inst_id": 1, "sid": 101, "serial": 202}
    assert re.fullmatch(r"[0-9a-f]{32}", reg["id_intervencao"])
    assert datetime.fromisoformat(reg["timestamp"]).tzinfo is not None
    # o id (hexadecimal) e o timestamp ficam fora da busca de "2001": o resto da linha não tem identidade
    _sem_valores_de_identidade(json.dumps({k: v for k, v in reg.items() if k not in ("id_intervencao", "timestamp")}))
    _sem_valores_de_identidade(json.dumps(tool))
    for proibido in (_USR_K4, _PROG_K4, _MACH_K4):
        assert proibido not in bruto.decode("utf-8")
    assert reg["id_intervencao"] not in desfecho["resultado_tool"]

    avisos = [r.getMessage() for r in caplog.records if "HITL RECUSADO LOCALMENTE" in r.getMessage()]
    assert len(avisos) == 1 and reg["id_intervencao"] in avisos[0] and str(campos_esperados) in avisos[0]
    _sem_valores_de_identidade(avisos[0].replace(reg["id_intervencao"], ""))

    # o reconciliador ignora a linha: nada reconciliado, nada inválido, arquivo byte a byte igual
    futuro = datetime.now(timezone.utc) + timedelta(days=1)
    resumo = oracle_dba.reconciliar_intencoes_orfas(caminho_log=log, agora=lambda: futuro)
    assert resumo["reconciliadas"] == [] and resumo["linhas_invalidas"] == 0
    assert resumo["recentes"] == [] and resumo["timestamp_invalido"] == []
    assert log.read_bytes() == bruto


def test_k4_a10_2_recusa_pre_hitl_nao_e_fase_de_registrar_log_aprovacao_kill(tmp_path):
    """K4/A10-2 (mata m31): a fase do evento fica FORA de FASES_REGISTRO_KILL; a API pública continua
    recusando-a com ValueError e sem criar arquivo."""
    assert "RECUSA_PRE_HITL" not in oracle_dba.FASES_REGISTRO_KILL
    log = tmp_path / "kill.log"
    with pytest.raises(ValueError):
        registrar_log_aprovacao_kill(
            "dba_teste", "APROVADO", "h" * 64, {"inst_id": 1, "sid": 101, "serial": 202},
            caminho_log=log, fase="RECUSA_PRE_HITL", id_intervencao="0123456789abcdef0123456789abcdef",
        )
    assert not log.exists()


def test_k4_a10_2_falha_ao_gravar_o_evento_da_logger_error_e_a_recusa_se_mantem(
    monkeypatch, tmp_path, ambiente_fake, caplog
):
    """K4/A10-2 (mata m31): falha de E/S no evento -> logger.error (tipo, errno, registro serializado) e a
    recusa segue: sem prompt, sem KILL, sem arquivo."""
    linha = _linha_diag_k4(logon_time=_LOGON_MICRO_2001)
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([linha, linha], kill_permitido=False))
    log = tmp_path / "kill.log"

    def _gravar_falha(caminho_log, registro):
        raise OSError(28, "disco cheio (simulado)")

    monkeypatch.setattr(oracle_dba, "_gravar_linha_jsonl_duravel", _gravar_falha)
    with caplog.at_level(logging.WARNING, logger=oracle_dba.logger.name):
        desfecho = conduzir_kill_hitl(
            dict(ARGS_ALVO), solicitar_aprovacao=_prompt_proibido, canal="TESTE", caminho_log=log
        )

    assert desfecho["prompt_exibido"] is False and desfecho["motivo"] == "PARAM_INVALIDO"
    assert oracle_fake.conexoes_kill == [] and not log.exists()
    erros = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(erros) == 1
    texto = erros[0].getMessage()
    assert "FALHA AO GRAVAR RECUSA_PRE_HITL" in texto and "OSError" in texto and "errno=28" in texto
    assert '"campos_invalidos"' in texto and "logon_time" in texto
    for proibido in (_USR_K4, _PROG_K4, _MACH_K4):
        assert proibido not in texto
    assert any("HITL RECUSADO LOCALMENTE" in r.getMessage() for r in caplog.records), "o warning também sai"


# ---- K4 (A8): matar_sessao_oracle fora da exportação de src.tools ----------------

def test_k4_a8_matar_sessao_oracle_nao_e_exportada_por_src_tools():
    """K4/A8 (mata m23): src.tools não exporta matar_sessao_oracle (nem em __all__, nem como atributo, nem por
    import *); a função continua em src.tools.oracle_dba, que é o caminho do conduzir_kill_hitl."""
    import src.tools as pacote_tools

    assert "matar_sessao_oracle" not in pacote_tools.__all__
    assert not hasattr(pacote_tools, "matar_sessao_oracle")
    espaco = {}
    exec("from src.tools import *", espaco)
    assert "matar_sessao_oracle" not in espaco
    assert callable(oracle_dba.matar_sessao_oracle), "o teste seria vazio se a função tivesse sumido"


# ---- T8: logon_time no SELECT DIAG, no hash e recalculável a partir do JSONL (D3) ----

def test_t8_logon_time_no_select_diag_no_hash_e_no_jsonl(monkeypatch, tmp_path, ambiente_fake):
    """T8: o SELECT DIAG lê logon_time; +1 s muda o hash; o hash é recalculável da linha INTENCAO;
    todo campo enviado ao PKG está no hash."""
    # Invariante (L23): todo campo da identidade esperada está nos campos hasheados
    esperados = set(oracle_dba.CAMPOS_IDENTIDADE_ESPERADA)
    assert esperados == {"username", "program", "machine", "logon_time"}
    assert esperados <= set(oracle_dba.CAMPOS_IDENTIDADE_ALVO)

    # O SQL DIAG (a description do fake é fixa e esconde a remoção da coluna: confere-se o texto do SELECT)
    oracle_fake = _OracleFake([_linha_alvo(), _linha_alvo()], status_pkg="ENCERRADA")
    desfecho, registros = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)
    sqls_diag = [sql for conta, sql, _ in oracle_fake.sql_executado if conta == "DIAG" and "gv$session" in sql.lower()]
    assert len(sqls_diag) == 2
    for sql in sqls_diag:
        assert re.search(r"\blogon_time\b", sql, re.IGNORECASE), "o SELECT DIAG deve ler logon_time"

    # +1 s no logon_time muda o hash
    base = dict(zip([c.lower() for c in COLUNAS_ALVO], _linha_alvo()))
    mais_1s = dict(base, logon_time=base["logon_time"] + timedelta(seconds=1))
    assert calcular_hash_identidade(base) != calcular_hash_identidade(mais_1s)

    # Auditoria offline: o hash recalculado do JSON da INTENCAO é o hash_payload gravado
    intencao = registros[0]
    assert intencao["fase"] == "INTENCAO"
    assert intencao["alvo"]["logon_time"] == "2026-11-23 10:00:00"
    assert calcular_hash_identidade(intencao["alvo"]) == intencao["hash_payload"]
    assert calcular_hash_identidade(base) == intencao["hash_payload"]


# ---- T9: exceção depois do execute = resultado desconhecido, sem retentativa (D8) ----

def test_t9_excecao_no_getvalue_apos_execute_resultado_desconhecido(monkeypatch, tmp_path, ambiente_fake):
    """T9: o getvalue do p_status levanta RuntimeError depois do execute -> resultado_desconhecido True,
    executado False, exatamente 1 execute na conta KILL (sem retentativa) e RESULTADO gravada."""
    oracle_fake = _OracleFake(
        [_linha_alvo(), _linha_alvo()], status_pkg="ENCERRADA", erro_getvalue_status=RuntimeError("falha simulada")
    )
    desfecho, registros = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)

    assert len(_binds_kill(oracle_fake)) == 1, "sem retentativa: 1 execute só"
    assert desfecho["resultado_desconhecido"] is True
    assert desfecho["executado"] is False
    tool = json.loads(desfecho["resultado_tool"])
    assert tool["resultado_desconhecido"] is True
    assert oracle_dba.MENSAGEM_RESULTADO_DESCONHECIDO in tool["mensagem"]
    assert len(ambiente_fake) == 1
    assert "NÃO executada" not in ambiente_fake[0]["assunto"], "e-mail não pode afirmar 'NÃO executada'"
    assert oracle_dba.MENSAGEM_RESULTADO_DESCONHECIDO in ambiente_fake[0]["assunto"]
    assert [r["fase"] for r in registros] == ["INTENCAO", "RESULTADO"]


# ---- T10: o LLM não fornece identidade nem ref (D4) --------------------------

def test_t10_argumentos_extras_do_llm_sao_ignorados(monkeypatch, tmp_path, ambiente_fake):
    """T10: ref_aprovacao, logon_time, username, program e machine vindos do LLM são ignorados: os binds vêm
    da reconsulta DIAG e do id_intervencao gerado internamente."""
    oracle_fake = _OracleFake([_linha_alvo(), _linha_alvo()], status_pkg="ENCERRADA")
    argumentos = dict(
        ARGS_ALVO, ref_aprovacao="f" * 32, logon_time="1999-01-01 00:00:00",
        username="EVIL_USER", program="evil.exe", machine="evil-host",
    )
    desfecho, registros = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake, argumentos)

    assert desfecho["executado"] is True
    (sql, binds), = _binds_kill(oracle_fake)
    assert binds["p_username_esperado"] == "APP_USER"
    assert binds["p_program_esperado"] == "app.exe"
    assert binds["p_machine_esperado"] == "srv-app01"
    assert binds["p_logon_time_esperado"].getvalue() == LOGON_TIME_PADRAO
    assert binds["p_ref_aprovacao"] == desfecho["id_intervencao"] != "f" * 32
    assert binds["p_ref_aprovacao"] == registros[0]["id_intervencao"]


# ---- K2: desfecho fora da lista fechada e texto sem erro do Oracle (correcao/decisao_c1.md, pontos 1 a 4) ----

def _texto_do_desfecho_sem_execucao(desfecho):
    """Textos de um desfecho que não podem afirmar execução nem 'NÃO executada' (resultado desconhecido)."""
    tool = json.loads(desfecho["resultado_tool"])
    return tool, tool.get("mensagem", "")


@pytest.mark.parametrize(
    "status_pkg",
    ["ERRO_ORACLE", "", None, "XYZ", "encerrada"],
    ids=["erro_oracle", "vazio", "nulo", "codigo_novo", "minusculo"],
)
def test_k2_status_fora_da_lista_fechada_e_resultado_desconhecido(monkeypatch, tmp_path, ambiente_fake, status_pkg):
    """K2 (A1; mata m17 e m18): p_status fora das duas listas (ERRO_ORACLE, vazio, nulo, código novo, caixa
    diferente) -> resultado_desconhecido True, executado False, 1 execute na conta KILL; tool e e-mail dizem
    'resultado desconhecido' e nunca 'executado para' nem 'NÃO executada'."""
    oracle_fake = _OracleFake([_linha_alvo(), _linha_alvo()], status_pkg=status_pkg)
    desfecho, registros = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)

    assert len(_binds_kill(oracle_fake)) == 1, "sem retentativa: 1 execute só"
    assert desfecho["resultado_desconhecido"] is True
    assert desfecho["executado"] is False
    assert desfecho["resultado_banco"] == (status_pkg or oracle_dba.STATUS_PKG_VAZIO)
    tool, mensagem = _texto_do_desfecho_sem_execucao(desfecho)
    assert tool["resultado_desconhecido"] is True and tool["executado"] is False
    assert oracle_dba.MENSAGEM_RESULTADO_DESCONHECIDO in mensagem
    assert "executado para" not in mensagem
    assert "NÃO executad" not in mensagem
    assert len(ambiente_fake) == 1
    assunto = ambiente_fake[0]["assunto"]
    assert oracle_dba.MENSAGEM_RESULTADO_DESCONHECIDO in assunto
    assert "NÃO executada" not in assunto and "Aprovada" not in assunto
    assert [r["fase"] for r in registros] == ["INTENCAO", "RESULTADO"]


# As 6 recusas do PKG que provam que nada foi encerrado (lista escrita aqui de propósito, sem ler a constante)
RECUSAS_ESPERADAS_PKG = [
    "PARAM_INVALIDO", "PROPRIA_SESSAO", "ALVO_NAO_ENCONTRADO", "ALVO_DIVERGENTE", "NAO_USUARIO", "USUARIO_PROTEGIDO",
]


@pytest.mark.parametrize("status_pkg", RECUSAS_ESPERADAS_PKG)
def test_k2_recusas_do_pkg_nao_sao_desconhecidas_nem_executadas(monkeypatch, tmp_path, ambiente_fake, status_pkg):
    """K2 (A1): cada recusa do PKG -> resultado_desconhecido False, executado False, mensagem própria (nunca
    'executado para'), e-mail 'NÃO executada' e não 'resultado desconhecido'."""
    oracle_fake = _OracleFake([_linha_alvo(), _linha_alvo()], status_pkg=status_pkg)
    desfecho, registros = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)

    assert len(_binds_kill(oracle_fake)) == 1
    assert desfecho["resultado_banco"] == status_pkg
    assert desfecho["resultado_desconhecido"] is False
    assert desfecho["executado"] is False
    tool, mensagem = _texto_do_desfecho_sem_execucao(desfecho)
    assert tool["resultado_desconhecido"] is False
    if status_pkg == "ALVO_DIVERGENTE":
        assert mensagem == oracle_dba.MENSAGEM_ALVO_DIVERGENTE
    else:
        assert mensagem == oracle_dba.MENSAGEM_RECUSA_PKG.format(status=status_pkg)
    assert "executado para" not in mensagem
    assert len(ambiente_fake) == 1
    assunto = ambiente_fake[0]["assunto"]
    assert "NÃO executada" in assunto and status_pkg in assunto
    assert oracle_dba.MENSAGEM_RESULTADO_DESCONHECIDO not in assunto and "Aprovada" not in assunto
    assert [r["fase"] for r in registros] == ["INTENCAO", "RESULTADO"]


def test_k2_executado_so_para_encerrada_e_marcada_para_kill(monkeypatch, tmp_path, ambiente_fake):
    """K2 (A1): o ramo 'executado para' continua valendo para MARCADA_PARA_KILL, com desconhecido False."""
    oracle_fake = _OracleFake([_linha_alvo(), _linha_alvo()], status_pkg="MARCADA_PARA_KILL")
    desfecho, _ = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)

    assert desfecho["executado"] is True and desfecho["resultado_desconhecido"] is False
    _, mensagem = _texto_do_desfecho_sem_execucao(desfecho)
    assert "executado para" in mensagem and "MARCADA_PARA_KILL" in mensagem
    assert "Aprovada" in ambiente_fake[0]["assunto"]


def test_k2_invariantes_das_listas_de_status_do_pkg():
    """K2 (L23; mata m17): listas disjuntas; códigos de erro fora das duas; e os literais v_status do SQL do PKG
    são exatamente RECUSAS U EXECUTADO U {ERRO_ORACLE} (status novo no SQL obriga a classificá-lo)."""
    recusas = set(oracle_dba.RECUSAS_PKG_SEM_KILL)
    executado = set(oracle_dba.RESULTADOS_KILL_EXECUTADO)
    assert recusas == set(RECUSAS_ESPERADAS_PKG)
    assert recusas.isdisjoint(executado)
    for valor in ("ERRO_ORACLE", "", "DESCONHECIDO", "ERRO_INTERNO"):
        assert valor not in recusas, f"{valor!r} não pode estar em RECUSAS_PKG_SEM_KILL"
        assert valor not in executado, f"{valor!r} não pode estar em RESULTADOS_KILL_EXECUTADO"
    sql = (ROOT_DIR_TESTE / "docs" / "entregas" / "1.11" / "item6" / "ops_kill.sql").read_text(
        encoding="utf-8", errors="replace"
    )
    literais = set(re.findall(r"v_status\s*:=\s*'([A-Z_]+)'", sql))
    assert literais, "nenhum v_status := '...' encontrado em ops_kill.sql"
    assert literais == recusas | executado | {"ERRO_ORACLE"}


class _ErroOracleStrQuebrado(oracledb.DatabaseError):
    """oracledb.Error cujo __str__ levanta (A3)."""

    def __str__(self):
        raise RuntimeError("SENTINELA_STR_QUEBRADO")


class _ErroGenericoStrQuebrado(Exception):
    """Exceção comum cujo __str__ levanta (A3)."""

    def __str__(self):
        raise RuntimeError("SENTINELA_STR_QUEBRADO")


@pytest.mark.parametrize(
    "falha, classe, desconhecido, motivo",
    [
        ("erro_kill", _ErroOracleStrQuebrado, True, "ERRO_ORACLE"),
        ("erro_getvalue_status", _ErroGenericoStrQuebrado, True, "_ErroGenericoStrQuebrado"),
        ("erro_connect_kill", _ErroOracleStrQuebrado, False, "ERRO_ORACLE"),
        ("erro_connect_kill", _ErroGenericoStrQuebrado, False, "_ErroGenericoStrQuebrado"),
    ],
    ids=["oracle_depois_do_execute", "generico_depois_do_execute", "oracle_antes_do_execute", "generico_antes_do_execute"],
)
def test_k2_str_do_erro_que_levanta_nao_escapa_de_matar_sessao(
    monkeypatch, ambiente_fake, falha, classe, desconhecido, motivo
):
    """K2 (A3; mata m21): o __str__ do erro levanta; nenhuma exceção sai de matar_sessao_oracle. Depois do execute:
    resultado_desconhecido True. Antes: False, e a mensagem é o nome do tipo (o texto do erro não é usado)."""
    oracle_fake = _OracleFake([], status_pkg="ENCERRADA", **{falha: classe("x")})
    _instalar_oracle(monkeypatch, oracle_fake)

    bruto = matar_sessao_oracle(
        sid=101, serial=202, inst_id=1, identidade_esperada=dict(IDENTIDADE_VALIDA), ref_aprovacao=REF_VALIDO
    )
    res = json.loads(bruto)
    assert res["status"] == "erro"
    assert res["motivo"] == motivo
    assert res["resultado_desconhecido"] is desconhecido
    assert "SENTINELA_STR_QUEBRADO" not in bruto
    if desconhecido:
        assert oracle_dba.MENSAGEM_RESULTADO_DESCONHECIDO in res["mensagem"]
        assert len(_binds_kill(oracle_fake)) == 1
    else:
        assert res["mensagem"] == classe.__name__
        assert _binds_kill(oracle_fake) == []


@pytest.mark.parametrize(
    "retorno",
    ["texto livre SENTINELA_ECO_DO_RETORNO", "[]", '"SENTINELA_ECO_DO_RETORNO"', None, "42"],
    ids=["nao_json", "lista_vazia", "json_string", "none", "json_numero"],
)
def test_k2_retorno_ilegivel_do_fluxo_de_kill_e_resultado_desconhecido(
    monkeypatch, tmp_path, ambiente_fake, retorno
):
    """K2 (A3; mata m20): matar_sessao_oracle devolve algo que não é um JSON dict -> resultado_desconhecido True,
    executado False, mensagem 'resultado desconhecido' e nenhum eco do texto recebido (tool, e-mail, JSONL)."""
    monkeypatch.setattr(oracle_dba, "matar_sessao_oracle", lambda *a, **k: retorno)
    oracle_fake = _OracleFake([_linha_alvo(), _linha_alvo()], kill_permitido=False)
    desfecho, registros = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)

    assert desfecho["resultado_desconhecido"] is True
    assert desfecho["executado"] is False
    assert desfecho["resultado_banco"] == oracle_dba.STATUS_PKG_VAZIO
    tool, mensagem = _texto_do_desfecho_sem_execucao(desfecho)
    assert tool["resultado_desconhecido"] is True and tool["executado"] is False
    assert oracle_dba.MENSAGEM_RESULTADO_DESCONHECIDO in mensagem
    assert "NÃO executad" not in mensagem
    assert len(ambiente_fake) == 1
    assert oracle_dba.MENSAGEM_RESULTADO_DESCONHECIDO in ambiente_fake[0]["assunto"]
    assert "NÃO executada" not in ambiente_fake[0]["assunto"]
    tudo = desfecho["resultado_tool"] + json.dumps(ambiente_fake) + json.dumps(registros)
    assert "SENTINELA_ECO_DO_RETORNO" not in tudo
    assert [r["fase"] for r in registros] == ["INTENCAO", "RESULTADO"]


@pytest.mark.parametrize(
    "chave",
    [{}, {"resultado_desconhecido": 0}, {"resultado_desconhecido": None}, {"resultado_desconhecido": "false"}],
    ids=["chave_ausente", "zero", "none", "texto_false"],
)
def test_k2_so_o_false_literal_tira_o_desconhecido(monkeypatch, tmp_path, ambiente_fake, chave):
    """K2 (A3; mata m20): JSON dict sem a chave, ou com 0, None ou 'false', continua desconhecido e executado
    False, mesmo com status_banco ENCERRADA; só o bool False explícito libera (controle positivo ao fim)."""
    monkeypatch.setattr(
        oracle_dba, "matar_sessao_oracle",
        lambda *a, **k: json.dumps(dict({"status": "ENCERRADA", "status_banco": "ENCERRADA"}, **chave)),
    )
    oracle_fake = _OracleFake([_linha_alvo(), _linha_alvo()], kill_permitido=False)
    desfecho, _ = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)

    assert desfecho["resultado_desconhecido"] is True
    assert desfecho["executado"] is False
    tool, _ = _texto_do_desfecho_sem_execucao(desfecho)
    assert tool["resultado_desconhecido"] is True and tool["executado"] is False
    assert oracle_dba.MENSAGEM_RESULTADO_DESCONHECIDO in ambiente_fake[0]["assunto"]


def test_k2_false_literal_explicito_libera_o_executado(monkeypatch, tmp_path, ambiente_fake):
    """K2: controle positivo do teste anterior: com resultado_desconhecido False explícito e ENCERRADA, executado."""
    monkeypatch.setattr(
        oracle_dba, "matar_sessao_oracle",
        lambda *a, **k: json.dumps({"status": "ENCERRADA", "status_banco": "ENCERRADA", "resultado_desconhecido": False}),
    )
    oracle_fake = _OracleFake([_linha_alvo(), _linha_alvo()], kill_permitido=False)
    desfecho, _ = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)

    assert desfecho["resultado_desconhecido"] is False and desfecho["executado"] is True
    assert "Aprovada" in ambiente_fake[0]["assunto"]


def _chaves_dos_json_dumps(funcao):
    """Para cada json.dumps(...) do código da função: (linha relativa, chaves literais do dict do 1º argumento)."""
    arvore = ast.parse(inspect.getsource(funcao))
    saida = []
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) and no.func.attr == "dumps"
            and isinstance(no.func.value, ast.Name) and no.func.value.id == "json"
        ):
            assert no.args and isinstance(no.args[0], ast.Dict), f"json.dumps sem dict literal na linha {no.lineno}"
            chaves = {k.value for k in no.args[0].keys if isinstance(k, ast.Constant)}
            saida.append((no.lineno, chaves))
    return saida


@pytest.mark.parametrize(
    "funcao, minimo",
    [(matar_sessao_oracle, 7), (oracle_dba.executar_kill_verificado, 4)],
    ids=["matar_sessao_oracle", "executar_kill_verificado"],
)
def test_k2_todo_json_dumps_traz_resultado_desconhecido(funcao, minimo):
    """K2 (decisao_c1.md, pontos 2a e 2c): todo json.dumps({...}) de matar_sessao_oracle e de
    executar_kill_verificado traz a chave resultado_desconhecido (o consumidor só aceita o bool False literal)."""
    chamadas = _chaves_dos_json_dumps(funcao)
    assert len(chamadas) >= minimo, f"{funcao.__name__}: esperava ao menos {minimo} json.dumps, achou {len(chamadas)}"
    faltando = [linha for linha, chaves in chamadas if "resultado_desconhecido" not in chaves]
    assert faltando == [], f"{funcao.__name__}: json.dumps sem resultado_desconhecido (linhas relativas {faltando})"


def test_k2_montar_notificacao_kill_resultado_desconhecido_keyword_only_sem_default():
    """K2 (ponto 2e): resultado_desconhecido é KEYWORD_ONLY e sem default (o chamador sempre o informa)."""
    parametro = inspect.signature(oracle_dba.montar_notificacao_kill).parameters["resultado_desconhecido"]
    assert parametro.kind is inspect.Parameter.KEYWORD_ONLY
    assert parametro.default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        oracle_dba.montar_notificacao_kill("dba", 1, 2, 3, "ENCERRADA", "h" * 64, "TESTE")


def test_k2_email_desconhecido_sem_erro_do_oracle_direto():
    """K2 (A9; mata m24): o corpo do e-mail desconhecido diz 'desfecho no banco não confirmado' e não 'erro do Oracle'."""
    assunto, corpo = oracle_dba.montar_notificacao_kill(
        "dba", 1, 101, 202, "XYZ", "h" * 64, "TESTE", resultado_desconhecido=True
    )
    assert oracle_dba.MENSAGEM_RESULTADO_DESCONHECIDO in assunto
    assert oracle_dba.MENSAGEM_DESFECHO_NAO_CONFIRMADO in corpo
    assert "erro do Oracle" not in corpo


@pytest.mark.parametrize(
    "fake",
    [
        dict(status_pkg="ENCERRADA", erro_getvalue_status=RuntimeError("falha simulada")),
        dict(status_pkg=""),
        dict(erro_kill=oracledb.DatabaseError("ORA-00600: erro interno")),
    ],
    ids=["d8_getvalue_levanta", "status_vazio", "erro_oracle_no_execute"],
)
def test_k2_email_do_desconhecido_no_fluxo_sem_erro_do_oracle(monkeypatch, tmp_path, ambiente_fake, fake):
    """K2 (A9; mata m24): no fluxo completo (D8, p_status vazio, erro do execute) o e-mail do desconhecido traz
    MENSAGEM_DESFECHO_NAO_CONFIRMADO e nunca 'erro do Oracle'."""
    oracle_fake = _OracleFake([_linha_alvo(), _linha_alvo()], **fake)
    desfecho, _ = _fluxo_aprovado(monkeypatch, tmp_path, oracle_fake)

    assert desfecho["resultado_desconhecido"] is True
    assert len(ambiente_fake) == 1
    corpo = ambiente_fake[0]["corpo"]
    assert oracle_dba.MENSAGEM_DESFECHO_NAO_CONFIRMADO in corpo
    assert "erro do Oracle" not in corpo


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
