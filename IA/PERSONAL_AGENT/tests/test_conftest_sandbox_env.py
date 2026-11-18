"""Testes (sem conexão) da carga controlada de credenciais de sandbox do conftest (D5)."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import tests.conftest as conftest
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


def test_credenciais_sandbox_valor_vazio_ou_sem_valor_nao_entra(tmp_path):
    """D6.1: `KEY=` (vazio) e `KEY` (sem valor) nunca entram, mesmo com operador "1" passado como argumento."""
    arq = tmp_path / ".env"
    arq.write_text(
        "ORACLE_DSN=\n"
        "ORACLE_USER_DIAG\n"
        "ORACLE_USER_KILL=kill_ficticio\n",
        encoding="utf-8",
    )
    antes = dict(os.environ)
    assert credenciais_sandbox_do_env(arq, "1", {}) == {"ORACLE_USER_KILL": "kill_ficticio"}
    assert dict(os.environ) == antes


_SCRIPT_LIGACAO = r"""
import json, os, runpy, sys
ns = runpy.run_path(sys.argv[1])
procuradas = list(ns["CHAVES_ENV_SANDBOX"]) + ["SENTINELA_D61_A", "SENTINELA_D61_B"]
print(json.dumps({
    "presentes": [k for k in procuradas if k in os.environ],  # só nomes, nunca valores
    "operador_visto": ns["ORACLE_SANDBOX_DO_OPERADOR"],
}))
"""


@pytest.mark.parametrize("sandbox_shell", [None, "0"], ids=["ausente", "zero"])
def test_ligacao_real_do_conftest_nao_carrega_env_sem_operador(tmp_path, sandbox_shell):
    """D6.1: o módulo conftest (copiado para um projeto fictício) não põe nada do .env em os.environ.

    O .env fictício só tem chaves de CHAVES_ENV_SANDBOX (valores fictícios) e nomes-sentinela. O filho não
    tem credenciais e o ORACLE_SANDBOX do filho é ausente ou "0", nunca "1". O .env real não é lido.
    """
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    shutil.copyfile(conftest.__file__, proj / "tests" / "conftest.py")
    linhas = [f"{k}=valor_ficticio_d61" for k in CHAVES_ENV_SANDBOX]
    linhas += ["SENTINELA_D61_A=1", "SENTINELA_D61_B=2"]
    (proj / ".env").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    env = {k: v for k, v in os.environ.items() if not k.startswith(("ORACLE_", "EMAIL_", "GEMINI_"))}
    (tmp_path / "tmp").mkdir()
    env["TEMP"] = env["TMP"] = str(tmp_path / "tmp")  # o mkdtemp do conftest cai em tmp_path
    if sandbox_shell is not None:
        assert sandbox_shell == "0"
        env["ORACLE_SANDBOX"] = sandbox_shell
    res = subprocess.run(
        [sys.executable, "-c", _SCRIPT_LIGACAO, str(proj / "tests" / "conftest.py")],
        capture_output=True, text=True, env=env, timeout=120, cwd=str(proj),
    )
    ultima = (res.stderr.strip().splitlines() or [""])[-1]
    assert res.returncode == 0, f"subprocesso falhou (returncode={res.returncode}): {ultima}"
    dados = json.loads(res.stdout.strip().splitlines()[-1])
    assert dados["presentes"] == [], f"chaves do .env fictício entraram em os.environ: {dados['presentes']}"
    assert dados["operador_visto"] == sandbox_shell
