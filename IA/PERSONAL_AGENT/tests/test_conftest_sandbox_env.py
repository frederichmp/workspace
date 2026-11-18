"""Testes (sem conexão) da carga controlada de credenciais de sandbox do conftest (D5)."""

import os

from tests.conftest import CHAVES_ENV_SANDBOX, credenciais_sandbox_do_env


def test_chaves_env_sandbox_lista_fechada():
    proibidas = {"ORACLE_SANDBOX", "ORACLE_USER", "ORACLE_PASSWORD"}
    assert not proibidas & set(CHAVES_ENV_SANDBOX)
    for chave in CHAVES_ENV_SANDBOX:
        assert not chave.startswith(("EMAIL_", "GEMINI_", "AGENTDBA_", "SCRIPTS_"))


def test_credenciais_sandbox_sem_operador_retorna_vazio(tmp_path):
    arq = tmp_path / ".env"
    arq.write_text("ORACLE_USER_KILL=kill_ficticio\n", encoding="utf-8")
    assert credenciais_sandbox_do_env(arq, None, {}) == {}
    assert credenciais_sandbox_do_env(arq, "0", {}) == {}


def test_credenciais_sandbox_filtra_e_nao_sobrescreve(tmp_path):
    arq = tmp_path / ".env"
    arq.write_text(
        "ORACLE_USER_KILL=kill_ficticio\n"
        "ORACLE_DSN=dsn_ficticio\n"
        "ORACLE_USER=legado_ficticio\n"
        "EMAIL_REMETENTE=x\n"
        "GEMINI_API_KEY=x\n"
        "AGENTDBA_LOG_DIR=x\n",
        encoding="utf-8",
    )
    antes = dict(os.environ)
    resultado = credenciais_sandbox_do_env(arq, "1", {"ORACLE_DSN": "do_shell"})
    assert resultado == {"ORACLE_USER_KILL": "kill_ficticio"}
    assert dict(os.environ) == antes
