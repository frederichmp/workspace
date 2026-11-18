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
        matar_sessao_oracle(sid=10, serial=20)

    for inst_invalido in (None, True, 1.5, "1a", "", 0, -3):
        res_inv = json.loads(matar_sessao_oracle(sid=10, serial=20, inst_id=inst_invalido))
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
