"""Caracterização do guard existente `pytest_sessionfinish` de tests/conftest.py (ORACLE_SANDBOX).

Não altera produção nem o conftest e não usa sandbox: ORACLE_SANDBOX só recebe "0" ou fica ausente
(nunca "1"), sempre por monkeypatch restaurado no teardown, para o guard real do fim da sessão não disparar.
"""
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
