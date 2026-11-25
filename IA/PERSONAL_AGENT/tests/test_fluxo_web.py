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
import sys
import types
from pathlib import Path

import pytest

from tests._guarda_env import instalar as _instalar_guarda_env
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

    def __init__(self, nome="matar_sessao_oracle", argumentos=None):
        self.function = _Fn(nome, json.dumps(ARGS_KILL if argumentos is None else argumentos))


class _Msg:
    def __init__(self, com_tool_call, chamada=None):
        self.content = None if com_tool_call else "Laudo final fake."
        self.tool_calls = [_ToolCall(*(chamada or ()))] if com_tool_call else None


class _Resp:
    def __init__(self, com_tool_call, chamada=None):
        self.choices = [types.SimpleNamespace(message=_Msg(com_tool_call, chamada))]


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


def _instalar_guarda_dotenv(mp, ficticio):
    """load_dotenv e dotenv_values viram stubs que registram a chamada; o guarda de tests/_guarda_env.py
    recusa (LeituraEnvRealBloqueada) e registra qualquer leitura de RAIZ/.env e redireciona open/io.open/os.stat
    do .env real para `ficticio` (arquivo vazio de teste).

    Devolve o registro; o teste afirma `leituras_env_reais == []` (nenhum leitor chega ao .env real) e
    `cargas >= 1` (a carga rodou; `cargas` conta as chamadas a load_dotenv, `valores` as de dotenv_values)."""
    import dotenv

    registro = _instalar_guarda_env(mp.setattr, RAIZ / ".env", ficticio)

    def _load_dotenv(*a, **k):
        registro.cargas.append({"funcao": "load_dotenv"})
        return False

    def _dotenv_values(*a, **k):
        registro.valores.append({"funcao": "dotenv_values"})
        return {}

    mp.setattr(dotenv, "load_dotenv", _load_dotenv)
    mp.setattr(dotenv, "dotenv_values", _dotenv_values)
    return registro


_AUSENTE = object()
_ATRIBUTO_ESTADO_ENV = "_personal_agent_estado_env"


def _montar(monkeypatch, tmp_path, linhas_diag, status_pkg=None, kill_permitido=True, ollama="local",
            versao_pkg="2"):
    monkeypatch.syspath_prepend(str(RAIZ / "src"))
    monkeypatch.syspath_prepend(str(RAIZ))
    monkeypatch.setenv("ORACLE_USER_DIAG", USER_DIAG_FAKE)
    monkeypatch.setenv("ORACLE_PASSWORD_DIAG", "senha-fake")
    monkeypatch.setenv("ORACLE_USER_KILL", USER_KILL_FAKE)
    monkeypatch.setenv("ORACLE_PASSWORD_KILL", "senha-fake")
    monkeypatch.setenv("ORACLE_DSN", "host-teste:1521/TESTE")
    monkeypatch.setenv("EMAIL_DESTINATARIO", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    # Fase 2 da R1 (decisao_c1.md §2.3; expectativa alterada, declarada): o kill exige OPS_KILL_PKG_VERSAO=2.
    if versao_pkg is None:
        monkeypatch.delenv("OPS_KILL_PKG_VERSAO", raising=False)
    else:
        monkeypatch.setenv("OPS_KILL_PKG_VERSAO", versao_pkg)

    # app.py chama load_dotenv(ROOT/".env"): proibido ler o .env real (stubs + guarda; open/stat vão ao fictício)
    ficticio = tmp_path / "env_ficticio_web.env"
    ficticio.write_bytes(b"")
    registro_env = _instalar_guarda_dotenv(monkeypatch, ficticio)

    # logging.basicConfig vira no-op (já existe handler na raiz) e não cria FileHandler real
    raiz_log = logging.getLogger()
    null = logging.NullHandler()
    raiz_log.addHandler(null)

    # Rede: a sonda do Ollama (11434) responde ("local") ou falha ("nuvem"), sem socket real; qualquer outro
    # destino é erro. Expectativa alterada, declarada (R1 ampliada, r1_ampliada/decisao_c1.md §8.5): o padrão
    # passa de Ollama offline para local, porque com a nuvem as ferramentas Oracle (e o kill) são recusadas
    # (decisão 5.2.1 do responsável). Os casos de nuvem são os testes W1-W6 no fim do arquivo.
    destinos_inesperados = []
    estado_rede = {"ollama": ollama}

    def _create_connection(endereco, *a, **k):
        if isinstance(endereco, tuple) and endereco[1] == 11434:
            if estado_rede["ollama"] == "local":
                import contextlib
                return contextlib.nullcontext()
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

    amb.estado_rede = estado_rede
    amb.chamada = None  # (nome, argumentos) da 1ª tool_call; None = matar_sessao_oracle com ARGS_KILL
    amb.base_url_forcado = None  # W6: cliente que diz um base_url diferente do pedido
    amb.bases_llm, amb.tools_llm = [], []

    class _Completions:
        def __init__(self, cliente):
            self.cliente = cliente

        def create(self, **kwargs):
            amb.mensagens_llm.append([dict(m) for m in kwargs["messages"]])
            amb.bases_llm.append(self.cliente.base_url)
            amb.tools_llm.append(kwargs.get("tools"))
            return _Resp(len(amb.mensagens_llm) == 1, amb.chamada)

    class _OpenAIFalso:
        def __init__(self, *a, **k):
            self.base_url = amb.base_url_forcado or k.get("base_url")
            self.chat = types.SimpleNamespace(completions=_Completions(self))

    monkeypatch.setattr(openai, "OpenAI", _OpenAIFalso)

    from streamlit.testing.v1 import AppTest

    amb.at = AppTest.from_file(str(APP), default_timeout=30)
    amb.destinos_inesperados = destinos_inesperados
    amb.leituras_env_reais = registro_env.leituras_env_reais
    amb.cargas = registro_env.cargas
    amb._null = null
    return amb


@pytest.fixture
def montar_web(monkeypatch, tmp_path, snapshot_logs_reais):
    """Fábrica de cenários; remove o NullHandler da raiz ao fim.

    Achado 2: o estado da carga do .env vive em sys; se já existir (outro teste, outra entrada), a carga
    não rodaria e o teste não provaria nada. Salvo na abertura, removido antes de cada cenário e restaurado
    EXATAMENTE no teardown (sem monkeypatch.delattr: não registra restauração sobre atributo ausente, L1)."""
    criados = []
    estado_env_antes = vars(sys).get(_ATRIBUTO_ESTADO_ENV, _AUSENTE)

    def _fabrica(linhas_diag, status_pkg=None, kill_permitido=True, ollama="local", versao_pkg="2"):
        vars(sys).pop(_ATRIBUTO_ESTADO_ENV, None)
        amb = _montar(monkeypatch, tmp_path, linhas_diag, status_pkg, kill_permitido, ollama, versao_pkg)
        criados.append(amb)
        return amb

    try:
        yield _fabrica
    finally:
        if estado_env_antes is _AUSENTE:
            vars(sys).pop(_ATRIBUTO_ESTADO_ENV, None)
        else:
            vars(sys)[_ATRIBUTO_ESTADO_ENV] = estado_env_antes
        for amb in criados:
            logging.getLogger().removeHandler(amb._null)
    for amb in criados:
        assert amb.leituras_env_reais == [], "leitura do .env real durante o teste Web"
        assert amb.destinos_inesperados == []
        assert len(amb.cargas) >= 1, "a carga do .env não rodou neste teste Web"


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


def test_web_status_pkg_vazio_e_resultado_desconhecido(montar_web):
    """K2 (A1, m30): p_status vazio (fora da lista fechada): st.error com 'resultado desconhecido' e o texto comum
    'desfecho no banco não confirmado', sem 'NÃO EXECUTADA' nem 'erro a partir da chamada ao PKG'."""
    import tools.oracle_dba as od

    linha = _linha_alvo()
    amb = montar_web([linha, linha], status_pkg="")
    _ate_painel_hitl(amb)
    _decidir(amb, "btn_hitl_approve", "dba_teste")

    assert amb.oracle.conexoes_kill == [USER_KILL_FAKE]
    textos = amb.textos_tela()
    assert any(od.MENSAGEM_RESULTADO_DESCONHECIDO in t and od.MENSAGEM_DESFECHO_NAO_CONFIRMADO in t for t in textos)
    assert not any("NÃO EXECUTADA" in t or "NÃO executada" in t for t in textos)
    assert not any("erro a partir da chamada ao PKG" in t for t in textos)
    assert len(amb.emails) == 1
    assert od.MENSAGEM_RESULTADO_DESCONHECIDO in amb.emails[0]["assunto"]
    assert "NÃO executada" not in amb.emails[0]["assunto"]
    assert od.MENSAGEM_DESFECHO_NAO_CONFIRMADO in amb.emails[0]["corpo"]
    assert "erro do Oracle" not in amb.emails[0]["corpo"]
    devolvido = amb.json_devolvido_ao_llm()
    assert devolvido["resultado_desconhecido"] is True and devolvido["executado"] is False


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


# =============================================================================
# R1 ampliada V8/V9 (r1_ampliada/decisao_c1.md §8.3): coordenador em nuvem na Web (W1-W6) e V3 (C3)
# =============================================================================

NOMES_ORACLE = {"coletar_sessoes_ativas", "coletar_top_sql", "coletar_plano_execucao", "matar_sessao_oracle"}
URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _nomes(tools):
    return {f["function"]["name"] for f in (tools or [])}


def _pedir(amb, texto=PEDIDO):
    at = amb.at
    at.run()
    assert not at.exception
    at.chat_input[0].set_value(texto).run()
    assert not at.exception


def _tools_vistas(amb, indice=-1):
    return [m for m in amb.mensagens_llm[indice] if m.get("role") == "tool"]


def test_web_w1_catalogo_local_tem_oracle_e_nuvem_nao(montar_web):
    """W1 (mata V8a, V9a): com o coordenador local o catálogo tem as ferramentas Oracle; com a nuvem, nenhuma.
    Em nenhum dos dois o analisar_log_complexo é oferecido."""
    local = montar_web([_linha_alvo()], kill_permitido=False)
    local.chamada = ("ferramenta_inexistente", {})
    _pedir(local)
    assert local.bases_llm[0] == "http://127.0.0.1:11434/v1"  # Fase 2, K5 (expectativa alterada, declarada; decisao_c1.md §8.4): o cliente local é 127.0.0.1, não localhost.
    assert NOMES_ORACLE <= _nomes(local.tools_llm[0])
    assert "analisar_log_complexo" not in _nomes(local.tools_llm[0])

    nuvem = montar_web([_linha_alvo()], kill_permitido=False, ollama="nuvem")
    nuvem.chamada = ("ferramenta_inexistente", {})
    _pedir(nuvem)
    assert nuvem.bases_llm[0] == URL_GEMINI
    nomes = _nomes(nuvem.tools_llm[0])
    assert nomes, "o catálogo da nuvem não pode vir vazio (SO + RAG)"
    assert not (nomes & NOMES_ORACLE) and "analisar_log_complexo" not in nomes


def test_web_w2_nuvem_chamada_inventada_a_ferramenta_oracle_e_recusada_sem_consultar(montar_web, monkeypatch):
    """W2 (mata V8b): com a nuvem, o LLM chama coletar_plano_execucao mesmo sem ela no catálogo: devolve a recusa
    fixa, sem chamar a ferramenta, sem sonda e sem conexão."""
    amb = montar_web([_linha_alvo()], kill_permitido=False, ollama="nuvem")
    import tools.oracle_dba as od  # depois do montar_web, que põe src/ no sys.path
    # coletar_plano_execucao: só o despacho do LLM a chama (a barra lateral chama coletar_sessoes_ativas e
    # coletar_top_sql direto, para a tela, a cada execução do script)
    chamadas = []
    monkeypatch.setattr(od, "coletar_plano_execucao", lambda *a, **k: chamadas.append(1) or "{}")
    amb.chamada = ("coletar_plano_execucao", {"sql_id": "abc123def4567"})
    _pedir(amb)

    assert chamadas == [] and amb.oracle.conexoes == []
    (tool,) = _tools_vistas(amb)
    assert tool["name"] == "coletar_plano_execucao" and tool["content"] == od.RESULTADO_ORACLE_SO_LOCAL
    assert amb.destinos_inesperados == []


def test_web_w3_nuvem_kill_inventado_nao_gera_pre_consulta_nem_painel(montar_web):
    """W3 (mata V8b): com a nuvem, matar_sessao_oracle não gera pré-consulta DIAG nem painel HITL."""
    amb = montar_web([_linha_alvo()], kill_permitido=False, ollama="nuvem")
    import tools.oracle_dba as od  # depois do montar_web, que põe src/ no sys.path
    _pedir(amb)

    assert amb.at.session_state.hitl_pendente is None
    assert amb.oracle.conexoes == []
    (tool,) = _tools_vistas(amb)
    assert tool["content"] == od.RESULTADO_ORACLE_SO_LOCAL
    assert amb.registros() == []


def test_web_w4_historico_com_dado_do_banco_nao_vai_a_nuvem(montar_web, monkeypatch):
    """W4 (mata V8c): turno 1 com o coordenador local traz dado do banco; o Ollama cai; no turno 2 a nuvem não
    recebe o histórico (nenhuma chamada nova) e a tela mostra o texto fixo."""
    amb = montar_web([_linha_alvo()], kill_permitido=False)
    import tools.oracle_dba as od  # depois do montar_web, que põe src/ no sys.path
    # depois do montar_web, que também substitui coletar_sessoes_ativas
    monkeypatch.setattr(od, "coletar_sessoes_ativas", lambda *a, **k: json.dumps({"sessoes": ["dado-sentinela"]}))
    amb.chamada = ("coletar_sessoes_ativas", {})
    _pedir(amb)
    assert len(amb.mensagens_llm) == 2  # tool_call + laudo, os dois com o coordenador local
    assert any("dado-sentinela" in t["content"] for t in _tools_vistas(amb))

    amb.estado_rede["ollama"] = "nuvem"
    amb.at.chat_input[0].set_value("e agora?").run()
    assert not amb.at.exception

    assert len(amb.mensagens_llm) == 2, "o histórico com dado do banco foi à nuvem"
    assert URL_GEMINI not in amb.bases_llm
    assert any(od.TEXTO_HISTORICO_COM_DADO_DO_BANCO in t for t in amb.textos_tela())


def test_web_w5_ollama_cai_entre_o_painel_e_o_clique(montar_web):
    """W5 (mata V8c): o painel HITL abre com o coordenador local; o Ollama cai antes do clique. O kill é decidido e
    gravado (INTENCAO e RESULTADO), mas o fechamento não vai à nuvem."""
    linha = _linha_alvo()
    amb = montar_web([linha, linha], status_pkg="ENCERRADA")
    import tools.oracle_dba as od  # depois do montar_web, que põe src/ no sys.path
    _ate_painel_hitl(amb)
    amb.estado_rede["ollama"] = "nuvem"

    _decidir(amb, "btn_hitl_approve", "dba_teste")

    resultado = amb.par_intencao_resultado()
    assert resultado["resultado_banco"] == "ENCERRADA"
    assert len(amb.mensagens_llm) == 1, "o fechamento pós-HITL foi à nuvem"
    assert any(od.TEXTO_HISTORICO_COM_DADO_DO_BANCO in t for t in amb.textos_tela())


def test_web_w6_sinal_e_o_base_url_do_cliente_e_nao_o_bool(montar_web):
    """W6 (mata V8d): a sonda diz que o Ollama está ativo, mas o cliente aponta para o Gemini; vale o base_url do
    cliente que envia: catálogo sem Oracle e kill recusado."""
    amb = montar_web([_linha_alvo()], kill_permitido=False)
    import tools.oracle_dba as od  # depois do montar_web, que põe src/ no sys.path
    amb.base_url_forcado = URL_GEMINI
    _pedir(amb)

    assert amb.bases_llm[0] == URL_GEMINI
    assert not (_nomes(amb.tools_llm[0]) & NOMES_ORACLE)
    assert amb.at.session_state.hitl_pendente is None and amb.oracle.conexoes == []
    assert _tools_vistas(amb)[0]["content"] == od.RESULTADO_ORACLE_SO_LOCAL


def test_web_c3_erro_execucao_so_com_o_tipo(montar_web, monkeypatch):
    """C3, Web (mata V3 na interface): exceção numa ferramenta vira {"erro_execucao": <tipo>} ao LLM, sem o texto."""
    def _quebra(*a, **k):
        raise RuntimeError("exc-sentinela")

    amb = montar_web([_linha_alvo()], kill_permitido=False)
    import tools.oracle_dba as od  # depois do montar_web, que põe src/ no sys.path
    # coletar_plano_execucao: só o LLM a chama (a barra lateral chama coletar_top_sql direto, fora do loop)
    monkeypatch.setattr(od, "coletar_plano_execucao", _quebra)
    amb.chamada = ("coletar_plano_execucao", {"sql_id": "abc123def4567"})
    _pedir(amb)

    (tool,) = _tools_vistas(amb)
    assert json.loads(tool["content"]) == {"erro_execucao": "RuntimeError"}
    assert not any("exc-sentinela" in json.dumps(m, default=str) for msgs in amb.mensagens_llm for m in msgs)


# =============================================================================
# R1 ampliada fase 2, K1 (fase2/decisao_c1.md §2): gate de produção do kill na Web (K1-T2, K1-T3 e K1-T7)
# =============================================================================

def test_web_k1_t3_sem_gate_kill_fora_do_catalogo_e_despacho_recusa(montar_web, monkeypatch, caplog):
    """K1-T2 na interface e K1-T3 (mata M_K1_CAT_LOCAL na Web e M_K1_DESP_WEB): coordenador local e sem
    OPS_KILL_PKG_VERSAO. O kill não está no catálogo; o LLM o chama mesmo assim e recebe a recusa fixa, sem
    preparar (sem pré-consulta e sem painel), sem JSONL e sem e-mail."""
    amb = montar_web([_linha_alvo()], kill_permitido=False, versao_pkg=None)
    import tools.oracle_dba as od  # depois do montar_web, que põe src/ no sys.path
    chamadas = []

    def _preparar_espiao(*a, **k):  # o rerun reimporta o nome de tools.oracle_dba
        chamadas.append(1)
        return {"requer_aprovacao": False, "motivo": "ESPIAO", "resultado_tool": "{}"}

    monkeypatch.setattr(od, "preparar_intervencao_kill", _preparar_espiao)
    _pedir(amb)

    assert amb.bases_llm[0] == "http://127.0.0.1:11434/v1"  # Fase 2, K5 (expectativa alterada, declarada; decisao_c1.md §8.4): o cliente local é 127.0.0.1, não localhost.
    nomes = _nomes(amb.tools_llm[0])
    assert "matar_sessao_oracle" not in nomes and (NOMES_ORACLE - {"matar_sessao_oracle"}) <= nomes
    assert chamadas == []
    (tool,) = _tools_vistas(amb)
    assert tool["name"] == "matar_sessao_oracle" and tool["content"] == od.RESULTADO_KILL_DESABILITADO
    assert amb.at.session_state.hitl_pendente is None and _painel_ausente(amb.at)
    assert amb.registros() == [] and amb.emails == [] and amb.oracle.conexoes_kill == []
    # o aviso do yield vai a um st.status que some no rerun; o registro local fica no log
    assert "KILL BLOQUEADO NO DESPACHO (Web): KILL_DESABILITADO (OPS_KILL_PKG_VERSAO)" in caplog.text


def test_web_k1_t7_hitl_pendente_com_o_gate_retirado_antes_do_clique(montar_web, monkeypatch):
    """K1-T7 (ponto do 9.4.2; mata M_K1_REG e M_K1_REG_APOS_INTENCAO na Web): o painel abre com "2"; a variável é
    retirada; o clique em aprovar grava uma RESULTADO KILL_DESABILITADO sem INTENCAO, sem reconsulta DIAG, sem
    conta KILL e sem e-mail. Não se contam conexões globais: o rerun do painel faz DIAG (L8)."""
    linha = _linha_alvo()
    amb = montar_web([linha, linha], status_pkg="ENCERRADA")
    import tools.oracle_dba as od  # depois do montar_web, que põe src/ no sys.path
    _ate_painel_hitl(amb)

    monkeypatch.delenv("OPS_KILL_PKG_VERSAO")
    chamadas = []

    def _espiao(nome):
        def _f(*a, **k):
            chamadas.append(nome)
            raise RuntimeError(f"{nome} chamado com o kill desabilitado")
        return _f

    monkeypatch.setattr(od, "executar_kill_verificado", _espiao("executar_kill_verificado"))
    monkeypatch.setattr(od, "consultar_alvo_sessao_diag", _espiao("consultar_alvo_sessao_diag"))
    _decidir(amb, "btn_hitl_approve", "dba_teste")

    assert chamadas == []
    (reg,) = amb.registros()
    assert reg["fase"] == "RESULTADO" and reg["decisao"] == "APROVADO" and reg["aprovador"] == "dba_teste"
    assert reg["resultado_banco"] == "KILL_DESABILITADO" and reg["motivo"] == "KILL_DESABILITADO"
    assert reg["resultado_desconhecido"] is False
    assert amb.oracle.conexoes_kill == [] and amb.emails == []
    assert amb.at.session_state.hitl_pendente is None and _painel_ausente(amb.at)
    assert any(
        "NÃO EXECUTADA:** encerramento desabilitado nesta instalação" in m["content"]
        for m in amb.at.session_state.messages
    )
    devolvido = amb.json_devolvido_ao_llm()
    assert devolvido["motivo"] == "KILL_DESABILITADO" and devolvido["executado"] is False
    assert "dba_teste" not in json.dumps(devolvido, ensure_ascii=False)


# =============================================================================
# R1 ampliada fase 2, K2 (fase2/decisao_c1.md §1 e §8.2): lista de permissão na Web (K2-T5 e K2-T6)
# =============================================================================

LIBERADAS_K2 = {"coletar_metricas_hardware", "verificar_espaco_disco"}
NOVA_K2 = {"type": "function", "function": {"name": "ferramenta_nova", "parameters": {"type": "object"}}}
ARGUMENTOS_K2 = {
    "coletar_plano_execucao": {"sql_id": "abc123def4567"}, "matar_sessao_oracle": ARGS_KILL,
    "buscar_script_interno": {"tema_ou_problema": "x"},
}


def test_web_k2_t5_catalogo_da_nuvem_so_com_as_liberadas(montar_web, monkeypatch):
    """K2-T5 (mata M_K2_CAT_EXCLUSAO e M_K2_WEB_CAT_SOMA): com uma ferramenta nova registrada (o rerun reimporta
    tools.os_tools), o catálogo local a recebe (o teste não é cego) e o da nuvem é exatamente as 2 de SO."""
    local = montar_web([_linha_alvo()], kill_permitido=False)
    import tools.os_tools as ost  # depois do montar_web, que põe src/ no sys.path
    monkeypatch.setattr(ost, "os_tools_schema", ost.os_tools_schema + [NOVA_K2])
    local.chamada = ("ferramenta_inexistente", {})
    _pedir(local)
    assert "ferramenta_nova" in _nomes(local.tools_llm[0])

    nuvem = montar_web([_linha_alvo()], kill_permitido=False, ollama="nuvem")
    nuvem.chamada = ("ferramenta_inexistente", {})
    _pedir(nuvem)
    assert nuvem.bases_llm[0] == URL_GEMINI
    assert _nomes(nuvem.tools_llm[0]) == LIBERADAS_K2


@pytest.mark.parametrize("ferramenta", sorted(NOMES_ORACLE | {"buscar_script_interno", "ferramenta_nova"}))
def test_web_k2_t5_nuvem_recusa_toda_ferramenta_nao_liberada(montar_web, monkeypatch, ferramenta):
    """K2-T5 (mata R1_M1 e M_K2_DESP_WEB_ORACLE): com a nuvem, o LLM chama cada ferramenta não liberada mesmo fora do
    catálogo: recusa fixa, sem executar, sem conexão e sem painel. A prova é o conteúdo da tool (a barra lateral chama
    coletar_sessoes_ativas e coletar_top_sql direto, a cada execução do script)."""
    amb = montar_web([_linha_alvo()], kill_permitido=False, ollama="nuvem")
    import tools.oracle_dba as od  # depois do montar_web, que põe src/ no sys.path
    import tools.rag_search as rag
    chamadas = []
    monkeypatch.setattr(rag, "buscar_script_interno", lambda *a, **k: chamadas.append("rag") or "{}")
    monkeypatch.setattr(od, "coletar_plano_execucao", lambda *a, **k: chamadas.append("plano") or "{}")
    amb.chamada = (ferramenta, ARGUMENTOS_K2.get(ferramenta, {}))
    _pedir(amb)

    (tool,) = _tools_vistas(amb)
    assert tool["name"] == ferramenta and tool["content"] == od.RESULTADO_ORACLE_SO_LOCAL
    assert chamadas == [] and amb.oracle.conexoes == [] and amb.at.session_state.hitl_pendente is None
    assert amb.registros() == []


def test_web_k2_t5_nuvem_executa_a_liberada(montar_web, monkeypatch):
    """K2-T5, controle positivo: com a nuvem, coletar_metricas_hardware é executada e o resultado vai ao LLM."""
    amb = montar_web([_linha_alvo()], kill_permitido=False, ollama="nuvem")
    import tools.os_tools as ost  # depois do montar_web, que põe src/ no sys.path
    monkeypatch.setattr(ost, "coletar_metricas_hardware", lambda *a, **k: '{"sentinela_hw": 1}')
    amb.chamada = ("coletar_metricas_hardware", {})
    _pedir(amb)

    (tool,) = _tools_vistas(amb)
    assert json.loads(tool["content"]) == {"sentinela_hw": 1}


def test_web_k2_t6_historico_com_rag_nao_vai_a_nuvem(montar_web, monkeypatch):
    """K2-T6, W4 com o RAG (mata M_K2_HIST_RAG e M_K2_RAG_LIBERADO): o turno 1, local, traz conteúdo do RAG; o
    Ollama cai; no turno 2 a nuvem não recebe o histórico e a tela mostra o texto fixo."""
    amb = montar_web([_linha_alvo()], kill_permitido=False)
    import tools.oracle_dba as od  # depois do montar_web, que põe src/ no sys.path
    import tools.rag_search as rag
    monkeypatch.setattr(rag, "buscar_script_interno", lambda *a, **k: json.dumps({"conteudo_sql": "sql-sentinela"}))
    amb.chamada = ("buscar_script_interno", {"tema_ou_problema": "x"})
    _pedir(amb)
    assert len(amb.mensagens_llm) == 2  # tool_call + laudo, os dois com o coordenador local
    assert any("sql-sentinela" in t["content"] for t in _tools_vistas(amb))

    amb.estado_rede["ollama"] = "nuvem"
    amb.at.chat_input[0].set_value("e agora?").run()
    assert not amb.at.exception
    assert len(amb.mensagens_llm) == 2, "o histórico com conteúdo do RAG foi à nuvem"
    assert URL_GEMINI not in amb.bases_llm
    assert any(od.TEXTO_HISTORICO_COM_DADO_DO_BANCO in t for t in amb.textos_tela())


# =============================================================================
# R1 ampliada fase 2, K5 (fase2/decisao_c1.md §8.4): fechamento pós-HITL pelo base_url (K5-T5)
# =============================================================================

def test_web_k5_t5_fechamento_pos_hitl_pelo_base_url_e_nao_pelo_bool(montar_web):
    """K5-T5 (mata R1_M2): o painel abre com o coordenador local; antes do clique a sonda segue "local" (o bool de
    obter_cliente_llm é True), mas o cliente devolvido diz o Gemini. O kill é decidido e gravado, e o fechamento
    não vai à nuvem: vale o base_url do cliente que envia (decisao_c1.md §3.1)."""
    linha = _linha_alvo()
    amb = montar_web([linha, linha], status_pkg="ENCERRADA")
    import tools.oracle_dba as od  # depois do montar_web, que põe src/ no sys.path
    _ate_painel_hitl(amb)
    amb.base_url_forcado = URL_GEMINI

    _decidir(amb, "btn_hitl_approve", "dba_teste")

    assert amb.par_intencao_resultado()["resultado_banco"] == "ENCERRADA"
    assert len(amb.mensagens_llm) == 1, "o fechamento pós-HITL foi à nuvem com a sonda dizendo local"
    assert any(od.TEXTO_HISTORICO_COM_DADO_DO_BANCO in t for t in amb.textos_tela())
