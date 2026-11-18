"""
Smoke tests do fluxo HITL na interface Web (app.py) com streamlit.testing.v1.AppTest.

Sem conexão: LLM, Oracle, SMTP, rede e .env neutralizados via monkeypatch (desfeitos ao fim).
Patches de oracle_dba miram `tools.oracle_dba` (cópia carregada por app.py), não `src.tools.oracle_dba`.
"""
import json
import logging
import os
import re
import socket
import types
from pathlib import Path

import pytest

from tests.fakes_oracle import USER_DIAG_FAKE, USER_KILL_FAKE, _linha_alvo, _OracleFake

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app.py"
LOGS_REAIS = (
    RAIZ / "data" / "logs" / "kill_approval.log",
    RAIZ / "auditoria_oracle.log",
    RAIZ / "data" / "logs" / "auditoria_oracle.log",
)
PEDIDO = "mate a sessão inst_id 1 sid 101 serial 202"
ARGS_KILL = {"inst_id": 1, "sid": 101, "serial": 202}


def _snapshot_logs_reais():
    """(existe, tamanho, mtime_ns) por stat; o conteúdo nunca é lido."""
    out = {}
    for p in LOGS_REAIS:
        try:
            st = p.stat()
            out[str(p)] = (True, st.st_size, st.st_mtime_ns)
        except FileNotFoundError:
            out[str(p)] = (False, None, None)
    return out


class _Fn:
    def __init__(self, nome, argumentos):
        self.name = nome
        self.arguments = argumentos


class _ToolCall:
    id = "call_1"
    type = "function"

    def __init__(self):
        self.function = _Fn("matar_sessao_oracle", json.dumps(ARGS_KILL))


class _Msg:
    def __init__(self, com_tool_call):
        self.content = None if com_tool_call else "Laudo final fake."
        self.tool_calls = [_ToolCall()] if com_tool_call else None


class _Resp:
    def __init__(self, com_tool_call):
        self.choices = [types.SimpleNamespace(message=_Msg(com_tool_call))]


class _Ambiente:
    """Estado compartilhado do cenário: fake Oracle, e-mails, chamadas ao LLM falso e log de aprovação."""

    def __init__(self, oracle_fake, log_aprovacao):
        self.oracle = oracle_fake
        self.log_aprovacao = log_aprovacao
        self.emails = []
        self.mensagens_llm = []  # snapshot (cópia) das mensagens recebidas em cada chamada
        self.at = None

    def registros(self):
        if not self.log_aprovacao.exists():
            return []
        linhas = self.log_aprovacao.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(x) for x in linhas]

    def par_intencao_resultado(self):
        """APROVADO grava 2 linhas (decisão 1): INTENCAO (resultado_banco None) e RESULTADO, mesmo id."""
        regs = self.registros()
        assert len(regs) == 2
        intencao, resultado = regs
        assert intencao["fase"] == "INTENCAO" and intencao["decisao"] == "APROVADO"
        assert intencao["resultado_banco"] is None
        assert resultado["fase"] == "RESULTADO"
        assert intencao["id_intervencao"] == resultado["id_intervencao"]
        assert re.fullmatch(r"[0-9a-f]{32}", resultado["id_intervencao"])
        return resultado

    def json_devolvido_ao_llm(self):
        """Conteúdo (JSON) da mensagem `tool` vista pelo LLM na chamada de fechamento (a última)."""
        tools = [m for m in self.mensagens_llm[-1] if m.get("role") == "tool"]
        return json.loads(tools[-1]["content"])

    def textos_tela(self):
        return [m.value for m in self.at.markdown]

    def avisos(self):
        return [w.value for w in self.at.warning]


@pytest.fixture
def snapshot_logs_reais():
    """Os logs reais não podem mudar (stat antes/depois) por causa do teste."""
    antes = _snapshot_logs_reais()
    yield
    assert _snapshot_logs_reais() == antes, "Log real alterado pelo teste Web"


def _montar(monkeypatch, tmp_path, linhas_diag, status_pkg=None, kill_permitido=True):
    monkeypatch.syspath_prepend(str(RAIZ / "src"))
    monkeypatch.syspath_prepend(str(RAIZ))
    monkeypatch.setenv("ORACLE_USER_DIAG", USER_DIAG_FAKE)
    monkeypatch.setenv("ORACLE_PASSWORD_DIAG", "senha-fake")
    monkeypatch.setenv("ORACLE_USER_KILL", USER_KILL_FAKE)
    monkeypatch.setenv("ORACLE_PASSWORD_KILL", "senha-fake")
    monkeypatch.setenv("ORACLE_DSN", "host-teste:1521/TESTE")
    monkeypatch.setenv("EMAIL_DESTINATARIO", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    # app.py chama load_dotenv(ROOT/".env"): proibido ler o .env
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)

    # logging.basicConfig vira no-op (já existe handler na raiz) e não cria FileHandler real
    raiz_log = logging.getLogger()
    null = logging.NullHandler()
    raiz_log.addHandler(null)

    # Rede: Ollama (11434) offline; qualquer outro destino é erro
    destinos_inesperados = []

    def _create_connection(endereco, *a, **k):
        if isinstance(endereco, tuple) and endereco[1] == 11434:
            raise OSError("neutralizado no teste")
        destinos_inesperados.append(endereco)
        raise AssertionError(f"rede inesperada: {endereco}")

    monkeypatch.setattr(socket, "create_connection", _create_connection)

    import oracledb
    import openai
    import tools.oracle_dba as od  # cópia usada por app.py

    log_aprovacao = tmp_path / "kill_approval_web.log"
    monkeypatch.setattr(od, "CAMINHO_LOG_APROVACAO_PADRAO", log_aprovacao)  # app.py não passa caminho_log
    monkeypatch.setattr(
        od,
        "verificar_acessibilidade_host",
        lambda dsn, timeout=3.0: {"acessivel": True, "host": "host-teste", "porta": 1521, "latencia_ms": 1},
    )
    monkeypatch.setattr(od, "coletar_sessoes_ativas", lambda *a, **k: json.dumps({"sessoes_ativas": 0, "sessoes_identificadas": []}))
    monkeypatch.setattr(od, "coletar_top_sql", lambda *a, **k: json.dumps({"top_sql": []}))

    fake = _OracleFake(linhas_diag, status_pkg=status_pkg, kill_permitido=kill_permitido)
    monkeypatch.setattr(oracledb, "connect", fake.connect)
    amb = _Ambiente(fake, log_aprovacao)

    def _email(assunto, corpo):
        amb.emails.append({"assunto": assunto, "corpo": corpo})
        return True, "capturado"

    monkeypatch.setattr(od, "enviar_alerta_email", _email)

    class _Completions:
        def create(self, **kwargs):
            amb.mensagens_llm.append([dict(m) for m in kwargs["messages"]])
            return _Resp(len(amb.mensagens_llm) == 1)

    class _OpenAIFalso:
        def __init__(self, *a, **k):
            self.chat = types.SimpleNamespace(completions=_Completions())

    monkeypatch.setattr(openai, "OpenAI", _OpenAIFalso)

    from streamlit.testing.v1 import AppTest

    amb.at = AppTest.from_file(str(APP), default_timeout=30)
    amb.destinos_inesperados = destinos_inesperados
    amb._null = null
    return amb


@pytest.fixture
def montar_web(monkeypatch, tmp_path, snapshot_logs_reais):
    """Fábrica de cenários; remove o NullHandler da raiz ao fim."""
    criados = []

    def _fabrica(linhas_diag, status_pkg=None, kill_permitido=True):
        amb = _montar(monkeypatch, tmp_path, linhas_diag, status_pkg, kill_permitido)
        criados.append(amb)
        return amb

    yield _fabrica
    for amb in criados:
        logging.getLogger().removeHandler(amb._null)
        assert amb.destinos_inesperados == []


def _ate_painel_hitl(amb):
    """at.run() -> pedido no chat -> painel HITL presente."""
    at = amb.at
    at.run()
    assert not at.exception
    at.chat_input[0].set_value(PEDIDO).run()
    assert not at.exception
    assert at.session_state.hitl_pendente is not None
    assert [w.key for w in at.text_input] == ["input_hitl_aprovador"]
    assert {b.key for b in at.button} >= {"btn_hitl_approve", "btn_hitl_abort"}
    assert len(amb.mensagens_llm) == 1  # 1ª chamada (tool_call); ainda sem fechamento


def _decidir(amb, botao, aprovador=None):
    at = amb.at
    if aprovador is not None:
        at.text_input(key="input_hitl_aprovador").input(aprovador)
    at.button(key=botao).click().run()
    assert not at.exception


def _painel_ausente(at):
    chaves = {w.key for w in at.text_input} | {b.key for b in at.button}
    return not ({"input_hitl_aprovador", "btn_hitl_approve", "btn_hitl_abort"} & chaves)


def test_web_painel_fecha_apos_aprovar(montar_web):
    """F1: processar_decisao_hitl devolve True -> st.rerun() dispara; painel some sem run() extra."""
    linha = _linha_alvo()
    amb = montar_web([linha, linha], status_pkg="ENCERRADA")
    _ate_painel_hitl(amb)

    _decidir(amb, "btn_hitl_approve", "dba_teste")

    assert amb.at.session_state.hitl_pendente is None
    assert _painel_ausente(amb.at)


def test_web_aprovado_encerrada(montar_web):
    linha = _linha_alvo()
    amb = montar_web([linha, linha], status_pkg="ENCERRADA")
    _ate_painel_hitl(amb)
    _decidir(amb, "btn_hitl_approve", "dba_teste")

    assert amb.oracle.conexoes.count(USER_DIAG_FAKE) == 2
    assert amb.oracle.conexoes_kill == [USER_KILL_FAKE]
    assert any("PKG_OPS_KILL.KILL_SESSION" in sql for conta, sql, _ in amb.oracle.sql_executado if conta == "KILL")

    assert len(amb.emails) == 1
    assert "Intervenção Aprovada" in amb.emails[0]["assunto"]

    reg = amb.par_intencao_resultado()
    assert reg["decisao"] == "APROVADO"
    assert reg["resultado_banco"] == "ENCERRADA"
    assert reg["aprovador"] == "dba_teste"

    assert any("executada com sucesso" in t for t in amb.textos_tela())
    assert any("executada com sucesso" in m["content"] for m in amb.at.session_state.messages)
    assert len(amb.mensagens_llm) == 2
    devolvido = amb.json_devolvido_ao_llm()
    assert devolvido["decisao"] == "APROVADO"
    assert devolvido["executado"] is True
    assert devolvido["resultado_banco"] == "ENCERRADA"
    assert amb.at.session_state.hitl_pendente is None


def test_web_aprovado_nao_usuario(montar_web):
    linha = _linha_alvo()
    amb = montar_web([linha, linha], status_pkg="NAO_USUARIO")
    _ate_painel_hitl(amb)
    _decidir(amb, "btn_hitl_approve", "dba_teste")

    assert amb.oracle.conexoes.count(USER_DIAG_FAKE) == 2
    assert amb.oracle.conexoes_kill == [USER_KILL_FAKE]

    assert len(amb.emails) == 1
    assert "NÃO executada" in amb.emails[0]["assunto"]
    assert "Aprovada" not in amb.emails[0]["assunto"]

    reg = amb.par_intencao_resultado()
    assert reg["decisao"] == "APROVADO"
    assert reg["resultado_banco"] == "NAO_USUARIO"

    assert any("mas NÃO executada" in t for t in amb.textos_tela())
    devolvido = amb.json_devolvido_ao_llm()
    assert devolvido["decisao"] == "APROVADO"
    assert devolvido["executado"] is False
    assert devolvido["resultado_banco"] == "NAO_USUARIO"


def test_web_rejeitado(montar_web):
    amb = montar_web([_linha_alvo()], kill_permitido=False)
    _ate_painel_hitl(amb)
    _decidir(amb, "btn_hitl_abort", "dba_teste")

    assert amb.oracle.conexoes.count(USER_DIAG_FAKE) == 1
    assert amb.oracle.conexoes_kill == []
    assert amb.emails == []

    (reg,) = amb.registros()
    assert reg["decisao"] == "REJEITADO"
    assert reg["resultado_banco"] is None
    assert reg["motivo"] == "REJEITADO_PELO_APROVADOR"

    assert any("Ação Abortada" in t and "negado" in t for t in amb.textos_tela())
    devolvido = amb.json_devolvido_ao_llm()
    assert devolvido["decisao"] == "REJEITADO"
    assert devolvido["executado"] is False
    assert amb.at.session_state.hitl_pendente is None


def test_web_aprovador_vazio(montar_web):
    """Aprovar sem identificação: st.warning, nada gravado, painel permanece, 0 KILL."""
    amb = montar_web([_linha_alvo()], kill_permitido=False)
    _ate_painel_hitl(amb)
    _decidir(amb, "btn_hitl_approve")  # campo vazio

    assert any("Informe a identificação do aprovador" in w for w in amb.avisos())
    assert amb.registros() == []
    assert not amb.log_aprovacao.exists()
    assert amb.emails == []
    assert amb.oracle.conexoes.count(USER_DIAG_FAKE) == 1
    assert amb.oracle.conexoes_kill == []
    assert amb.at.session_state.hitl_pendente is not None
    assert not _painel_ausente(amb.at)
    assert len(amb.mensagens_llm) == 1  # nenhuma devolução ao LLM


def test_web_alvo_alterado(montar_web):
    amb = montar_web(
        [_linha_alvo(program="app.exe"), _linha_alvo(program="outro_programa.exe")], kill_permitido=False
    )
    _ate_painel_hitl(amb)
    _decidir(amb, "btn_hitl_approve", "dba_teste")

    assert amb.oracle.conexoes.count(USER_DIAG_FAKE) == 2
    assert amb.oracle.conexoes_kill == []

    assert len(amb.emails) == 1
    assert "NÃO executada" in amb.emails[0]["assunto"]

    reg = amb.par_intencao_resultado()
    assert reg["decisao"] == "APROVADO"
    assert reg["resultado_banco"] == "ALVO_ALTERADO"

    assert any("mas NÃO executada" in t for t in amb.textos_tela())
    devolvido = amb.json_devolvido_ao_llm()
    assert devolvido["decisao"] == "APROVADO"
    assert devolvido["executado"] is False
    assert devolvido["resultado_banco"] == "ALVO_ALTERADO"


# ---------------------------------------------------------------------------
# Item 1 (1c, T13, T14, reconciliador): mensagens e pendência na Web
# ---------------------------------------------------------------------------

def test_web_falha_log_aprovacao(montar_web, monkeypatch):
    """T13: falha do log na INTENCAO -> st.error 'NÃO EXECUTADA', 0 KILL, 0 e-mail, pendência limpa, painel ausente."""
    amb = montar_web([_linha_alvo()], kill_permitido=False)
    _ate_painel_hitl(amb)

    def _fsync_falha(fd):
        raise OSError(5, "fsync falhou (injetado)")

    monkeypatch.setattr(os, "fsync", _fsync_falha)
    _decidir(amb, "btn_hitl_approve", "dba_teste")

    assert amb.oracle.conexoes.count(USER_DIAG_FAKE) == 1, "sem reconsulta DIAG depois da decisão"
    assert amb.oracle.conexoes_kill == []
    assert amb.emails == []
    # st.error é emitido e a página recarrega (st.rerun); o texto persiste no histórico do chat
    textos = amb.textos_tela()
    assert any("NÃO EXECUTADA" in t and "Nenhuma chamada à conta KILL" in t for t in textos)
    assert amb.at.session_state.hitl_pendente is None
    assert _painel_ausente(amb.at)
    devolvido = amb.json_devolvido_ao_llm()
    assert devolvido["motivo"] == "FALHA_LOG_APROVACAO" and devolvido["executado"] is False


def test_web_excecao_em_registrar_decisao(montar_web, monkeypatch):
    """T14 (plano 9.3): RuntimeError não quebra o app; pendência limpa; mensagem tool com estado desconhecido."""
    import tools.oracle_dba as od

    amb = montar_web([_linha_alvo()], kill_permitido=False)
    _ate_painel_hitl(amb)

    def _explode(*a, **k):
        raise RuntimeError("detalhe-interno-xyz")

    monkeypatch.setattr(od, "registrar_decisao_kill", _explode)
    _decidir(amb, "btn_hitl_approve", "dba_teste")  # _decidir já exige `not at.exception`

    assert amb.at.session_state.hitl_pendente is None
    assert _painel_ausente(amb.at)
    assert any("estado desconhecido" in t for t in amb.textos_tela())
    tools = [m for m in amb.at.session_state.llm_messages if m.get("role") == "tool"]
    assert len(tools) == 1
    conteudo = json.loads(tools[0]["content"])
    assert conteudo["executado"] is None and "estado desconhecido" in conteudo["mensagem"]
    assert "OPS_KILL_AUDIT" in conteudo["mensagem"]
    assert "detalhe-interno-xyz" not in tools[0]["content"]
    assert len(amb.mensagens_llm) == 1, "sem fechamento pelo LLM depois do erro interno"
    assert amb.oracle.conexoes_kill == [] and amb.emails == []


def test_web_clique_repetido_nao_reaproveita_pendencia(montar_web, monkeypatch):
    """1c: a pendência é limpa antes de registrar_decisao_kill, mesmo quando a chamada levanta exceção."""
    import tools.oracle_dba as od

    amb = montar_web([_linha_alvo()], kill_permitido=False)
    _ate_painel_hitl(amb)
    vistos = []

    def _espia(*a, **k):
        vistos.append(amb.at.session_state.hitl_pendente)
        raise RuntimeError("x")

    monkeypatch.setattr(od, "registrar_decisao_kill", _espia)
    _decidir(amb, "btn_hitl_approve", "dba_teste")
    assert vistos == [None]


def test_web_resultado_desconhecido(montar_web):
    """ERRO_ORACLE a partir do execute: st.error 'resultado desconhecido', e-mail e JSON ao LLM idem."""
    import oracledb

    linha = _linha_alvo()
    amb = montar_web([linha, linha], kill_permitido=True)
    amb.oracle.erro_kill = oracledb.DatabaseError("ORA-00600: interno")
    _ate_painel_hitl(amb)
    _decidir(amb, "btn_hitl_approve", "dba_teste")

    assert amb.oracle.conexoes_kill == [USER_KILL_FAKE]
    assert any("resultado desconhecido: conferir sessão" in t for t in amb.textos_tela())
    assert len(amb.emails) == 1
    assert "resultado desconhecido: conferir sessão" in amb.emails[0]["assunto"]
    assert "NÃO executada" not in amb.emails[0]["assunto"]
    devolvido = amb.json_devolvido_ao_llm()
    assert devolvido["resultado_desconhecido"] is True and devolvido["executado"] is False
    assert "resultado desconhecido: conferir sessão" in devolvido["mensagem"]


def _intencao_antiga(id_="e" * 32):
    from datetime import datetime, timedelta, timezone

    return {
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), "fase": "INTENCAO",
        "id_intervencao": id_, "aprovador": "dba", "decisao": "APROVADO", "resultado_banco": None,
        "motivo": None, "hash_payload": "h", "parametros": {"inst_id": 1, "sid": 1, "serial": 1}, "alvo": {},
    }


def test_web_reconciliador_na_subida(montar_web):
    """Uma vez por sessão: INTENCAO antiga ganha NAO_CONCLUIDA e a tela mostra st.warning com o id."""
    amb = montar_web([_linha_alvo()], kill_permitido=False)
    amb.log_aprovacao.write_text(json.dumps(_intencao_antiga()) + "\n", encoding="utf-8")

    amb.at.run()
    assert not amb.at.exception

    assert amb.at.session_state.reconciliacao_kill["reconciliadas"] == ["e" * 32]
    assert any("e" * 32 in w and "OPS_KILL_AUDIT" in w for w in amb.avisos())
    regs = amb.registros()
    assert [r["fase"] for r in regs] == ["INTENCAO", "RESULTADO"]
    assert regs[1]["resultado_banco"] == "NAO_CONCLUIDA" and regs[1]["motivo"] == "RECONCILIADO_NA_SUBIDA"

    amb.at.run()  # segunda execução do script na mesma sessão: não reconcilia de novo
    assert len(amb.registros()) == 2


def test_web_reconciliador_falha_nao_quebra_o_app(montar_web, monkeypatch):
    import tools.oracle_dba as od

    def _lock_indisponivel(*a, **k):
        raise od.LockLogAprovacaoIndisponivel("lock indisponível (injetado)")

    amb = montar_web([_linha_alvo()], kill_permitido=False)
    monkeypatch.setattr(od, "reconciliar_intencoes_orfas", _lock_indisponivel)
    amb.at.run()

    assert not amb.at.exception
    assert any("Reconciliação do log de aprovações NÃO executada" in w for w in amb.avisos())
    assert amb.at.session_state.reconciliacao_kill["erro"] == "LockLogAprovacaoIndisponivel"
