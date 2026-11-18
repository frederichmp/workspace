"""Caracterização (B refeito, incidente 01:27): importar módulos de teste não pode alterar os.environ.

Se falhar com chaves ORACLE_* adicionadas, a causa é load_dotenv de produção (oracle_dba.py:33,
executor.py:38, notificador.py:17) preenchendo a partir do .env: fora do escopo deste commit
(só tests/); reportar, não alterar a expectativa.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_PREFIXOS = ("ORACLE_", "EMAIL_", "GEMINI_")

_SCRIPT = r"""
import importlib, json, os, sys
raiz, testes = sys.argv[1], sys.argv[2]
sys.path.insert(0, raiz)
sys.path.insert(0, testes)
PREF = ("ORACLE_", "EMAIL_", "GEMINI_")
antes = dict(os.environ)
# D6.5: inclui src.config.settings e os dois testes de privilégio (carregavam o .env no import).
for nome in (
    "test_executor", "test_oracle_kill", "test_item1_intencao",
    "src.config.settings", "test_privilegio_read", "test_privilegio_write_sandbox",
):
    importlib.import_module(nome)
depois = dict(os.environ)
add = sorted(set(depois) - set(antes))
rem = sorted(set(antes) - set(depois))
alt = sorted(k for k in set(antes) & set(depois) if antes[k] != depois[k])
nao_sens = sorted(k for k in set(add + rem + alt) if not k.startswith(PREF))
print(json.dumps({
    "adicionadas_n": len(add),
    "removidas_n": len(rem),
    "alteradas_n": len(alt),
    "nomes_nao_sensiveis": nao_sens,
    "oracle_sandbox_antes": "presente" if "ORACLE_SANDBOX" in antes else "ausente",
    "oracle_sandbox_depois": "presente" if "ORACLE_SANDBOX" in depois else "ausente",
}))
"""


def test_imports_de_teste_nao_alteram_environ(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith(_PREFIXOS)}
    env["AGENTDBA_LOG_DIR"] = str(tmp_path / "log")
    env["SCRIPTS_REGISTRY_PATH"] = str(RAIZ / "registry" / "test_scripts.yaml")
    res = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ), str(RAIZ / "tests")],
        capture_output=True, text=True, env=env, timeout=120, cwd=str(RAIZ),
    )
    ultima = (res.stderr.strip().splitlines() or [""])[-1]
    assert res.returncode == 0, f"subprocesso falhou (returncode={res.returncode}): {ultima}"
    dados = json.loads(res.stdout.strip().splitlines()[-1])
    resumo = (
        f"adicionadas_n={dados['adicionadas_n']}, removidas_n={dados['removidas_n']}, "
        f"alteradas_n={dados['alteradas_n']}, nomes_nao_sensiveis={dados['nomes_nao_sensiveis']}"
    )
    assert dados["oracle_sandbox_antes"] == "ausente", resumo
    assert dados["oracle_sandbox_depois"] == "ausente", resumo
    assert dados["adicionadas_n"] == 0 and dados["removidas_n"] == 0, resumo
    assert dados["alteradas_n"] == 0, resumo
