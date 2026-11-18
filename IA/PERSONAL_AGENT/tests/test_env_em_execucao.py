"""D4: o .env alterado em disco depois do start não pode mudar credenciais do processo em execução."""
import os

import dotenv.main
import oracledb

from src.tools import notificador, oracle_dba
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
