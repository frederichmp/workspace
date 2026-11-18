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
        "src_oracle_dba_importado": "src.tools.oracle_dba" in sys.modules,
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


if cfg.get("pre_importar_src"):
    # Cenário A3a: a cópia src.tools.oracle_dba é importada antes da entrada (e antes da carga do .env).
    import src.tools.oracle_dba  # noqa: F401

if cfg.get("raiz_em_error"):
    # C3: a raiz já configurada em ERROR antes da entrada (o log de WARNING fica suprimido).
    logging.basicConfig(level=logging.ERROR)
raiz_log = logging.getLogger()
raiz_log.addHandler(_Captura())
if not cfg.get("raiz_em_error"):
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
        "oracle_dsn_do_shell": os.environ.get("ORACLE_DSN") == "dsn_shell_ficticio",  # nunca imprime o valor
        "excecoes": excecoes,
        "warning_tela": [],
        "tela_texto": "",
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
        estado = _estado(excecoes)
        for at in ats:
            estado["warning_tela"].extend(str(w.value) for w in at.warning)
            estado["tela_texto"] += repr(at.main) + repr(at.sidebar)
        por_run.append(estado)
        apos = cfg.get("apos_run", {}).get(str(i))
        if apos is not None:
            with open(env_ficticio, "wb") as f:
                f.write(bytes.fromhex(apos))
except Exception as exc:  # erro do harness: aparece no JSON em vez de derrubar o filho
    excecoes_harness.append(type(exc).__name__ + ": " + str(exc) + " | " + traceback.format_exc()[-400:])

def _destino_log(nome):
    modulo = sys.modules.get(nome)
    try:
        return None if modulo is None else str(modulo._caminho_log_efetivo(None))  # só resolve; nunca grava
    except Exception as exc:
        return "erro " + type(exc).__name__

final = _estado([])
print("\n" + json.dumps({
    "sandbox": final["sandbox"],
    "sentinela": final["sentinela"],
    "sentinela_fase3": final["sentinela_fase3"],
    "sentinela_tardia": final["sentinela_tardia"],
    "por_run": por_run,
    "oracle_dsn_do_shell": final["oracle_dsn_do_shell"],
    "log_total": [m for n, m in capturados],
    "avisos": [m for n, m in capturados if n == "WARNING"],
    "chamadas": chamadas,
    "chamadas_values": chamadas_values,
    "leituras_reais": leituras_reais,
    "excecoes_harness": excecoes_harness,
    "destino_log": {"src": _destino_log("src.tools.oracle_dba"), "tools": _destino_log("tools.oracle_dba")},
}))
"""

MENSAGEM_FALHA_CARGA = "Carga do .env falhou"


def _rodar(
    entrada, tmp_path, conteudo_env, sandbox_shell=None, runs=1, sessoes=1, apos_run=None,
    sem_log_dir=False, pre_importar_src=False, env_extra=None, raiz_em_error=False,
):
    """Roda a entrada em subprocesso. `conteudo_env` e os valores de `apos_run` ({índice_do_run: conteúdo})
    aceitam str ou bytes; `apos_run` regrava o fictício depois do run indicado (alteração em disco).
    `sem_log_dir` tira AGENTDBA_LOG_DIR do ambiente do filho; `pre_importar_src` importa
    src.tools.oracle_dba antes da entrada; `env_extra` acrescenta variáveis ao ambiente do filho (depois do
    filtro de prefixos); `raiz_em_error` chama logging.basicConfig(level=ERROR) antes da entrada."""
    def _bytes(c):
        return c if isinstance(c, bytes) else c.encode("utf-8")

    env_ficticio = tmp_path / "ficticio.env"
    env_ficticio.write_bytes(_bytes(conteudo_env))
    cfg = {
        "runs": runs,
        "sessoes": sessoes,
        "pre_importar_src": pre_importar_src,
        "raiz_em_error": raiz_em_error,
        "apos_run": {str(i): _bytes(c).hex() for i, c in (apos_run or {}).items()},
    }
    env = {k: v for k, v in os.environ.items() if not k.startswith(_PREFIXOS)}
    if sem_log_dir:
        env.pop("AGENTDBA_LOG_DIR", None)
    else:
        env["AGENTDBA_LOG_DIR"] = str(tmp_path / "log")
    env["SCRIPTS_REGISTRY_PATH"] = str(RAIZ / "registry" / "test_scripts.yaml")
    if sandbox_shell is not None:
        env["ORACLE_SANDBOX"] = sandbox_shell
    env.update(env_extra or {})
    env["PYTHONIOENCODING"] = "utf-8"
    res = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ), entrada, str(env_ficticio), json.dumps(cfg)],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=180, cwd=str(RAIZ),
    )
    ultima = (res.stderr.strip().splitlines() or [""])[-1]
    assert res.returncode == 0, f"subprocesso falhou (returncode={res.returncode}): {ultima}"
    dados = json.loads(res.stdout.strip().splitlines()[-1])
    assert dados["excecoes_harness"] == [], f"erro do harness: {dados['excecoes_harness']}"
    dados["stderr"] = res.stderr
    dados["stdout_resto"] = "\n".join(res.stdout.strip().splitlines()[:-1])  # tudo menos o JSON final
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


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_a3_src_tools_antes_da_entrada_mesmo_destino(entrada, tmp_path):
    """A3a: src.tools.oracle_dba importada antes da entrada resolve o mesmo destino de log que tools.oracle_dba.

    O filho não tem AGENTDBA_LOG_DIR no ambiente; o fictício o define. Só resolve o destino, nunca grava o
    log (em d05577e a cópia src aponta para C:/AgentDBA/logs e uma gravação criaria a pasta real).
    """
    dir_env = tmp_path / "dir_env"
    esperado = dir_env / "kill_approval.log"
    agentdba_existia = Path("C:/AgentDBA").exists()
    dados = _rodar(
        entrada, tmp_path, f"AGENTDBA_LOG_DIR={dir_env.as_posix()}\n",
        sem_log_dir=True, pre_importar_src=True,
    )
    destinos = dados["destino_log"]
    resumo = f"destino_log={destinos}, esperado={esperado}, chamadas={dados['chamadas']}"
    assert destinos["src"] is not None and Path(destinos["src"]) == esperado, resumo
    assert destinos["tools"] is not None and Path(destinos["tools"]) == esperado, resumo
    assert [c["src_oracle_dba_importado"] for c in dados["chamadas"]] == [True], resumo  # cenário do A3a
    assert not dir_env.exists()
    assert Path("C:/AgentDBA").exists() == agentdba_existia
    assert dados["leituras_reais"] == []


# Contrato de produção (decisao_fase3.md, P1 e P3c). Textos fixos, sem valor do .env.
_TEXTO_DESCARTE = (
    "ORACLE_SANDBOX encontrada no .env foi DESCARTADA: só vale quando definida pelo operador no shell. "
    "Remova a chave do .env."
)
_PREFIXO_SOMBREADAS = "Variáveis do .env ignoradas porque o ambiente já as define com outro valor: "
_PREFIXO_CLI = "[Sistema]: AVISO: "


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_b3_nomes_sombreados_sem_valores(entrada, tmp_path):
    """B3: chave do .env sombreada pelo ambiente com outro valor é avisada só pelo nome, nunca pelo valor."""
    dados = _rodar(
        entrada, tmp_path,
        "ORACLE_DSN=dsn_arquivo_ficticio\nSENTINELA_IGUAL=igual\nSENTINELA_FASE3=1\n",
        env_extra={"ORACLE_DSN": "dsn_shell_ficticio", "SENTINELA_IGUAL": "igual"},
    )
    resumo = f"avisos={dados['avisos']}, stderr={dados['stderr']!r}, por_run={dados['por_run']}"
    sombreados = [a for a in dados["avisos"] if "ORACLE_DSN" in a]
    assert len(sombreados) == 1, resumo
    assert "SENTINELA_IGUAL" not in sombreados[0], resumo
    assert _PREFIXO_SOMBREADAS in sombreados[0] and "DESCARTADA" not in sombreados[0], resumo
    log_total = "\n".join(dados["log_total"])
    tela = dados["por_run"][0]["tela_texto"]
    assert "dsn_" not in log_total and "dsn_" not in dados["stdout_resto"], resumo
    assert "dsn_" not in dados["stderr"] and "dsn_" not in tela, resumo
    assert dados["oracle_dsn_do_shell"] is True, resumo  # o valor do shell prevaleceu
    if entrada == "cli":
        assert _PREFIXO_CLI + _PREFIXO_SOMBREADAS in dados["stderr"], resumo
        assert "ORACLE_DSN" in dados["stderr"].split(_PREFIXO_SOMBREADAS, 1)[-1], resumo
    else:
        assert any("ORACLE_DSN" in w and _PREFIXO_SOMBREADAS in w for w in dados["por_run"][0]["warning_tela"]), resumo
    assert len(dados["chamadas_values"]) == 1, resumo
    assert Path(dados["chamadas_values"][0]["caminho"]) == RAIZ / ".env", resumo
    assert dados["leituras_reais"] == []


def test_c3_cli_aviso_em_stderr(tmp_path):
    """C3: o descarte de ORACLE_SANDBOX aparece uma vez no stderr da CLI, além do log."""
    dados = _rodar("cli", tmp_path, "ORACLE_SANDBOX=1\nSENTINELA_FASE3=1\n")
    resumo = f"stderr={dados['stderr']!r}, avisos={dados['avisos']}"
    assert dados["stderr"].count(_PREFIXO_CLI + _TEXTO_DESCARTE) == 1, resumo
    assert dados["sandbox"] == "AUSENTE", resumo
    assert dados["leituras_reais"] == []


def test_c3_cli_aviso_com_raiz_em_error(tmp_path):
    """C3: com o logger raiz em ERROR (WARNING suprimido) o aviso ainda chega ao stderr da CLI."""
    dados = _rodar("cli", tmp_path, "ORACLE_SANDBOX=1\nSENTINELA_FASE3=1\n", raiz_em_error=True)
    resumo = f"stderr={dados['stderr']!r}, avisos={dados['avisos']}"
    assert _TEXTO_DESCARTE in dados["stderr"], resumo
    assert dados["sandbox"] == "AUSENTE", resumo
    assert dados["leituras_reais"] == []


def test_c3_web_st_warning_em_todo_rerun(tmp_path):
    """C3: na Web o aviso de descarte é um st.warning visível em todo rerun, não só no primeiro."""
    dados = _rodar("web", tmp_path, "ORACLE_SANDBOX=1\nSENTINELA_FASE3=1\n", runs=2)
    resumo = f"por_run={[r['warning_tela'] for r in dados['por_run']]}"
    assert len(dados["por_run"]) == 2, resumo
    for run in dados["por_run"]:
        assert any(_TEXTO_DESCARTE in w for w in run["warning_tela"]), resumo
    assert dados["sandbox"] == "AUSENTE", resumo
    assert dados["leituras_reais"] == []
