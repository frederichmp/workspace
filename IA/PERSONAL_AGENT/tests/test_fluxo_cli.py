"""
Smoke test do fluxo HITL na CLI (src/main.py), sem conexão: LLM, Oracle, rede e SMTP são falsos.

Neutralizações (fixture de módulo): load_dotenv no-op, credenciais fictícias, handler nulo na raiz
(basicConfig vira no-op, sem FileHandler para auditoria_oracle.log) e socket.create_connection
bloqueado (127.0.0.1:11434 -> OSError; qualquer outro destino -> falha do teste).
Os patches de Oracle miram `tools.oracle_dba` (objeto usado por main.py), não `src.tools.oracle_dba`.
"""
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.fakes_oracle import (
    USER_DIAG_FAKE,
    USER_KILL_FAKE,
    _OracleFake,
    _eh_consulta_alvo,
    _linha_alvo,
)

RAIZ = Path(__file__).resolve().parent.parent
LOGS_REAIS = (RAIZ / "auditoria_oracle.log", RAIZ / "data" / "logs" / "auditoria_oracle.log")
ARGS_KILL = {"inst_id": 1, "sid": 101, "serial": 202}


class _LLMFalso:
    """Substitui main.client: 1ª chamada pede matar_sessao_oracle; 2ª devolve texto final."""

    def __init__(self):
        self.chamadas = []  # cópia da lista de mensagens recebida em cada chamada
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model=None, messages=None, tools=None, **kwargs):
        self.chamadas.append(list(messages))
        if len(self.chamadas) == 1:
            tool_call = SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(name="matar_sessao_oracle", arguments=json.dumps(ARGS_KILL)),
            )
            msg = SimpleNamespace(content=None, tool_calls=[tool_call])
        else:
            msg = SimpleNamespace(content="Resposta final do agente falso.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    def resultado_tool(self):
        """JSON devolvido ao LLM (mensagem role=tool vista na 2ª chamada)."""
        assert len(self.chamadas) == 2, "o LLM falso deveria ter sido chamado exatamente 2 vezes"
        tools = [m for m in self.chamadas[1] if isinstance(m, dict) and m.get("role") == "tool"]
        assert len(tools) == 1
        return json.loads(tools[0]["content"])


def _snapshot(caminho):
    try:
        st = caminho.stat()
    except FileNotFoundError:
        return (False, None, None)
    return (True, st.st_size, st.st_mtime_ns)


def _filehandlers_auditoria():
    """FileHandlers cujo arquivo é um dos logs reais de auditoria (raiz, tools.oracle_dba e main)."""
    alvos = {str(p.resolve()).lower() for p in LOGS_REAIS}
    encontrados = []
    for nome in ("", "tools.oracle_dba", "src.tools.oracle_dba", "main"):
        for h in logging.getLogger(nome).handlers:
            if isinstance(h, logging.FileHandler) and str(Path(h.baseFilename).resolve()).lower() in alvos:
                encontrados.append(h)
    return encontrados


@pytest.fixture(scope="module")
def main_cli():
    mp = pytest.MonkeyPatch()
    import dotenv
    mp.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    for caminho in (str(RAIZ / "src"), str(RAIZ)):
        mp.syspath_prepend(caminho)
    mp.setenv("ORACLE_USER_DIAG", USER_DIAG_FAKE)
    mp.setenv("ORACLE_PASSWORD_DIAG", "senha_diag_ficticia")
    mp.setenv("ORACLE_USER_KILL", USER_KILL_FAKE)
    mp.setenv("ORACLE_PASSWORD_KILL", "senha_kill_ficticia")
    mp.setenv("ORACLE_DSN", "host-ficticio.invalid:1521/FAKE")
    mp.delenv("ORACLE_SANDBOX", raising=False)

    import socket

    def _create_connection(endereco, *args, **kwargs):
        if tuple(endereco) == ("127.0.0.1", 11434):
            raise OSError("Ollama indisponível (neutralizado no teste)")
        pytest.fail(f"Tentativa de conexão de rede não permitida: {endereco!r}")

    mp.setattr(socket, "create_connection", _create_connection)

    nulo = logging.NullHandler()
    logging.getLogger().addHandler(nulo)
    ja_importado = "main" in sys.modules
    try:
        import main
        main.client = _LLMFalso()
        assert not _filehandlers_auditoria(), "import de main não pode adicionar FileHandler de auditoria"
        yield main
    finally:
        logging.getLogger().removeHandler(nulo)
        if not ja_importado:
            sys.modules.pop("main", None)
        mp.undo()


@pytest.fixture
def cenario(main_cli, monkeypatch, isolar_log_aprovacao, caplog, capsys):
    """Prepara um fluxo: devolve executar(linhas_diag, status_pkg, entradas, kill_permitido)."""
    import tools.oracle_dba as od

    # O log de aprovação padrão deve apontar para tmp_path (autouse do conftest ou redirecionamento local)
    if od.CAMINHO_LOG_APROVACAO_PADRAO != isolar_log_aprovacao:
        monkeypatch.setattr(od, "CAMINHO_LOG_APROVACAO_PADRAO", isolar_log_aprovacao)
    assert od.CAMINHO_LOG_APROVACAO_PADRAO == isolar_log_aprovacao

    emails = []

    def _email(assunto, corpo):
        emails.append((assunto, corpo))
        return True, "capturado (fake)"

    monkeypatch.setattr(
        od, "verificar_acessibilidade_host",
        lambda dsn, timeout=3.0: {"acessivel": True, "host": "fake", "porta": 1521, "erro_rede": None},
    )
    monkeypatch.setattr(od, "enviar_alerta_email", _email)
    caplog.set_level(logging.INFO)

    def executar(linhas_diag, status_pkg, entradas, kill_permitido=True):
        oracle = _OracleFake(linhas_diag, status_pkg=status_pkg, kill_permitido=kill_permitido)
        monkeypatch.setattr(od.oracledb, "connect", oracle.connect)
        iterador = iter(entradas)
        monkeypatch.setattr("builtins.input", lambda *a, **k: next(iterador))
        llm = _LLMFalso()
        monkeypatch.setattr(main_cli, "client", llm)
        main_cli.executar_agente("mate a sessão 101,202 da instância 1")
        assert next(iterador, None) is None, "sobraram entradas não consumidas em input()"
        linhas = []
        if isolar_log_aprovacao.exists():
            linhas = [json.loads(l) for l in isolar_log_aprovacao.read_text(encoding="utf-8").splitlines() if l.strip()]
        consultas_diag = sum(1 for conta, sql, _ in oracle.sql_executado if conta == "DIAG" and _eh_consulta_alvo(sql))
        return SimpleNamespace(
            oracle=oracle, llm=llm, emails=emails, linhas=linhas, consultas_diag=consultas_diag,
            tela=capsys.readouterr().out, log=caplog.text, json_tool=llm.resultado_tool(),
        )

    return executar


def _um_registro(r):
    assert len(r.linhas) == 1
    return r.linhas[0]


def _sem_filehandler_real():
    assert not _filehandlers_auditoria()


def test_cli_aprovado_encerrada(cenario):
    r = cenario([_linha_alvo(), _linha_alvo()], "ENCERRADA", ["dba", "S"])
    assert r.consultas_diag == 2
    assert len(r.oracle.conexoes_kill) == 1
    assert len(r.emails) == 1 and "Intervenção Aprovada" in r.emails[0][0]
    reg = _um_registro(r)
    assert reg["decisao"] == "APROVADO" and reg["resultado_banco"] == "ENCERRADA"
    assert reg["aprovador"] == "dba"
    assert "EXECUTADA COM SUCESSO" in r.tela
    assert "AUDITORIA HITL: APROVADO" in r.log
    assert r.json_tool["decisao"] == "APROVADO" and r.json_tool["executado"] is True
    assert r.json_tool["resultado_banco"] == "ENCERRADA"
    _sem_filehandler_real()


def test_cli_aprovado_nao_usuario(cenario):
    r = cenario([_linha_alvo(), _linha_alvo()], "NAO_USUARIO", ["dba", "S"])
    assert r.consultas_diag == 2
    assert len(r.oracle.conexoes_kill) == 1
    assert len(r.emails) == 1 and "NÃO executada" in r.emails[0][0]
    reg = _um_registro(r)
    assert reg["decisao"] == "APROVADO" and reg["resultado_banco"] == "NAO_USUARIO"
    assert "mas NÃO EXECUTADA" in r.tela
    assert r.json_tool["decisao"] == "APROVADO" and r.json_tool["executado"] is False
    assert r.json_tool["resultado_banco"] == "NAO_USUARIO"
    _sem_filehandler_real()


def test_cli_rejeitado(cenario):
    r = cenario([_linha_alvo()], None, ["dba", "N"], kill_permitido=False)
    assert r.consultas_diag == 1
    assert len(r.oracle.conexoes_kill) == 0
    assert r.emails == []
    reg = _um_registro(r)
    assert reg["decisao"] == "REJEITADO" and reg["resultado_banco"] is None
    assert reg["motivo"] == "REJEITADO_PELO_APROVADOR"
    assert "NÃO aprovada" in r.tela
    assert r.json_tool["decisao"] == "REJEITADO" and r.json_tool["executado"] is False
    _sem_filehandler_real()


def test_cli_aprovador_vazio(cenario):
    r = cenario([_linha_alvo()], None, [""], kill_permitido=False)
    assert r.consultas_diag == 1
    assert len(r.oracle.conexoes_kill) == 0
    assert r.emails == []
    reg = _um_registro(r)
    assert reg["decisao"] == "REJEITADO" and reg["resultado_banco"] is None
    assert reg["motivo"] == "SEM_IDENTIFICACAO"
    assert "Identificação do aprovador é obrigatória" in r.tela
    assert r.json_tool["decisao"] == "REJEITADO" and r.json_tool["executado"] is False
    assert r.json_tool["motivo"] == "SEM_IDENTIFICACAO"
    _sem_filehandler_real()


def test_cli_alvo_alterado(cenario):
    r = cenario([_linha_alvo(), _linha_alvo(program="outro.exe")], None, ["dba", "S"], kill_permitido=False)
    assert r.consultas_diag == 2
    assert len(r.oracle.conexoes_kill) == 0
    assert len(r.emails) == 1 and "NÃO executada" in r.emails[0][0]
    reg = _um_registro(r)
    assert reg["decisao"] == "APROVADO" and reg["resultado_banco"] == "ALVO_ALTERADO"
    assert "mas NÃO EXECUTADA" in r.tela
    assert "ALVO_ALTERADO" in r.log
    assert r.json_tool["decisao"] == "APROVADO" and r.json_tool["executado"] is False
    assert r.json_tool["resultado_banco"] == "ALVO_ALTERADO"
    _sem_filehandler_real()


def test_cli_nao_grava_auditoria_real(cenario):
    antes = [_snapshot(p) for p in LOGS_REAIS]
    r = cenario([_linha_alvo(), _linha_alvo()], "ENCERRADA", ["dba", "S"])
    assert r.json_tool["executado"] is True
    depois = [_snapshot(p) for p in LOGS_REAIS]
    assert antes == depois, "auditoria_oracle.log real foi alterado pelo fluxo CLI"
    _sem_filehandler_real()
