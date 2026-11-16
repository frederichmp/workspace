"""
Configuração global do Pytest para o Personal Agent.
Gerencia marcações de sandbox para proteção contra execuções não autorizadas
e carrega o registro de testes (registry/test_scripts.yaml).
"""

import os
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


def pytest_runtest_setup(item):
    if "sandbox_only" in item.keywords:
        if os.getenv("ORACLE_SANDBOX") != "1":
            pytest.skip("Teste ignorado: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)")
