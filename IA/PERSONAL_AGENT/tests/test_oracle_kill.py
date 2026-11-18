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
from datetime import datetime, timedelta, timezone
import inspect
import json
import os
from pathlib import Path
import pytest
import oracledb

import logging
import re
import uuid

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

# Identidade e referência válidas (formato) para chamadas diretas a matar_sessao_oracle.
IDENT_VALIDA = {
    "username": "APP_USER",
    "program": "app.exe",
    "machine": "srv-app01",
    "logon_time": datetime(2026, 11, 17, 8, 0, 0),
}
REF_VALIDA = "0123456789abcdef0123456789abcdef"
KW_V2 = {"identidade_esperada": IDENT_VALIDA, "ref_aprovacao": REF_VALIDA}


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
        res_json = matar_sessao_oracle(sid=sid_val, serial=serial_val, inst_id=inst_val, **KW_V2)
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

    res = json.loads(matar_sessao_oracle(sid=10, serial=20, inst_id=1, **KW_V2))
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
        matar_sessao_oracle(sid=10, serial=20, **KW_V2)

    for inst_invalido in (None, True, 1.5, "1a", "", 0, -3):
        res_inv = json.loads(matar_sessao_oracle(sid=10, serial=20, inst_id=inst_invalido, **KW_V2))
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
    assert len(registros) == 1
    assert registros[0]["decisao"] == "APROVADO"
    assert registros[0]["motivo"] is None


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
    assert len(registros) == 2
    aprovado, rejeitado = registros
    for reg in registros:
        assert "decisao" in reg and "resultado_banco" in reg
        assert "status_banco" not in reg

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
    assert isolar_log_aprovacao != real
    assert not isolar_log_aprovacao.exists()

    registrar_log_aprovacao_kill("dba_teste", "REJEITADO", "hash-fake", {"sid": 1}, motivo="TESTE")

    assert isolar_log_aprovacao.exists()
    registro = json.loads(isolar_log_aprovacao.read_text(encoding="utf-8").splitlines()[0])
    assert registro["aprovador"] == "dba_teste"


# =============================================================================
# A3. ITEM 6 (PKG v2) — IDENTIDADE E REFERÊNCIA OBRIGATÓRIAS (SEM CONEXÃO, FAKES)
# =============================================================================

from tests.fakes_oracle import BINDS_KILL_V2, LOGON_TIME_FAKE, assert_kill_binds  # noqa: E402

_RE_HEX32 = re.compile(r"[0-9a-f]{32}")
_ARGS_LINHA = (1, 101, 202, "APP_USER", "app.exe", "srv-app01", LOGON_TIME_FAKE)


def _ultimo_registro(log):
    return json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1])


def test_kill_chamada_nomeada_nove_formais(monkeypatch, tmp_path, ambiente_fake):
    """Fluxo APROVADO: 1 chamada ao PKG com 9 associações nome => :nome, sem argumento posicional."""
    linha = _linha_alvo()
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([linha, linha], status_pkg="ENCERRADA"))
    log = tmp_path / "kill.log"

    desfecho = conduzir_kill_hitl(
        dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=log
    )
    assert desfecho["executado"] is True

    ref = _ultimo_registro(log)["id_intervencao"]
    assert _RE_HEX32.fullmatch(ref)
    # O LLM não vê o id: ausente do resultado_tool (chave e valor)
    assert "id_intervencao" not in json.loads(desfecho["resultado_tool"])
    assert ref not in desfecho["resultado_tool"]

    binds = assert_kill_binds(oracle_fake, *_ARGS_LINHA, ref_aprovacao=ref)
    assert set(binds) == set(BINDS_KILL_V2)

    sql = next(s for conta, s, _ in oracle_fake.sql_executado if conta == "KILL")
    for formal in BINDS_KILL_V2:
        assert re.search(rf"\b{formal}\s*=>\s*:{formal}\b", sql), f"falta {formal} => :{formal}"
    corpo = sql[sql.index("KILL_SESSION") + len("KILL_SESSION"):]
    argumentos = corpo[corpo.index("(") + 1:corpo.rindex(")")].split(",")
    assert len(argumentos) == 9
    assert all("=>" in a for a in argumentos), "nenhum argumento posicional é permitido"


@pytest.mark.parametrize(
    "status_pkg, erro_kill",
    [
        ("ENCERRADA", None),
        ("ALVO_DIVERGENTE", None),
        (None, oracledb.DatabaseError("ORA-00600: erro interno simulado")),
    ],
    ids=["encerrada", "alvo_divergente", "execute_levanta_erro"],
)
def test_kill_ponto_unico_de_chamada(monkeypatch, tmp_path, ambiente_fake, status_pkg, erro_kill):
    """Qualquer desfecho do PKG: exatamente 1 conexão e 1 execute na conta KILL, sem nova tentativa."""
    linha = _linha_alvo()
    oracle_fake = _instalar_oracle(
        monkeypatch, _OracleFake([linha, linha], status_pkg=status_pkg, erro_kill=erro_kill)
    )
    conduzir_kill_hitl(
        dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=tmp_path / "kill.log"
    )
    assert oracle_fake.conexoes_kill == [USER_KILL_FAKE]
    assert_kill_binds(oracle_fake, *_ARGS_LINHA)


def test_kill_pls00306_vira_erro_oracle(monkeypatch, tmp_path, ambiente_fake):
    """
    PLS-00306 levantado pelo execute da conta KILL -> ERRO_ORACLE, 1 execute, sem nova tentativa.
    Prova só o lado Python (fake). Que o banco v1 de fato devolve PLS-00306 para a chamada v2
    só é provado no sandbox (test_sandbox_python_v2_contra_pkg_v1).
    """
    erro = oracledb.DatabaseError(
        "ORA-06550: line 2, column 5:\nPLS-00306: wrong number or types of arguments in call to 'KILL_SESSION'"
    )
    linha = _linha_alvo()
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([linha, linha], erro_kill=erro))
    log = tmp_path / "kill.log"

    desfecho = conduzir_kill_hitl(
        dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=log
    )

    assert len([1 for conta, _, _ in oracle_fake.sql_executado if conta == "KILL"]) == 1
    assert oracle_fake.conexoes_kill == [USER_KILL_FAKE]
    assert desfecho["resultado_banco"] == "ERRO_ORACLE"
    assert desfecho["executado"] is False
    assert len(ambiente_fake) == 1
    assert "NÃO executada" in ambiente_fake[0]["assunto"]
    assert "Aprovada" not in ambiente_fake[0]["assunto"]
    reg = _ultimo_registro(log)
    assert reg["resultado_banco"] == "ERRO_ORACLE"
    assert _RE_HEX32.fullmatch(reg["id_intervencao"])


def _ident(**mudancas):
    base = dict(IDENT_VALIDA)
    base.update(mudancas)
    return base


def _sem(chave):
    base = dict(IDENT_VALIDA)
    del base[chave]
    return base


_INVALIDOS_IDENTIDADE = [
    pytest.param(None, REF_VALIDA, id="identidade_none"),
    pytest.param({}, REF_VALIDA, id="identidade_vazia"),
    pytest.param(_sem("username"), REF_VALIDA, id="sem_username"),
    pytest.param(_ident(username="  "), REF_VALIDA, id="username_branco"),
    pytest.param(_sem("program"), REF_VALIDA, id="sem_chave_program"),
    pytest.param(_sem("machine"), REF_VALIDA, id="sem_chave_machine"),
    pytest.param(_ident(program=123), REF_VALIDA, id="program_int"),
    pytest.param(_ident(logon_time=None), REF_VALIDA, id="logon_time_none"),
    pytest.param(_ident(logon_time="2026-11-17T08:00:00"), REF_VALIDA, id="logon_time_str"),
    pytest.param(IDENT_VALIDA, None, id="ref_none"),
    pytest.param(IDENT_VALIDA, REF_VALIDA.upper(), id="ref_maiusculo"),
    pytest.param(IDENT_VALIDA, REF_VALIDA[:31], id="ref_31"),
    pytest.param(IDENT_VALIDA, REF_VALIDA + "a", id="ref_33"),
]

_CHAVES_KILL = {"ORACLE_USER_KILL", "ORACLE_PASSWORD_KILL", "ORACLE_DSN"}


def _espiar_getenv(monkeypatch):
    """Registra as chaves lidas por os.getenv e repassa ao original."""
    chaves = []
    original = os.getenv

    def espiao(chave, *args, **kwargs):
        chaves.append(chave)
        return original(chave, *args, **kwargs)

    monkeypatch.setattr(os, "getenv", espiao)
    return chaves


@pytest.mark.parametrize("identidade, ref", _INVALIDOS_IDENTIDADE)
def test_identidade_obrigatoria_param_invalido(monkeypatch, identidade, ref):
    """Identidade ou ref inválidas -> PARAM_INVALIDO, sem connect e sem ler as chaves ORACLE_*_KILL/DSN."""
    def fail_connect(*args, **kwargs):
        pytest.fail("oracledb.connect não deve ser chamado com identidade/ref inválidas")

    monkeypatch.setattr(oracledb, "connect", fail_connect)
    chaves = _espiar_getenv(monkeypatch)

    res = json.loads(
        matar_sessao_oracle(sid=10, serial=20, inst_id=1, identidade_esperada=identidade, ref_aprovacao=ref)
    )
    assert res["motivo"] == "PARAM_INVALIDO"
    assert res["status_banco"] == "PARAM_INVALIDO"
    assert not (_CHAVES_KILL & set(chaves)), f"getenv indevido: {chaves}"


def test_identidade_valida_com_program_e_machine_none_passa_da_validacao(monkeypatch):
    """program=None e machine=None são válidos: a validação passa e a execução chega ao getenv (ERRO_CONFIG)."""
    def fail_connect(*args, **kwargs):
        pytest.fail("sem credenciais não deve haver connect")

    monkeypatch.setattr(oracledb, "connect", fail_connect)
    monkeypatch.delenv("ORACLE_USER_KILL", raising=False)
    chaves = _espiar_getenv(monkeypatch)

    res = json.loads(
        matar_sessao_oracle(
            sid=10, serial=20, inst_id=1,
            identidade_esperada=_ident(program=None, machine=None), ref_aprovacao=REF_VALIDA,
        )
    )
    assert res["motivo"] == "ERRO_CONFIG"
    assert "ORACLE_USER_KILL" in chaves


def test_assinatura_kill_identidade_keyword_only_sem_default():
    """identidade_esperada e ref_aprovacao são KEYWORD_ONLY sem default; omitir qualquer um -> TypeError."""
    params = inspect.signature(matar_sessao_oracle).parameters
    for nome in ("identidade_esperada", "ref_aprovacao"):
        assert params[nome].kind is inspect.Parameter.KEYWORD_ONLY
        assert params[nome].default is inspect.Parameter.empty

    with pytest.raises(TypeError):
        matar_sessao_oracle(sid=10, serial=20, inst_id=1, ref_aprovacao=REF_VALIDA)
    with pytest.raises(TypeError):
        matar_sessao_oracle(sid=10, serial=20, inst_id=1, identidade_esperada=IDENT_VALIDA)


def test_logon_time_diferente_vira_alvo_alterado(monkeypatch, tmp_path, ambiente_fake):
    """logon_time muda entre pré-consulta e reconsulta (resto igual) -> ALVO_ALTERADO, 0 conexão KILL."""
    aprovada = _linha_alvo(logon_time=datetime(2026, 11, 17, 8, 0, 0))
    reconsulta = _linha_alvo(logon_time=datetime(2026, 11, 17, 9, 30, 0))
    oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([aprovada, reconsulta], kill_permitido=False))

    desfecho = conduzir_kill_hitl(
        dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=tmp_path / "kill.log"
    )
    assert desfecho["resultado_banco"] == "ALVO_ALTERADO"
    assert desfecho["executado"] is False
    assert oracle_fake.conexoes_kill == []


def test_alvo_divergente_nao_executado(monkeypatch, tmp_path, ambiente_fake):
    """PKG devolve ALVO_DIVERGENTE -> executado False; e-mail e mensagem dizem 'NÃO executada'."""
    linha = _linha_alvo()
    _instalar_oracle(monkeypatch, _OracleFake([linha, linha], status_pkg="ALVO_DIVERGENTE"))

    desfecho = conduzir_kill_hitl(
        dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=tmp_path / "kill.log"
    )
    assert desfecho["resultado_banco"] == "ALVO_DIVERGENTE"
    assert desfecho["executado"] is False
    assert len(ambiente_fake) == 1
    assert "NÃO executada" in ambiente_fake[0]["assunto"]
    assert "Aprovada" not in ambiente_fake[0]["assunto"]
    assert "ALVO_DIVERGENTE" in ambiente_fake[0]["corpo"]
    assert json.loads(desfecho["resultado_tool"])["executado"] is False


def test_hash_inclui_logon_time():
    """logon_time entra no hash; datetime é normalizado (mesmo instante -> mesmo hash)."""
    base = dict(zip([c.lower() for c in COLUNAS_ALVO], _linha_alvo()))
    outro = dict(base, logon_time=datetime(2026, 11, 17, 8, 0, 1))
    mesmo_instante = dict(base, logon_time=datetime(2026, 11, 17, 8, 0, 0))

    assert calcular_hash_identidade(base) != calcular_hash_identidade(outro)
    assert calcular_hash_identidade(base) == calcular_hash_identidade(mesmo_instante)
    assert "logon_time" in oracle_dba.CAMPOS_IDENTIDADE_ALVO


# =============================================================================
# B. TESTES EM AMBIENTE DE SANDBOX (REQUER ORACLE_SANDBOX=1)
# =============================================================================
# PKG v2 (item 6): a versão instalada no banco é decisão aprovada do operador, informada em
# OPS_KILL_PKG_VERSAO=1|2. Cada teste pula quando a versão não bate. Alvos são sessões
# descartáveis de STARTUP_DIAG (nunca SYS, background ou terceiros). Só ORACLE_USER_DIAG,
# ORACLE_USER_KILL e ORACLE_USER_MUT (nunca ORACLE_USER).
#
# Contagem de OPS_KILL_AUDIT: nenhuma conta documentada no repositório tem leitura dessa
# tabela; por isso estes testes NÃO a contam. Conferência manual (linhas novas, ref_aprovacao e
# campos_divergentes) fica a cargo do operador com a conta dona do esquema.

BLOCO_KILL_V2 = """
BEGIN
    OPS_OWNER.PKG_OPS_KILL.KILL_SESSION(
        p_inst_id             => :p_inst_id,
        p_sid                 => :p_sid,
        p_serial              => :p_serial,
        p_username_esperado   => :p_username_esperado,
        p_program_esperado    => :p_program_esperado,
        p_machine_esperado    => :p_machine_esperado,
        p_logon_time_esperado => :p_logon_time_esperado,
        p_ref_aprovacao       => :p_ref_aprovacao,
        p_status              => :p_status
    );
END;
"""

# Bloco literal da assinatura v1 (4 argumentos), para provar que o PKG v2 o rejeita.
BLOCO_KILL_V1 = """
BEGIN
    OPS_OWNER.PKG_OPS_KILL.KILL_SESSION(
        p_inst_id => :p_inst_id,
        p_sid     => :p_sid,
        p_serial  => :p_serial,
        p_status  => :p_status
    );
END;
"""


def _exigir_versao_pkg(versao):
    """Pula o teste quando a versão do PKG informada pelo operador (OPS_KILL_PKG_VERSAO) não bate."""
    atual = os.getenv("OPS_KILL_PKG_VERSAO")
    if atual != versao:
        pytest.skip(f"requer OPS_KILL_PKG_VERSAO={versao} (atual: {atual!r})")


def _conectar(sufixo):
    return oracledb.connect(
        user=os.getenv(f"ORACLE_USER_{sufixo}"),
        password=os.getenv(f"ORACLE_PASSWORD_{sufixo}"),
        dsn=os.getenv("ORACLE_DSN"),
    )


def _ler_identidade_propria(conn):
    """Lê da GV$SESSION, pela própria sessão da conexão, (inst_id, sid, serial, identidade)."""
    cur = conn.cursor()
    cur.execute("SELECT SYS_CONTEXT('USERENV', 'SID'), SYS_CONTEXT('USERENV', 'INSTANCE') FROM DUAL")
    row = cur.fetchone()
    sid, inst = int(row[0]), int(row[1])
    cur.execute(
        "SELECT serial#, username, program, machine, logon_time FROM GV$SESSION "
        "WHERE inst_id = :inst AND sid = :sid",
        inst=inst, sid=sid,
    )
    serial, username, program, machine, logon_time = cur.fetchone()
    cur.close()
    identidade = {"username": username, "program": program, "machine": machine, "logon_time": logon_time}
    return inst, sid, int(serial), identidade


def _abrir_alvo_descartavel():
    """Abre sessão descartável de STARTUP_DIAG (alvo). Devolve (conexao, inst, sid, serial, identidade)."""
    conn = _conectar("DIAG")
    inst, sid, serial, identidade = _ler_identidade_propria(conn)
    return conn, inst, sid, serial, identidade


def _sessao_viva(inst, sid, serial):
    """Confere pela conta DIAG (conexão própria) se a sessão ainda existe na GV$SESSION."""
    conn = _conectar("DIAG")
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM GV$SESSION WHERE inst_id = :i AND sid = :s AND serial# = :r",
            i=inst, s=sid, r=serial,
        )
        return cur.fetchone()[0] == 1
    finally:
        conn.close()


def _fechar(conn):
    try:
        conn.close()
    except Exception:
        pass


def _chamar_pkg_v2_na_conta_kill(inst, sid, serial, identidade, ref):
    """
    Chama o PKG v2 por bloco próprio na conta KILL, para enviar valores que a validação local
    de matar_sessao_oracle recusaria (ref maiúsculo, texto > 128 bytes) e provar a checagem do banco.
    """
    conn = _conectar("KILL")
    try:
        cur = conn.cursor()
        status = cur.var(oracledb.DB_TYPE_VARCHAR, size=128)
        cur.execute(
            BLOCO_KILL_V2,
            p_inst_id=inst, p_sid=sid, p_serial=serial,
            p_username_esperado=identidade["username"],
            p_program_esperado=identidade["program"],
            p_machine_esperado=identidade["machine"],
            p_logon_time_esperado=identidade["logon_time"],
            p_ref_aprovacao=ref,
            p_status=status,
        )
        return str(status.getvalue() or "").strip()
    finally:
        conn.close()


@pytest.mark.sandbox_only
def test_sandbox_kill_sessao_valida_encerrada():
    """PKG v2 com identidade real da sessão alvo (STARTUP_DIAG) retorna ENCERRADA."""
    _exigir_versao_pkg("2")
    conn_alvo, inst, sid, serial, identidade = _abrir_alvo_descartavel()
    try:
        res = json.loads(
            matar_sessao_oracle(
                sid=sid, serial=serial, inst_id=inst,
                identidade_esperada=identidade, ref_aprovacao=uuid.uuid4().hex,
            )
        )
        assert res.get("status_banco") in ("ENCERRADA", "MARCADA_PARA_KILL"), f"Esperado ENCERRADA, obtido: {res}"
    finally:
        _fechar(conn_alvo)


@pytest.mark.sandbox_only
def test_sandbox_kill_alvo_nao_encontrado():
    """PKG v2: SID 999999 / serial 1 retorna ALVO_NAO_ENCONTRADO (identidade bem formada, ref válido)."""
    _exigir_versao_pkg("2")
    res = json.loads(
        matar_sessao_oracle(
            sid=999999, serial=1, inst_id=1,
            identidade_esperada=IDENT_VALIDA, ref_aprovacao=uuid.uuid4().hex,
        )
    )
    assert res.get("status_banco") == "ALVO_NAO_ENCONTRADO"


@pytest.mark.sandbox_only
def test_sandbox_kill_param_invalido():
    """PKG v2: SID -1 retorna PARAM_INVALIDO (barreira local, antes de qualquer conexão)."""
    _exigir_versao_pkg("2")
    res = json.loads(
        matar_sessao_oracle(
            sid=-1, serial=1, inst_id=1,
            identidade_esperada=IDENT_VALIDA, ref_aprovacao=uuid.uuid4().hex,
        )
    )
    assert res.get("status_banco") == "PARAM_INVALIDO"


@pytest.mark.sandbox_only
def test_sandbox_kill_propria_sessao_ou_usuario_protegido():
    """PKG v2: tentar matar sessão STARTUPADMIN (identidade real dela) retorna USUARIO_PROTEGIDO."""
    _exigir_versao_pkg("2")
    conn = _conectar("MUT")
    try:
        inst, sid, serial, identidade = _ler_identidade_propria(conn)
        res = json.loads(
            matar_sessao_oracle(
                sid=sid, serial=serial, inst_id=inst,
                identidade_esperada=identidade, ref_aprovacao=uuid.uuid4().hex,
            )
        )
    finally:
        _fechar(conn)
    assert res.get("status_banco") in ("USUARIO_PROTEGIDO", "PROPRIA_SESSAO"), f"Esperado USUARIO_PROTEGIDO, obtido: {res}"


@pytest.mark.sandbox_only
def test_sandbox_python_v2_contra_pkg_v1():
    """Python v2 x PKG v1: chamada de 9 formais falha na compilação (PLS-00306); ERRO_ORACLE e alvo vivo."""
    _exigir_versao_pkg("1")
    conn_alvo, inst, sid, serial, identidade = _abrir_alvo_descartavel()
    try:
        res = json.loads(
            matar_sessao_oracle(
                sid=sid, serial=serial, inst_id=inst,
                identidade_esperada=identidade, ref_aprovacao=uuid.uuid4().hex,
            )
        )
        assert res.get("status_banco") == "ERRO_ORACLE", res
        assert "PLS-00306" in res.get("mensagem", ""), res
        assert _sessao_viva(inst, sid, serial), "o alvo não pode ser encerrado"
    finally:
        _fechar(conn_alvo)


@pytest.mark.sandbox_only
def test_sandbox_bloco_v1_literal_contra_pkg_v2():
    """Bloco v1 (4 argumentos) x PKG v2, conta KILL: PLS-00306 e alvo vivo."""
    _exigir_versao_pkg("2")
    conn_alvo, inst, sid, serial, _ = _abrir_alvo_descartavel()
    conn_kill = _conectar("KILL")
    try:
        cur = conn_kill.cursor()
        status = cur.var(oracledb.DB_TYPE_VARCHAR, size=128)
        with pytest.raises(oracledb.DatabaseError) as exc_info:
            cur.execute(BLOCO_KILL_V1, p_inst_id=inst, p_sid=sid, p_serial=serial, p_status=status)
        assert "PLS-00306" in str(exc_info.value)
        assert _sessao_viva(inst, sid, serial), "o alvo não pode ser encerrado"
    finally:
        _fechar(conn_kill)
        _fechar(conn_alvo)


@pytest.mark.sandbox_only
def test_sandbox_program_errado_alvo_divergente():
    """PKG v2 com program errado -> ALVO_DIVERGENTE e alvo vivo."""
    _exigir_versao_pkg("2")
    conn_alvo, inst, sid, serial, identidade = _abrir_alvo_descartavel()
    try:
        errada = dict(identidade, program="programa_errado_xyz.exe")
        res = json.loads(
            matar_sessao_oracle(
                sid=sid, serial=serial, inst_id=inst,
                identidade_esperada=errada, ref_aprovacao=uuid.uuid4().hex,
            )
        )
        assert res.get("status_banco") == "ALVO_DIVERGENTE", res
        assert _sessao_viva(inst, sid, serial)
    finally:
        _fechar(conn_alvo)


@pytest.mark.sandbox_only
def test_sandbox_logon_time_errado_alvo_divergente():
    """PKG v2 com logon_time errado -> ALVO_DIVERGENTE e alvo vivo."""
    _exigir_versao_pkg("2")
    conn_alvo, inst, sid, serial, identidade = _abrir_alvo_descartavel()
    try:
        errada = dict(identidade, logon_time=identidade["logon_time"] - timedelta(days=1))
        res = json.loads(
            matar_sessao_oracle(
                sid=sid, serial=serial, inst_id=inst,
                identidade_esperada=errada, ref_aprovacao=uuid.uuid4().hex,
            )
        )
        assert res.get("status_banco") == "ALVO_DIVERGENTE", res
        assert _sessao_viva(inst, sid, serial)
    finally:
        _fechar(conn_alvo)


# Caso "program só com caixa diferente sob NLS_COMP=LINGUISTIC / NLS_SORT=BINARY_CI -> ALVO_DIVERGENTE"
# (implantacao.md seção 5): NÃO automatizado aqui, porque exige SQL de sessão (NLS) e o CLAUDE.md proíbe
# SQL de sessão no Python. Conferência manual do operador no sandbox (SQL*Plus, conta KILL).


@pytest.mark.sandbox_only
@pytest.mark.parametrize("caso", ["ref_maiusculo", "texto_acima_128_bytes"])
def test_sandbox_pkg_param_invalido_ref_e_texto(caso):
    """Direto no PKG v2: ref em hexadecimal maiúsculo ou texto esperado > 128 bytes -> PARAM_INVALIDO."""
    _exigir_versao_pkg("2")
    conn_alvo, inst, sid, serial, identidade = _abrir_alvo_descartavel()
    try:
        ref = uuid.uuid4().hex
        if caso == "ref_maiusculo":
            ref = ref.upper()
        else:
            identidade = dict(identidade, program="x" * 129)
        status = _chamar_pkg_v2_na_conta_kill(inst, sid, serial, identidade, ref)
        assert status == "PARAM_INVALIDO"
        assert _sessao_viva(inst, sid, serial)
    finally:
        _fechar(conn_alvo)


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
