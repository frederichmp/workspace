"""
Configuração global do Pytest para o Personal Agent.
Gerencia marcações de sandbox para proteção contra execuções não autorizadas.
"""

import os
import pytest


def pytest_runtest_setup(item):
    if "sandbox_only" in item.keywords:
        if os.getenv("ORACLE_SANDBOX") != "1":
            pytest.skip("Teste ignorado: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)")
