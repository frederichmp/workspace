"""
Configuração global do Pytest para o Personal Agent.
Gerencia marcações de sandbox para proteção contra execuções não autorizadas
e carrega o registro de testes (registry/test_scripts.yaml).
"""

import os

# Valor de ORACLE_SANDBOX definido pelo operador antes do início do processo; nada do conftest nem dos testes executou ainda.
ORACLE_SANDBOX_DO_OPERADOR = os.environ.get("ORACLE_SANDBOX")

import shutil
import sys
import tempfile
from pathlib import Path

# ATENÇÃO: definido ANTES de qualquer import de código de produção. O diretório do log de aprovações
# (AGENTDBA_LOG_DIR) aponta para um diretório temporário em %TEMP% (fora do OneDrive), de modo que
# nenhum teste grave em C:\AgentDBA nem em data/logs/ do repositório.
_DIR_LOG_TESTE = tempfile.mkdtemp(prefix="agentdba_test_")
os.environ["AGENTDBA_LOG_DIR"] = _DIR_LOG_TESTE

import pytest

# Configura SCRIPTS_REGISTRY_PATH para apontar para test_scripts.yaml durante os testes (L8)
test_registry_path = Path(__file__).resolve().parent.parent / "registry" / "test_scripts.yaml"
if test_registry_path.is_file():
    os.environ["SCRIPTS_REGISTRY_PATH"] = str(test_registry_path)


ORACLE_SANDBOX_INICIO_SESSAO = None
_SNAPSHOT_SESSAO_TOMADO = False


def _estado_sandbox(valor):
    return "ausente" if valor is None else "presente"


@pytest.fixture(scope="session", autouse=True)
def guard_oracle_sandbox():
    """Aborta a sessão se ORACLE_SANDBOX mudou entre o início do processo e o início da sessão."""
    global ORACLE_SANDBOX_INICIO_SESSAO, _SNAPSHOT_SESSAO_TOMADO
    atual = os.environ.get("ORACLE_SANDBOX")
    if atual != ORACLE_SANDBOX_DO_OPERADOR:
        pytest.exit(
            "FALHA DE GOVERNANCA: ORACLE_SANDBOX alterado entre o início do processo e o início da sessão "
            f"(operador: {_estado_sandbox(ORACLE_SANDBOX_DO_OPERADOR)}, atual: {_estado_sandbox(atual)}). "
            "Nenhum teste executado.",
            returncode=3,
        )
    ORACLE_SANDBOX_INICIO_SESSAO = atual
    _SNAPSHOT_SESSAO_TOMADO = True
    yield


@pytest.fixture(scope="session", autouse=True)
def inicializar_registro_testes(guard_oracle_sandbox):
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

# Padrão de produção (DIRETORIO_LOG_PADRAO): a suíte não pode criar a pasta nem alterar o log.
PASTA_PADRAO_PRODUCAO = Path(r"C:\AgentDBA")
LOG_PADRAO_PRODUCAO = Path(r"C:\AgentDBA\logs\kill_approval.log")


def _snapshot_arquivo(caminho):
    """Retorna (existe, tamanho, mtime_ns) usando apenas stat (sem ler conteúdo)."""
    try:
        st = caminho.stat()
    except OSError:
        return (False, None, None)
    return (True, st.st_size, st.st_mtime_ns)


SNAPSHOT_LOG_PADRAO_INICIO = _snapshot_arquivo(LOG_PADRAO_PRODUCAO)
PASTA_PADRAO_EXISTIA_NO_INICIO = PASTA_PADRAO_PRODUCAO.exists()


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
    final_sandbox = os.environ.get("ORACLE_SANDBOX")
    if final_sandbox != ORACLE_SANDBOX_DO_OPERADOR or (
        _SNAPSHOT_SESSAO_TOMADO and final_sandbox != ORACLE_SANDBOX_INICIO_SESSAO
    ):
        print(
            "\nFALHA DE GOVERNANCA: ORACLE_SANDBOX mudou durante a sessão de testes "
            f"(início: {_estado_sandbox(ORACLE_SANDBOX_INICIO_SESSAO if _SNAPSHOT_SESSAO_TOMADO else ORACLE_SANDBOX_DO_OPERADOR)}, "
            f"fim: {_estado_sandbox(final_sandbox)})."
        )
        session.exitstatus = 1

    final = _snapshot_log_real()
    if final != SNAPSHOT_LOG_REAL_INICIO:
        print(
            "\nFALHA DE GOVERNANCA: data/logs/kill_approval.log real foi alterado durante a sessão "
            f"de testes (início={SNAPSHOT_LOG_REAL_INICIO}, fim={final})."
        )
        session.exitstatus = 1

    final_padrao = _snapshot_arquivo(LOG_PADRAO_PRODUCAO)
    if final_padrao != SNAPSHOT_LOG_PADRAO_INICIO:
        print(
            "\nFALHA DE GOVERNANCA: C:\\AgentDBA\\logs\\kill_approval.log foi alterado durante a sessão "
            f"de testes (início={SNAPSHOT_LOG_PADRAO_INICIO}, fim={final_padrao})."
        )
        session.exitstatus = 1
    if not PASTA_PADRAO_EXISTIA_NO_INICIO and PASTA_PADRAO_PRODUCAO.exists():
        print("\nFALHA DE GOVERNANCA: a suíte de testes criou C:\\AgentDBA.")
        session.exitstatus = 1

    shutil.rmtree(_DIR_LOG_TESTE, ignore_errors=True)


def pytest_runtest_setup(item):
    if "sandbox_only" in item.keywords:
        if os.getenv("ORACLE_SANDBOX") != "1":
            pytest.skip("Teste ignorado: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)")
