"""D4: o .env alterado em disco depois do start não pode mudar credenciais do processo em execução."""
import json
import os
import types

import dotenv
import dotenv.main
import oracledb
import pytest

from src.tools import executor, gemini_router, notificador, oracle_dba, rag_search
from src.tools.oracle_dba import conduzir_kill_hitl
from tests.fakes_oracle import USER_DIAG_FAKE, USER_KILL_FAKE, _OracleFake, _linha_alvo

CHAVES = (
    "ORACLE_USER_DIAG", "ORACLE_PASSWORD_DIAG", "ORACLE_USER_KILL", "ORACLE_PASSWORD_KILL",
    "ORACLE_DSN", "EMAIL_REMETENTE", "EMAIL_SENHA_APP", "EMAIL_DESTINATARIO",
)
VALORES_START = {
    "ORACLE_USER_DIAG": "diag_inicio",
    "ORACLE_PASSWORD_DIAG": "senha_diag_inicio",
    "ORACLE_USER_KILL": "kill_inicio",
    "ORACLE_PASSWORD_KILL": "senha_kill_inicio",
    "ORACLE_DSN": "host-inicio.invalid:1521/x",
    "EMAIL_REMETENTE": "remetente_inicio@exemplo.invalid",
    "EMAIL_SENHA_APP": "senhaappinicio",
    "EMAIL_DESTINATARIO": "destino_inicio@exemplo.invalid",
}


class _OracleFakeValoresStart(_OracleFake):
    """Registra o usuário recebido e o traduz para as contas do fake compartilhado."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.usuarios_recebidos = []

    def connect(self, user=None, password=None, dsn=None, **kwargs):
        self.usuarios_recebidos.append(user)
        mapa = {"diag_inicio": USER_DIAG_FAKE, "kill_inicio": USER_KILL_FAKE}
        return super().connect(user=mapa.get(user, user), password=password, dsn=dsn, **kwargs)


class _SmtpFake:
    logins = []
    enviados = 0

    def __init__(self, *a, **k):
        pass

    def starttls(self):
        pass

    def login(self, usuario, senha):
        _SmtpFake.logins.append(usuario)

    def send_message(self, msg):
        _SmtpFake.enviados += 1

    def quit(self):
        pass


def test_kill_apos_alteracao_do_env_usa_valores_do_start(monkeypatch, tmp_path):
    # Fase 2 da R1 (decisao_c1.md §2.3; expectativa alterada, declarada): o kill exige OPS_KILL_PKG_VERSAO=2.
    monkeypatch.setenv("OPS_KILL_PKG_VERSAO", "2")
    for chave, valor in VALORES_START.items():
        monkeypatch.setenv(chave, valor)

    # .env em disco alterado depois do start (mesmas chaves, valores diferentes, nenhuma outra).
    arquivo = tmp_path / ".env"
    arquivo.write_text(
        "\n".join(f"{c}={v.replace('inicio', 'alterado')}" for c, v in VALORES_START.items()) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dotenv.main, "find_dotenv", lambda *a, **k: str(arquivo))

    _SmtpFake.logins = []
    _SmtpFake.enviados = 0
    monkeypatch.setattr(notificador.smtplib, "SMTP", _SmtpFake)
    monkeypatch.setattr(
        oracle_dba,
        "verificar_acessibilidade_host",
        lambda dsn, timeout=3.0: {"acessivel": True, "host": "host-teste", "porta": 1521, "latencia_ms": 0.1},
    )
    fake = _OracleFakeValoresStart(
        [_linha_alvo(), _linha_alvo(), _linha_alvo(), _linha_alvo()], status_pkg="ENCERRADA"
    )
    monkeypatch.setattr(oracledb, "connect", fake.connect)

    for i in (1, 2):
        desfecho = conduzir_kill_hitl(
            {"inst_id": 1, "sid": 101, "serial": 202},
            solicitar_aprovacao=lambda prep: ("APROVADO", "dba_teste", None),
            canal="TESTE",
            caminho_log=tmp_path / f"kill{i}.log",
        )
        assert desfecho["decisao"] == "APROVADO"
        assert desfecho["executado"] is True

    kills = [u for u in fake.usuarios_recebidos if u in ("kill_inicio", "kill_alterado")]
    assert kills == ["kill_inicio", "kill_inicio"]
    assert "kill_alterado" not in fake.usuarios_recebidos
    assert _SmtpFake.logins == ["remetente_inicio@exemplo.invalid"] * 2
    assert _SmtpFake.enviados == 2
    for chave, valor in VALORES_START.items():
        assert os.environ[chave] == valor


def test_fluxo_nao_le_nem_recarrega_dotenv(monkeypatch, tmp_path):
    """D6.2: nenhum leitor de .env é acionado durante o fluxo (kill, e-mail, análise Gemini, execução de
    script homologado e busca RAG).

    O guarda em DotEnv.__init__ pega qualquer leitura, inclusive de nomes ligados no import
    (`from dotenv import load_dotenv`) e de caminho explícito; load_dotenv e dotenv_values trocados por
    funções que também registram. Uma leitura levantaria AssertionError (que o notificador captura), por
    isso a lista de leituras é a asserção principal.
    """
    # Fase 2 da R1 (decisao_c1.md §2.3; expectativa alterada, declarada): o kill exige OPS_KILL_PKG_VERSAO=2.
    monkeypatch.setenv("OPS_KILL_PKG_VERSAO", "2")
    leituras = []

    def _registrar(origem):
        def _falha(*a, **k):
            leituras.append(origem)
            raise AssertionError(f"leitura de .env durante o fluxo: {origem}")
        return _falha

    def _guarda_init(self, *args, **kwargs):
        leituras.append("DotEnv.__init__")
        raise AssertionError("DotEnv construído durante o fluxo")

    monkeypatch.setattr(dotenv.main.DotEnv, "__init__", _guarda_init)
    monkeypatch.setattr(dotenv, "load_dotenv", _registrar("dotenv.load_dotenv"))
    monkeypatch.setattr(dotenv, "dotenv_values", _registrar("dotenv.dotenv_values"))
    monkeypatch.setattr(dotenv.main, "load_dotenv", _registrar("dotenv.main.load_dotenv"))
    monkeypatch.setattr(dotenv.main, "dotenv_values", _registrar("dotenv.main.dotenv_values"))

    for chave, valor in VALORES_START.items():
        monkeypatch.setenv(chave, valor)
    monkeypatch.setenv("GEMINI_API_KEY", "chave_ficticia_d62")
    monkeypatch.setenv("ORACLE_USER_READ", "read_inicio")
    monkeypatch.setenv("ORACLE_PASSWORD_READ", "senha_read_inicio")

    _SmtpFake.logins = []
    _SmtpFake.enviados = 0
    monkeypatch.setattr(notificador.smtplib, "SMTP", _SmtpFake)
    monkeypatch.setattr(
        oracle_dba,
        "verificar_acessibilidade_host",
        lambda dsn, timeout=3.0: {"acessivel": True, "host": "host-teste", "porta": 1521, "latencia_ms": 0.1},
    )
    fake = _OracleFakeValoresStart([_linha_alvo(), _linha_alvo()], status_pkg="ENCERRADA")

    # executar_script (conta READ): conexão e cursor falsos devolvem uma linha fixa; o kill segue no fake acima.
    conexoes_read = []

    class _CursorSelectFalso:
        description = [("INST_ID",)]

        def execute(self, sql, binds=None):
            pass

        def fetchone(self):
            return (1,)

        def fetchmany(self, n):
            return [(1,)]

        def close(self):
            pass

    class _ConexaoSelectFalsa:
        call_timeout = None

        def cursor(self):
            return _CursorSelectFalso()

        def rollback(self):
            pass

        def close(self):
            pass

    def _connect(user=None, password=None, dsn=None, **kwargs):
        if user == "read_inicio":
            conexoes_read.append(user)
            return _ConexaoSelectFalsa()
        return fake.connect(user=user, password=password, dsn=dsn, **kwargs)

    monkeypatch.setattr(oracledb, "connect", _connect)

    # buscar_script_interno: base vetorial falsa (sem chromadb, modelo ou rede); CHROMA_DB_DIR existe em tmp_path.
    chroma_dir = tmp_path / "chroma_db"
    chroma_dir.mkdir()
    monkeypatch.setattr(rag_search, "CHROMA_DB_DIR", chroma_dir)

    class _VectorstoreFalso:
        def similarity_search_with_score(self, consulta, k=3):
            doc = types.SimpleNamespace(
                metadata={"source": str(tmp_path / "script_fictico.sql")}, page_content="SELECT 1 FROM dual"
            )
            return [(doc, 0.25)]

    monkeypatch.setattr(rag_search, "_obter_vectorstore", lambda: _VectorstoreFalso())

    # Gemini neutralizado: sem rede; só registra a chave recebida (booleano) e devolve texto fixo.
    chaves_configuradas = []

    class _ModeloFalso:
        def __init__(self, nome):
            self.nome = nome

        def generate_content(self, prompt, **kwargs):
            return types.SimpleNamespace(text="analise fictícia")

    monkeypatch.setattr(gemini_router.genai, "configure", lambda **k: chaves_configuradas.append(k.get("api_key")))
    monkeypatch.setattr(gemini_router.genai, "GenerativeModel", _ModeloFalso)

    desfecho = None
    saida_script = None
    busca = None
    try:
        desfecho = conduzir_kill_hitl(
            {"inst_id": 1, "sid": 101, "serial": 202},
            solicitar_aprovacao=lambda prep: ("APROVADO", "dba_teste", None),
            canal="TESTE",
            caminho_log=tmp_path / "kill.log",
        )
        laudo = json.loads(gemini_router.analisar_log_complexo("dados fictícios", "contexto fictício"))
        saida_script = json.loads(executor.executar_script("verificar_dual", {}))
        busca = json.loads(rag_search.buscar_script_interno("sessões bloqueadas"))
    except AssertionError:
        laudo = None  # a leitura já foi registrada em `leituras`

    assert leituras == []
    assert desfecho is not None and desfecho["decisao"] == "APROVADO" and desfecho["executado"] is True
    assert _SmtpFake.logins == ["remetente_inicio@exemplo.invalid"]
    assert laudo is not None and laudo["status"] == "sucesso"
    assert chaves_configuradas == ["chave_ficticia_d62"]
    assert saida_script is not None and saida_script["status"] == "sucesso"
    assert saida_script["tipo"] == "SELECT" and saida_script["saida"] == [{"inst_id": 1}]
    assert conexoes_read == ["read_inicio"]
    assert busca is not None and busca["status"] == "sucesso"
    assert busca["total_encontrado"] == 1 and busca["scripts_homologados"][0]["arquivo"] == "script_fictico.sql"


def test_k1_t10_gate_nao_rele_o_dotenv(monkeypatch, tmp_path):
    """K1-T10, L13 (mata M_K1_RELE_DOTENV): sem a variável no ambiente e com um .env em disco que a define como 2,
    o kill segue indisponível. O gate lê só os.environ: construir um DotEnv falha o teste."""
    monkeypatch.delenv("OPS_KILL_PKG_VERSAO", raising=False)
    for chave, valor in VALORES_START.items():
        monkeypatch.setenv(chave, valor)
    arquivo = tmp_path / ".env"
    arquivo.write_text("OPS_KILL_PKG_VERSAO=2\n", encoding="utf-8")
    monkeypatch.setattr(dotenv.main, "find_dotenv", lambda *a, **k: str(arquivo))

    def _guarda_init(self, *a, **k):
        pytest.fail("DotEnv construído: o gate releu o .env")

    monkeypatch.setattr(dotenv.main.DotEnv, "__init__", _guarda_init)
    monkeypatch.setattr(
        oracle_dba,
        "verificar_acessibilidade_host",
        lambda dsn, timeout=3.0: {"acessivel": True, "host": "host-teste", "porta": 1521, "latencia_ms": 0.1},
    )
    fake = _OracleFakeValoresStart([_linha_alvo()], status_pkg="ENCERRADA")
    monkeypatch.setattr(oracledb, "connect", fake.connect)

    def _sem_prompt(prep):
        pytest.fail("prompt exibido com o kill desabilitado")

    desfecho = conduzir_kill_hitl(
        {"inst_id": 1, "sid": 101, "serial": 202},
        solicitar_aprovacao=_sem_prompt,
        canal="TESTE",
        caminho_log=tmp_path / "kill.log",
    )
    assert desfecho["motivo"] == "KILL_DESABILITADO" and desfecho["executado"] is False
    assert fake.usuarios_recebidos == []
    assert "OPS_KILL_PKG_VERSAO" not in os.environ
