"""D4: o .env alterado em disco depois do start não pode mudar credenciais do processo em execução."""
import json
import os
import types

import dotenv
import dotenv.main
import oracledb

from src.tools import gemini_router, notificador, oracle_dba
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
    """D6.2: nenhum leitor de .env é acionado durante o fluxo (kill, e-mail e análise Gemini).

    O guarda em DotEnv.__init__ pega qualquer leitura, inclusive de nomes ligados no import
    (`from dotenv import load_dotenv`) e de caminho explícito; load_dotenv e dotenv_values trocados por
    funções que também registram. Uma leitura levantaria AssertionError (que o notificador captura), por
    isso a lista de leituras é a asserção principal.
    """
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

    _SmtpFake.logins = []
    _SmtpFake.enviados = 0
    monkeypatch.setattr(notificador.smtplib, "SMTP", _SmtpFake)
    monkeypatch.setattr(
        oracle_dba,
        "verificar_acessibilidade_host",
        lambda dsn, timeout=3.0: {"acessivel": True, "host": "host-teste", "porta": 1521, "latencia_ms": 0.1},
    )
    fake = _OracleFakeValoresStart([_linha_alvo(), _linha_alvo()], status_pkg="ENCERRADA")
    monkeypatch.setattr(oracledb, "connect", fake.connect)

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
    try:
        desfecho = conduzir_kill_hitl(
            {"inst_id": 1, "sid": 101, "serial": 202},
            solicitar_aprovacao=lambda prep: ("APROVADO", "dba_teste", None),
            canal="TESTE",
            caminho_log=tmp_path / "kill.log",
        )
        laudo = json.loads(gemini_router.analisar_log_complexo("dados fictícios", "contexto fictício"))
    except AssertionError:
        laudo = None  # a leitura já foi registrada em `leituras`

    assert leituras == []
    assert desfecho is not None and desfecho["decisao"] == "APROVADO" and desfecho["executado"] is True
    assert _SmtpFake.logins == ["remetente_inicio@exemplo.invalid"]
    assert laudo is not None and laudo["status"] == "sucesso"
    assert chaves_configuradas == ["chave_ficticia_d62"]
