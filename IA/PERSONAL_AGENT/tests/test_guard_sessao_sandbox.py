"""Caracterização do guard existente `pytest_sessionfinish` de tests/conftest.py (ORACLE_SANDBOX).

Não altera produção nem o conftest e não usa sandbox: ORACLE_SANDBOX só recebe "0" ou fica ausente
(nunca "1"), sempre por monkeypatch restaurado no teardown, para o guard real do fim da sessão não disparar.
"""
import json
import os
import subprocess
import sys
import types

import pytest

import tests.conftest as conftest


def _preparar(monkeypatch, tmp_path, operador, inicio, tomado, env):
    assert sys.modules["tests.conftest"] is conftest
    # Evita apagar o diretório de log da sessão real (shutil.rmtree no fim da função).
    monkeypatch.setattr(conftest, "_DIR_LOG_TESTE", str(tmp_path / "dir_log_falso"))
    # Neutraliza os checks de log real: só o guard de ORACLE_SANDBOX pode mudar o exitstatus.
    monkeypatch.setattr(conftest, "SNAPSHOT_LOG_REAL_INICIO", conftest._snapshot_log_real())
    monkeypatch.setattr(
        conftest, "SNAPSHOT_LOG_PADRAO_INICIO", conftest._snapshot_arquivo(conftest.LOG_PADRAO_PRODUCAO)
    )
    monkeypatch.setattr(conftest, "PASTA_PADRAO_EXISTIA_NO_INICIO", conftest.PASTA_PADRAO_PRODUCAO.exists())
    monkeypatch.setattr(conftest, "ORACLE_SANDBOX_DO_OPERADOR", operador)
    monkeypatch.setattr(conftest, "ORACLE_SANDBOX_INICIO_SESSAO", inicio)
    monkeypatch.setattr(conftest, "_SNAPSHOT_SESSAO_TOMADO", tomado)
    if env is None:
        monkeypatch.delenv("ORACLE_SANDBOX", raising=False)
    else:
        assert env == "0"
        monkeypatch.setenv("ORACLE_SANDBOX", env)
    sessao = types.SimpleNamespace(exitstatus=0)
    conftest.pytest_sessionfinish(sessao, 0)
    return sessao


@pytest.mark.parametrize(
    "operador, inicio, tomado, env",
    [
        (None, None, True, None),   # a) sem mudança
        (None, None, False, None),  # e) snapshot não tomado
    ],
    ids=["sem_mudanca", "snapshot_nao_tomado"],
)
def test_guard_sem_mudanca_nao_falha(monkeypatch, tmp_path, capsys, operador, inicio, tomado, env):
    sessao = _preparar(monkeypatch, tmp_path, operador, inicio, tomado, env)
    assert sessao.exitstatus == 0
    assert "ORACLE_SANDBOX" not in capsys.readouterr().out


def test_guard_sandbox_aparece_durante_sessao(monkeypatch, tmp_path, capsys):
    sessao = _preparar(monkeypatch, tmp_path, None, None, True, "0")
    saida = capsys.readouterr().out
    assert sessao.exitstatus == 1
    assert "FALHA DE GOVERNANCA: ORACLE_SANDBOX mudou durante a sessão" in saida
    assert "início: ausente" in saida
    assert "fim: presente" in saida
    assert "=0" not in saida and "'0'" not in saida


def test_guard_sandbox_some_durante_sessao(monkeypatch, tmp_path, capsys):
    sessao = _preparar(monkeypatch, tmp_path, "0", "0", True, None)
    saida = capsys.readouterr().out
    assert sessao.exitstatus == 1
    assert "FALHA DE GOVERNANCA: ORACLE_SANDBOX mudou durante a sessão" in saida
    assert "início: presente" in saida
    assert "fim: ausente" in saida


def test_guard_diverge_so_do_inicio_da_sessao(monkeypatch, tmp_path, capsys):
    sessao = _preparar(monkeypatch, tmp_path, "0", None, True, "0")
    assert sessao.exitstatus == 1
    assert "FALHA DE GOVERNANCA: ORACLE_SANDBOX mudou durante a sessão" in capsys.readouterr().out


# --- D6.4: a fixture guard_oracle_sandbox (aborta a sessão se ORACLE_SANDBOX mudou antes do início) ---

def _corpo_da_fixture_guard():
    """Função geradora subjacente à fixture (pytest 9: FixtureFunctionDefinition)."""
    fixture = conftest.guard_oracle_sandbox
    if hasattr(fixture, "_get_wrapped_function"):
        return fixture._get_wrapped_function()
    return fixture.__wrapped__


def _isolar_globais_da_fixture(monkeypatch, operador):
    # A fixture grava estes dois globais; o monkeypatch registra antes para o teardown restaurá-los.
    monkeypatch.setattr(conftest, "ORACLE_SANDBOX_DO_OPERADOR", operador)
    monkeypatch.setattr(conftest, "ORACLE_SANDBOX_INICIO_SESSAO", None)
    monkeypatch.setattr(conftest, "_SNAPSHOT_SESSAO_TOMADO", False)


def test_fixture_guard_sai_quando_operador_tinha_e_ambiente_nao_tem(monkeypatch):
    _isolar_globais_da_fixture(monkeypatch, "0")
    monkeypatch.delenv("ORACLE_SANDBOX", raising=False)
    gen = _corpo_da_fixture_guard()()
    with pytest.raises(pytest.exit.Exception) as exc:
        next(gen)
    assert exc.value.returncode == 3
    assert "FALHA DE GOVERNANCA: ORACLE_SANDBOX alterado entre o início do processo e o início da sessão" in exc.value.msg
    assert "operador: presente, atual: ausente" in exc.value.msg
    assert "Nenhum teste executado" in exc.value.msg
    assert conftest._SNAPSHOT_SESSAO_TOMADO is False  # não chegou a tomar o snapshot


def test_fixture_guard_sai_quando_ambiente_tem_e_operador_nao_tinha(monkeypatch):
    _isolar_globais_da_fixture(monkeypatch, None)
    monkeypatch.setenv("ORACLE_SANDBOX", "0")
    gen = _corpo_da_fixture_guard()()
    with pytest.raises(pytest.exit.Exception) as exc:
        next(gen)
    assert exc.value.returncode == 3
    assert "operador: ausente, atual: presente" in exc.value.msg
    assert "'0'" not in exc.value.msg and "=0" not in exc.value.msg  # nunca o valor
    assert conftest._SNAPSHOT_SESSAO_TOMADO is False


@pytest.mark.parametrize("valor", [None, "0"], ids=["ausente", "zero"])
def test_fixture_guard_sem_divergencia_nao_sai_e_toma_o_snapshot(monkeypatch, valor):
    _isolar_globais_da_fixture(monkeypatch, valor)
    if valor is None:
        monkeypatch.delenv("ORACLE_SANDBOX", raising=False)
    else:
        monkeypatch.setenv("ORACLE_SANDBOX", valor)
    gen = _corpo_da_fixture_guard()()
    next(gen)  # chegou ao yield: não saiu
    assert conftest._SNAPSHOT_SESSAO_TOMADO is True
    assert conftest.ORACLE_SANDBOX_INICIO_SESSAO == valor
    gen.close()


_SCRIPT_OPERADOR = r"""
import json, runpy, sys
ns = runpy.run_path(sys.argv[1])
print(json.dumps({"operador_visto": ns["ORACLE_SANDBOX_DO_OPERADOR"]}))
"""


@pytest.mark.parametrize("sandbox_shell", [None, "0"], ids=["ausente", "zero"])
def test_operador_e_lido_do_ambiente_no_inicio_do_processo(tmp_path, sandbox_shell):
    """ORACLE_SANDBOX_DO_OPERADOR reflete o ambiente do processo (não um valor fixo), em subprocesso.

    O valor "1" nunca é usado. O mkdtemp do conftest do filho cai em tmp_path. Sem operador "1", o
    conftest não lê nenhum .env.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ORACLE_", "EMAIL_", "GEMINI_"))}
    (tmp_path / "tmp").mkdir()
    env["TEMP"] = env["TMP"] = str(tmp_path / "tmp")
    if sandbox_shell is not None:
        assert sandbox_shell == "0"
        env["ORACLE_SANDBOX"] = sandbox_shell
    res = subprocess.run(
        [sys.executable, "-c", _SCRIPT_OPERADOR, conftest.__file__],
        capture_output=True, text=True, env=env, timeout=120, cwd=str(tmp_path),
    )
    ultima = (res.stderr.strip().splitlines() or [""])[-1]
    assert res.returncode == 0, f"subprocesso falhou (returncode={res.returncode}): {ultima}"
    assert json.loads(res.stdout.strip().splitlines()[-1])["operador_visto"] == sandbox_shell


def test_guard_oracle_sandbox_e_autouse_e_de_sessao(request):
    """D6.4: a fixture guard_oracle_sandbox é autouse (aparece em fixturenames sem ser pedida) e tem escopo session."""
    assert "guard_oracle_sandbox" in request.fixturenames  # este teste não a pede: só o autouse a traz
    # fixturenames inclui dependências: o autouse `inicializar_registro_testes` pede a guard e a traria mesmo
    # sem autouse. A lista de autouse do nó (API interna do pytest 9, conferida) fecha essa brecha.
    assert "guard_oracle_sandbox" in set(request._fixturemanager._getautousenames(request.node))
    definicoes = request._fixturemanager.getfixturedefs("guard_oracle_sandbox", request.node)
    assert definicoes, "FixtureDef de guard_oracle_sandbox não encontrada"
    assert definicoes[-1].scope == "session"
