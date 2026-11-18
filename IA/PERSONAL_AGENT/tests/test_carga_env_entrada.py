"""Fase 2 (D1/D2): a carga do .env nas entradas (src/main.py e app.py) não pode introduzir ORACLE_SANDBOX.

REGRA DE SEGURANÇA (incidente 01:27): o .env fictício com ORACLE_SANDBOX só é lido DENTRO DE SUBPROCESSO
sem credenciais (nenhuma chave ORACLE_/EMAIL_/GEMINI_ herdada). O processo do pytest nunca tem
ORACLE_SANDBOX alterada e o .env real nunca é lido (load_dotenv é redirecionado para o arquivo fictício).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
_PREFIXOS = ("ORACLE_", "EMAIL_", "GEMINI_")

_SCRIPT = r"""
import json, logging, os, socket, sys
raiz, entrada, env_ficticio = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, raiz)
sys.path.insert(0, os.path.join(raiz, "src"))

import dotenv
_original = dotenv.load_dotenv
chamadas = []

def _wrapper(dotenv_path=None, *args, **kwargs):
    chamadas.append({
        "caminho": None if dotenv_path is None else str(dotenv_path),
        "override": kwargs["override"] if "override" in kwargs else "AUSENTE",
    })
    kwargs.setdefault("override", False)
    return _original(env_ficticio, *args, **kwargs)

dotenv.load_dotenv = _wrapper

capturados = []

class _Captura(logging.Handler):
    def emit(self, record):
        capturados.append((record.levelname, record.getMessage()))

raiz_log = logging.getLogger()
raiz_log.addHandler(_Captura())
raiz_log.setLevel(logging.INFO)  # handlers existentes: basicConfig vira no-op, sem FileHandler novo

def _sem_rede(*a, **k):
    raise OSError("rede neutralizada no teste")

socket.create_connection = _sem_rede

if entrada == "cli":
    import main  # noqa: F401
else:
    from streamlit.testing.v1 import AppTest
    AppTest.from_file(os.path.join(raiz, "app.py"), default_timeout=30).run()

print(json.dumps({
    "sandbox": os.environ.get("ORACLE_SANDBOX", "AUSENTE"),
    "sentinela": os.environ.get("SENTINELA_FASE2", "AUSENTE"),
    "avisos": [m for n, m in capturados if n == "WARNING"],
    "chamadas": chamadas,
}))
"""


def _rodar(entrada, tmp_path, conteudo_env, sandbox_shell=None):
    env_ficticio = tmp_path / "ficticio.env"
    env_ficticio.write_text(conteudo_env, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith(_PREFIXOS)}
    env["AGENTDBA_LOG_DIR"] = str(tmp_path / "log")
    env["SCRIPTS_REGISTRY_PATH"] = str(RAIZ / "registry" / "test_scripts.yaml")
    if sandbox_shell is not None:
        env["ORACLE_SANDBOX"] = sandbox_shell
    res = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ), entrada, str(env_ficticio)],
        capture_output=True, text=True, env=env, timeout=180, cwd=str(RAIZ),
    )
    ultima = (res.stderr.strip().splitlines() or [""])[-1]
    assert res.returncode == 0, f"subprocesso falhou (returncode={res.returncode}): {ultima}"
    return json.loads(res.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_oracle_sandbox_do_env_descartada(entrada, tmp_path):
    dados = _rodar(entrada, tmp_path, "ORACLE_SANDBOX=1\nSENTINELA_FASE2=1\n")
    resumo = f"sandbox={dados['sandbox']}, avisos={dados['avisos']}, chamadas={dados['chamadas']}"
    assert dados["sentinela"] == "1", resumo  # prova que o .env fictício foi carregado
    assert dados["sandbox"] == "AUSENTE", resumo
    descartes = [a for a in dados["avisos"] if "ORACLE_SANDBOX" in a and "DESCARTADA" in a]
    assert len(descartes) == 1, resumo
    assert len(dados["chamadas"]) == 1, resumo
    chamada = dados["chamadas"][0]
    assert chamada["caminho"] is not None and Path(chamada["caminho"]) == RAIZ / ".env", resumo
    assert chamada["override"] is False, resumo


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_oracle_sandbox_do_shell_prevalece(entrada, tmp_path):
    dados = _rodar(entrada, tmp_path, "ORACLE_SANDBOX=1\n", sandbox_shell="0")
    resumo = f"sandbox={dados['sandbox']}, avisos={dados['avisos']}"
    assert dados["sandbox"] == "0", resumo
    assert not [a for a in dados["avisos"] if "DESCARTADA" in a], resumo
