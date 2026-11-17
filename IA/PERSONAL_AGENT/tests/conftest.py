"""
Configuração global do Pytest para o Personal Agent.
Gerencia marcações de sandbox para proteção contra execuções não autorizadas
e carrega o registro de testes (registry/test_scripts.yaml).
"""

import os
import sys
from pathlib import Path
import pytest

# Configura SCRIPTS_REGISTRY_PATH para apontar para test_scripts.yaml durante os testes (L8)
test_registry_path = Path(__file__).resolve().parent.parent / "registry" / "test_scripts.yaml"
if test_registry_path.is_file():
    os.environ["SCRIPTS_REGISTRY_PATH"] = str(test_registry_path)


@pytest.fixture(scope="session", autouse=True)
def inicializar_registro_testes():
    """Garante que a suíte de testes utilize registry/test_scripts.yaml com cache inicializado."""
    from src.tools.registry import carregar_registro
    carregar_registro(forcar_recarga=True)


LOG_REAL_APROVACAO = Path(__file__).resolve().parent.parent / "data" / "logs" / "kill_approval.log"


def _snapshot_log_real():
    """Retorna (existe, tamanho, mtime_ns) do log real usando apenas stat (sem ler conteúdo)."""
    try:
        st = LOG_REAL_APROVACAO.stat()
    except FileNotFoundError:
        return (False, None, None)
    return (True, st.st_size, st.st_mtime_ns)


SNAPSHOT_LOG_REAL_INICIO = _snapshot_log_real()


@pytest.fixture(scope="session")
def snapshot_log_real_inicio():
    """Snapshot (existe, tamanho, mtime_ns) do log real de aprovação no início da sessão."""
    return SNAPSHOT_LOG_REAL_INICIO


@pytest.fixture(autouse=True)
def isolar_log_aprovacao(monkeypatch, tmp_path):
    """Redireciona o log padrão de aprovação para tmp_path em ambas as cópias do módulo."""
    destino = tmp_path / "kill_approval_isolado.log"
    import src.tools.oracle_dba  # noqa: F401  garante a cópia 'src.tools.oracle_dba'
    for nome in ("src.tools.oracle_dba", "tools.oracle_dba"):
        modulo = sys.modules.get(nome)
        if modulo is not None:
            monkeypatch.setattr(modulo, "CAMINHO_LOG_APROVACAO_PADRAO", destino)
    return destino


def pytest_sessionfinish(session, exitstatus):
    final = _snapshot_log_real()
    if final != SNAPSHOT_LOG_REAL_INICIO:
        print(
            "\nFALHA DE GOVERNANCA: data/logs/kill_approval.log real foi alterado durante a sessão "
            f"de testes (início={SNAPSHOT_LOG_REAL_INICIO}, fim={final})."
        )
        session.exitstatus = 1


def pytest_runtest_setup(item):
    if "sandbox_only" in item.keywords:
        if os.getenv("ORACLE_SANDBOX") != "1":
            pytest.skip("Teste ignorado: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)")
