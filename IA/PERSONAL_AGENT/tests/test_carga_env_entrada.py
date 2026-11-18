"""Fases 2 e 3 (D1/D2, B4, C1, C2a, R-F2-1): a carga do .env nas entradas (src/main.py e app.py).

REGRA DE SEGURANÇA (incidente 01:27): o .env fictício com ORACLE_SANDBOX=1 só é lido DENTRO DE SUBPROCESSO
sem credenciais (nenhuma chave ORACLE_/EMAIL_/GEMINI_ herdada). O processo do pytest nunca tem
ORACLE_SANDBOX alterada. O .env real nunca é lido: no filho, load_dotenv e dotenv_values são
redirecionados para o arquivo fictício e um guarda em dotenv.main.DotEnv.__init__ registra (e recusa com
AssertionError) qualquer leitura que resolva para RAIZ/.env; todo teste afirma `leituras_reais == []`.
O filho sempre imprime o JSON, mesmo quando a entrada levanta exceção. Nenhum teste lê ou grava o estado
privado das entradas (`_personal_agent_estado_env`): tudo é observado de fora, em subprocesso.
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
import json, logging, os, socket, sys, traceback
raiz, entrada, env_ficticio, cfg_json = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
cfg = json.loads(cfg_json)
sys.path.insert(0, raiz)
sys.path.insert(0, os.path.join(raiz, "src"))

import dotenv
import dotenv.main

chamadas = []          # load_dotenv: (caminho recebido, override)
chamadas_values = []   # dotenv_values: (caminho recebido)
leituras_reais = []    # qualquer DotEnv(...) que resolva para RAIZ/.env

_original = dotenv.load_dotenv
_original_values = dotenv.dotenv_values
_init_original = dotenv.main.DotEnv.__init__
_real = os.path.normcase(os.path.realpath(os.path.join(raiz, ".env")))


def _wrapper(dotenv_path=None, *args, **kwargs):
    chamadas.append({
        "caminho": None if dotenv_path is None else str(dotenv_path),
        "override": kwargs["override"] if "override" in kwargs else "AUSENTE",
    })
    kwargs.setdefault("override", False)
    return _original(env_ficticio, *args, **kwargs)


def _wrapper_values(dotenv_path=None, *args, **kwargs):
    chamadas_values.append({"caminho": None if dotenv_path is None else str(dotenv_path)})
    return _original_values(env_ficticio, *args, **kwargs)


def _guarda_init(self, *args, **kwargs):
    caminho = kwargs["dotenv_path"] if "dotenv_path" in kwargs else (args[0] if args else None)
    if caminho is not None and not hasattr(caminho, "read"):
        try:
            alvo = os.path.normcase(os.path.realpath(os.fspath(caminho)))
        except Exception:
            alvo = None
        if alvo == _real:
            leituras_reais.append(str(caminho))
            raise AssertionError("leitura do .env real bloqueada pelo guarda do teste")
    return _init_original(self, *args, **kwargs)


dotenv.load_dotenv = _wrapper
dotenv.dotenv_values = _wrapper_values
dotenv.main.DotEnv.__init__ = _guarda_init

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

por_run = []       # um item por run: estado do ambiente e exceções depois do run
excecoes_harness = []


def _estado(excecoes):
    return {
        "sandbox": os.environ.get("ORACLE_SANDBOX", "AUSENTE"),
        "sentinela": os.environ.get("SENTINELA_FASE2", "AUSENTE"),
        "sentinela_fase3": os.environ.get("SENTINELA_FASE3", "AUSENTE"),
        "sentinela_tardia": os.environ.get("SENTINELA_TARDIA_FASE3", "AUSENTE"),
        "excecoes": excecoes,
    }


try:
    ats = []
    if entrada == "web":
        from streamlit.testing.v1 import AppTest
        for _ in range(cfg.get("sessoes", 1)):
            ats.append(AppTest.from_file(os.path.join(raiz, "app.py"), default_timeout=30))
    for i in range(cfg.get("runs", 1)):
        excecoes = []
        if entrada == "cli":
            sys.modules.pop("main", None)  # reimport: simula nova subida da entrada no mesmo processo
            try:
                import main  # noqa: F401
            except Exception as exc:
                excecoes.append(type(exc).__name__ + ": " + str(exc))
        else:
            for at in ats:
                try:
                    at.run()
                except Exception as exc:
                    excecoes.append("harness " + type(exc).__name__ + ": " + str(exc))
                excecoes.extend(type(e).__name__ + ": " + str(e.value) for e in at.exception)
        por_run.append(_estado(excecoes))
        apos = cfg.get("apos_run", {}).get(str(i))
        if apos is not None:
            with open(env_ficticio, "wb") as f:
                f.write(bytes.fromhex(apos))
except Exception as exc:  # erro do harness: aparece no JSON em vez de derrubar o filho
    excecoes_harness.append(type(exc).__name__ + ": " + str(exc) + " | " + traceback.format_exc()[-400:])

final = _estado([])
print("\n" + json.dumps({
    "sandbox": final["sandbox"],
    "sentinela": final["sentinela"],
    "sentinela_fase3": final["sentinela_fase3"],
    "sentinela_tardia": final["sentinela_tardia"],
    "por_run": por_run,
    "avisos": [m for n, m in capturados if n == "WARNING"],
    "chamadas": chamadas,
    "chamadas_values": chamadas_values,
    "leituras_reais": leituras_reais,
    "excecoes_harness": excecoes_harness,
}))
"""

MENSAGEM_FALHA_CARGA = "Carga do .env falhou"


def _rodar(entrada, tmp_path, conteudo_env, sandbox_shell=None, runs=1, sessoes=1, apos_run=None):
    """Roda a entrada em subprocesso. `conteudo_env` e os valores de `apos_run` ({índice_do_run: conteúdo})
    aceitam str ou bytes; `apos_run` regrava o fictício depois do run indicado (alteração em disco)."""
    def _bytes(c):
        return c if isinstance(c, bytes) else c.encode("utf-8")

    env_ficticio = tmp_path / "ficticio.env"
    env_ficticio.write_bytes(_bytes(conteudo_env))
    cfg = {
        "runs": runs,
        "sessoes": sessoes,
        "apos_run": {str(i): _bytes(c).hex() for i, c in (apos_run or {}).items()},
    }
    env = {k: v for k, v in os.environ.items() if not k.startswith(_PREFIXOS)}
    env["AGENTDBA_LOG_DIR"] = str(tmp_path / "log")
    env["SCRIPTS_REGISTRY_PATH"] = str(RAIZ / "registry" / "test_scripts.yaml")
    if sandbox_shell is not None:
        env["ORACLE_SANDBOX"] = sandbox_shell
    res = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ), entrada, str(env_ficticio), json.dumps(cfg)],
        capture_output=True, text=True, env=env, timeout=180, cwd=str(RAIZ),
    )
    ultima = (res.stderr.strip().splitlines() or [""])[-1]
    assert res.returncode == 0, f"subprocesso falhou (returncode={res.returncode}): {ultima}"
    dados = json.loads(res.stdout.strip().splitlines()[-1])
    assert dados["excecoes_harness"] == [], f"erro do harness: {dados['excecoes_harness']}"
    return dados


def _falha_fixa(excecoes):
    return any(MENSAGEM_FALHA_CARGA in e for e in excecoes)


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
    assert dados["leituras_reais"] == []


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_oracle_sandbox_do_shell_prevalece(entrada, tmp_path):
    dados = _rodar(entrada, tmp_path, "ORACLE_SANDBOX=1\n", sandbox_shell="0")
    resumo = f"sandbox={dados['sandbox']}, avisos={dados['avisos']}"
    assert dados["sandbox"] == "0", resumo
    assert not [a for a in dados["avisos"] if "DESCARTADA" in a], resumo
    assert dados["leituras_reais"] == []


def test_b4_web_chave_nova_entre_reruns_nao_entra(tmp_path):
    """B4: chave acrescentada ao .env entre dois reruns do AppTest não entra no processo."""
    dados = _rodar(
        "web", tmp_path, "SENTINELA_FASE3=1\n", runs=2,
        apos_run={0: "SENTINELA_FASE3=1\nSENTINELA_TARDIA_FASE3=1\n"},
    )
    resumo = f"por_run={dados['por_run']}, chamadas={dados['chamadas']}"
    assert dados["sentinela_tardia"] == "AUSENTE", resumo
    assert len(dados["chamadas"]) == 1, resumo
    assert dados["leituras_reais"] == []


_ENV_COM_NUL = b"ORACLE_SANDBOX=1\nSENTINELA_FASE3=1\nVALOR_NUL_FICTICIO=a\x00b\n"


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_c1_nul_nao_deixa_oracle_sandbox(entrada, tmp_path):
    """C1: .env com byte NUL: a carga aborta e ORACLE_SANDBOX do arquivo não fica no processo (2 tentativas)."""
    dados = _rodar(entrada, tmp_path, _ENV_COM_NUL, runs=2)
    resumo = f"por_run={dados['por_run']}, chamadas={dados['chamadas']}"
    assert len(dados["por_run"]) == 2, resumo
    assert [r["sandbox"] for r in dados["por_run"]] == ["AUSENTE", "AUSENTE"], resumo
    assert all(_falha_fixa(r["excecoes"]) for r in dados["por_run"]), resumo
    assert len(dados["chamadas"]) == 1, resumo
    assert dados["leituras_reais"] == []


@pytest.mark.parametrize("entrada", ["web", "cli"])
def test_c2a_rerun_apos_falha_nao_promove_a_shell(entrada, tmp_path):
    """C2a: depois de falha por NUL, tirar a linha NUL e repetir não promove ORACLE_SANDBOX a 'do shell'."""
    dados = _rodar(
        entrada, tmp_path, _ENV_COM_NUL, runs=2,
        apos_run={0: b"ORACLE_SANDBOX=1\nSENTINELA_FASE3=1\n"},
    )
    resumo = f"por_run={dados['por_run']}, chamadas={dados['chamadas']}"
    assert len(dados["por_run"]) == 2, resumo
    assert dados["por_run"][1]["sandbox"] == "AUSENTE", resumo
    assert _falha_fixa(dados["por_run"][1]["excecoes"]), resumo  # fail-closed: o run 2 mantém o erro fixo
    assert len(dados["chamadas"]) == 1, resumo
    assert dados["leituras_reais"] == []


def test_r_f2_1_duas_sessoes_uma_carga(tmp_path):
    """R-F2-1: duas instâncias de AppTest no mesmo processo carregam o .env uma única vez.

    A intercalação entre threads não é testável de forma determinística; fica fechada por construção
    (lock e retrato único) e isso é declarado no GOVERNANCA_LOG.
    """
    dados = _rodar("web", tmp_path, "ORACLE_SANDBOX=1\nSENTINELA_FASE3=1\n", sessoes=2)
    resumo = f"sandbox={dados['sandbox']}, chamadas={dados['chamadas']}, por_run={dados['por_run']}"
    assert len(dados["chamadas"]) == 1, resumo
    assert dados["sandbox"] == "AUSENTE", resumo
    assert dados["leituras_reais"] == []
