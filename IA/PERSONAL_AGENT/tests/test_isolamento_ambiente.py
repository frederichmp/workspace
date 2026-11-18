"""Isolamento de ambiente da suíte: load_dotenv sem override e vigilância dos logs reais.
Sem conexão e sem ler o .env real."""

import os
import re
from pathlib import Path

from tests import conftest
from dotenv import load_dotenv

_PADRAO_OVERRIDE = re.compile(r"load_dotenv\s*\([^)]*override\s*=\s*True", re.DOTALL)


def test_nenhum_load_dotenv_com_override_em_tests():
    pasta = Path(__file__).resolve().parent
    ofensores = [
        p.name
        for p in pasta.glob("*.py")
        if p.name != Path(__file__).name and _PADRAO_OVERRIDE.search(p.read_text(encoding="utf-8"))
    ]
    assert ofensores == []


def test_load_dotenv_sem_override_preserva_log_dir(tmp_path, monkeypatch):
    env_falso = tmp_path / ".env"
    env_falso.write_text("AGENTDBA_LOG_DIR=C:\AgentDBA\logs\n", encoding="utf-8")
    alvo = str(tmp_path / "logs_teste")
    monkeypatch.setenv("AGENTDBA_LOG_DIR", alvo)
    load_dotenv(dotenv_path=env_falso, override=False)
    assert os.environ["AGENTDBA_LOG_DIR"] == alvo


def test_load_dotenv_sem_override_preenche_variavel_ausente(tmp_path, monkeypatch):
    """risco residual: o .env não deve conter ORACLE_SANDBOX."""
    env_falso = tmp_path / ".env"
    env_falso.write_text("ORACLE_SANDBOX=1\n", encoding="utf-8")
    monkeypatch.delenv("ORACLE_SANDBOX", raising=False)
    load_dotenv(dotenv_path=env_falso, override=False)
    assert os.environ.get("ORACLE_SANDBOX") == "1"
    monkeypatch.delenv("ORACLE_SANDBOX", raising=False)


def test_log_real_nao_tocado_ate_aqui():
    assert conftest.INSTANTANEO_LOGS_REAIS_INICIO == conftest._instantaneo_logs_reais()


def test_conftest_detecta_log_real_tocado(tmp_path, monkeypatch):
    a, b = tmp_path / "a.log", tmp_path / "b.log"
    a.write_bytes(b"x")
    monkeypatch.setattr(conftest, "LOGS_REAIS_VIGIADOS", (a, b))
    inicio = conftest._instantaneo_logs_reais()
    assert not conftest._log_real_tocado(inicio, conftest._instantaneo_logs_reais())
    with open(a, "ab") as f:
        f.write(b"y")
    assert conftest._log_real_tocado(inicio, conftest._instantaneo_logs_reais())
    inicio2 = conftest._instantaneo_logs_reais()
    b.write_bytes(b"z")  # criado
    assert conftest._log_real_tocado(inicio2, conftest._instantaneo_logs_reais())
