"""Fases 2 e 3 (D1/D2, B4, C1, C2a, R-F2-1): a carga do .env nas entradas (src/main.py e app.py).

REGRA DE SEGURANÇA (incidente 01:27): o .env fictício com ORACLE_SANDBOX=1 só é lido DENTRO DE SUBPROCESSO
sem credenciais (nenhuma chave ORACLE_/EMAIL_/GEMINI_ herdada). O processo do pytest nunca tem
ORACLE_SANDBOX alterada. O .env real nunca é lido: no filho, o helper tests/_guarda_env.py redireciona
open/io.open/os.stat de RAIZ/.env para o arquivo fictício e recusa (LeituraEnvRealBloqueada) qualquer DotEnv do
real; load_dotenv e dotenv_values chamados com caminho (b0ce169) também vão ao fictício, e com stream (fase 4)
passam intactos. Todo teste afirma `leituras_reais == []`.
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

import builtins
import io as _io

from tests._guarda_env import instalar, mesmo_arquivo, LeituraEnvRealBloqueada  # noqa: F401  (raiz no sys.path)

_original = dotenv.load_dotenv
_original_values = dotenv.dotenv_values


def _wrapper(dotenv_path=None, *args, **kwargs):
    # H1 (fase 4): com stream, os argumentos passam intactos (a produção já leu o fictício pelo open
    # redirecionado); sem stream (b0ce169), o caminho continua trocado pelo fictício.
    com_stream = kwargs.get("stream") is not None
    chamadas.append({
        "caminho": None if dotenv_path is None else str(dotenv_path),
        "stream": com_stream,
        "override": kwargs["override"] if "override" in kwargs else "AUSENTE",
        "src_oracle_dba_importado": "src.tools.oracle_dba" in sys.modules,
    })
    kwargs.setdefault("override", False)
    return _original(dotenv_path if com_stream else env_ficticio, *args, **kwargs)


def _wrapper_values(dotenv_path=None, *args, **kwargs):
    com_stream = kwargs.get("stream") is not None
    chamadas_values.append({"caminho": None if dotenv_path is None else str(dotenv_path), "stream": com_stream})
    return _original_values(dotenv_path if com_stream else env_ficticio, *args, **kwargs)


dotenv.load_dotenv = _wrapper
dotenv.dotenv_values = _wrapper_values

# H2/H3 (fase 4): contagem das leituras efetivas do fictício (toda abertura cujo alvo final é o fictício,
# redirecionada pelo helper ou direta) e injeções de falha configuráveis, uma vez cada. Instalado ANTES do
# helper, para que as aberturas redirecionadas também passem por aqui. Só caminho e contagem; nunca conteúdo.
class InterrupcaoSimulada(BaseException):
    pass


injecoes = cfg.get("injecoes", {})
disparos = {}
run_atual = [0]
leituras_efetivas = []  # índice do run de cada leitura efetiva do fictício
_open_base = builtins.open


def _open_contado(file, *args, **kwargs):
    if mesmo_arquivo(file, env_ficticio):
        leituras_efetivas.append(run_atual[0])
        falha = injecoes.get("leitura")
        if falha and not disparos.get("leitura"):
            disparos["leitura"] = True
            if falha == "BaseException":
                raise InterrupcaoSimulada("interrupção simulada na leitura")
            raise PermissionError(13, "lock simulado na leitura")
    return _open_base(file, *args, **kwargs)


builtins.open = _open_contado
_io.open = _open_contado

if injecoes.get("putenv"):
    _putenv_base = os.putenv

    def _putenv(chave, valor):
        if not disparos.get("putenv") and str(chave).upper() == injecoes["putenv"].upper():
            disparos["putenv"] = True
            raise OSError("putenv simulado")
        return _putenv_base(chave, valor)

    os.putenv = _putenv

if injecoes.get("unsetenv"):
    _unsetenv_base = os.unsetenv

    def _unsetenv(chave):
        if not disparos.get("unsetenv") and str(chave).upper() == injecoes["unsetenv"].upper():
            disparos["unsetenv"] = True
            raise OSError("unsetenv simulado")
        return _unsetenv_base(chave)

    os.unsetenv = _unsetenv
# Guarda do .env real (open/io.open/os.stat redirecionados ao fictício; DotEnv do real bloqueado). Os wrappers
# acima ainda redirecionam load_dotenv/dotenv_values; setattr simples basta (o processo é descartável).
registro = instalar(setattr, os.path.join(raiz, ".env"), env_ficticio)
leituras_reais = registro.leituras_env_reais  # qualquer leitura de RAIZ/.env (DotEnv, open, io.open)

capturados = []


eventos = []  # ordem de basicConfig e dos WARNINGs (D6.3b)


class _Captura(logging.Handler):
    def emit(self, record):
        capturados.append((record.levelname, record.getMessage()))
        if record.levelname == "WARNING":
            eventos.append(["WARNING", record.getMessage()])


if cfg.get("pre_importar_src"):
    # Cenário A3a: a cópia src.tools.oracle_dba é importada antes da entrada (e antes da carga do .env).
    import src.tools.oracle_dba  # noqa: F401

if cfg.get("raiz_em_error"):
    # C3: a raiz já configurada em ERROR antes da entrada (o log de WARNING fica suprimido).
    logging.basicConfig(level=logging.ERROR)
_basic_original = logging.basicConfig


def _basic_wrapper(*a, **k):
    eventos.append(["basicConfig"])
    return _basic_original(*a, **k)


logging.basicConfig = _basic_wrapper
raiz_log = logging.getLogger()
raiz_log.addHandler(_Captura())
if not cfg.get("raiz_em_error"):
    raiz_log.setLevel(logging.INFO)  # handlers existentes: basicConfig vira no-op, sem FileHandler novo


def _sem_rede(*a, **k):
    raise OSError("rede neutralizada no teste")


socket.create_connection = _sem_rede

por_run = []       # um item por run: estado do ambiente e exceções depois do run
excecoes_harness = []


aberturas_por_run = []  # por run: aberturas redirecionadas de open/io.open (só caminho original e tipo)
stats_por_run = []      # por run: quantos os.stat do .env real foram redirecionados ao fictício
_aberturas_vistas = 0
_stats_vistos = 0


def _aberturas_do_run():
    global _aberturas_vistas
    novas = [a for a in registro.aberturas_redirecionadas if a["tipo"] in ("open", "io.open")][_aberturas_vistas:]
    _aberturas_vistas += len(novas)
    return novas


def _stats_do_run():
    global _stats_vistos
    novos = [a for a in registro.aberturas_redirecionadas if a["tipo"] == "stat"][_stats_vistos:]
    _stats_vistos += len(novos)
    return len(novos)


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
        run_atual[0] = i
        excecoes = []
        if entrada == "cli":
            sys.modules.pop("main", None)  # reimport: simula nova subida da entrada no mesmo processo
            try:
                import main  # noqa: F401
            except Exception as exc:
                excecoes.append(type(exc).__name__ + ": " + str(exc))
            except InterrupcaoSimulada as exc:  # só nas configurações com injeção BaseException
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
        aberturas_por_run.append(_aberturas_do_run())
        stats_por_run.append(_stats_do_run())
        apos = cfg.get("apos_run", {}).get(str(i))
        if apos is not None:
            with _open_base(env_ficticio, "wb") as f:  # gravação do harness: não conta como leitura
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
    "eventos": eventos,
    "gemini_key_igual": None if sys.modules.get("tools.gemini_router") is None
        else sys.modules["tools.gemini_router"].GEMINI_API_KEY == "chave_ficticia_d63",  # só booleano
    "avisos": [m for n, m in capturados if n == "WARNING"],
    "chamadas": chamadas,
    "chamadas_values": chamadas_values,
    "leituras_reais": leituras_reais,
    "aberturas_por_run": aberturas_por_run,
    "stats_por_run": stats_por_run,
    "leituras_efetivas_por_run": [leituras_efetivas.count(i) for i in range(cfg.get("runs", 1))],
    "disparos": disparos,
    "excecoes_harness": excecoes_harness,
    "destino_log": {"src": _destino_log("src.tools.oracle_dba"), "tools": _destino_log("tools.oracle_dba")},
}))
"""

MENSAGEM_FALHA_CARGA = "Carga do .env falhou"


def _rodar(
    entrada, tmp_path, conteudo_env, sandbox_shell=None, runs=1, sessoes=1, apos_run=None,
    sem_log_dir=False, pre_importar_src=False, env_extra=None, raiz_em_error=False,
    ficticio_tipo="arquivo", injecoes=None,
):
    """Roda a entrada em subprocesso. `conteudo_env` e os valores de `apos_run` ({índice_do_run: conteúdo})
    aceitam str ou bytes; `apos_run` regrava o fictício depois do run indicado (alteração em disco).
    `sem_log_dir` tira AGENTDBA_LOG_DIR do ambiente do filho; `pre_importar_src` importa
    src.tools.oracle_dba antes da entrada; `env_extra` acrescenta variáveis ao ambiente do filho (depois do
    filtro de prefixos); `raiz_em_error` chama logging.basicConfig(level=ERROR) antes da entrada."""
    def _bytes(c):
        return c if isinstance(c, bytes) else c.encode("utf-8")

    env_ficticio = tmp_path / "ficticio.env"
    if ficticio_tipo == "arquivo":
        env_ficticio.write_bytes(_bytes(conteudo_env))
    elif ficticio_tipo == "diretorio":  # fase 4, Achado 3: .env que não é arquivo regular
        env_ficticio.mkdir()
    else:
        assert ficticio_tipo == "ausente", ficticio_tipo  # fase 4, P1: .env ausente
    cfg = {
        "injecoes": injecoes or {},  # fase 4 (H3): {"leitura": "PermissionError"|"BaseException", "putenv": nome, "unsetenv": nome}
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


# Fase 4 (decisao_fase4.md §1): as duas mensagens começam com MENSAGEM_FALHA_CARGA.
MENSAGEM_NOVA_TENTATIVA = "Nova tentativa na próxima subida"
MENSAGEM_REINICIE = "reinicie o processo"


def _unica_abertura_e_do_env_real(dados):
    """D3: em todo o processo, uma única abertura (open/io.open) do .env, e ela é de RAIZ/.env."""
    aberturas = [a for run in dados["aberturas_por_run"] for a in run]
    return (
        len(aberturas) == 1
        and Path(aberturas[0]["caminho"]) == RAIZ / ".env"
        and sum(dados["leituras_efetivas_por_run"]) == 1
    )


def _com(excecoes, *trechos):
    return any(all(t in e for t in trechos) for e in excecoes)


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
    # D3 (fase 4): a carga recebe o texto por stream; o caminho lido é provado pela única abertura registrada.
    assert chamada["caminho"] is None and chamada["stream"] is True, resumo
    assert _unica_abertura_e_do_env_real(dados), resumo
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
    # D3 (fase 4): dotenv_values recebe o texto por stream; o caminho lido é provado pela única abertura.
    assert dados["chamadas_values"][0]["caminho"] is None and dados["chamadas_values"][0]["stream"] is True, resumo
    assert _unica_abertura_e_do_env_real(dados), resumo
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


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_d63_valor_lido_no_import_prova_carga_antes_dos_imports(entrada, tmp_path):
    """D6.3a (I1): a carga do .env vem antes dos imports de `tools.*`.

    O fictício tem GEMINI_API_KEY; tools.gemini_router lê a chave no import. Só o booleano
    (igual/diferente) é registrado: a chave nunca é impressa.
    """
    dados = _rodar(entrada, tmp_path, "GEMINI_API_KEY=chave_ficticia_d63\nSENTINELA_FASE3=1\n")
    resumo = f"gemini_key_igual={dados['gemini_key_igual']}, sentinela_fase3={dados['sentinela_fase3']}"
    assert dados["gemini_key_igual"] is True, resumo
    assert dados["sentinela_fase3"] == "1", resumo  # o fictício foi carregado
    assert dados["leituras_reais"] == []


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_d63_warning_de_descarte_depois_do_basicconfig(entrada, tmp_path):
    """D6.3b (I3/D2): o WARNING de descarte de ORACLE_SANDBOX é emitido depois de logging.basicConfig."""
    dados = _rodar(entrada, tmp_path, "ORACLE_SANDBOX=1\nSENTINELA_FASE3=1\n")
    eventos = dados["eventos"]
    resumo = f"eventos={eventos}"
    idx_warn = [i for i, e in enumerate(eventos) if e[0] == "WARNING" and "DESCARTADA" in e[1]]
    idx_basic = [i for i, e in enumerate(eventos) if e[0] == "basicConfig"]
    assert len(idx_warn) == 1, resumo
    assert idx_basic and idx_basic[0] < idx_warn[0], resumo
    assert dados["leituras_reais"] == []


# --- Fase 4 (docs/entregas/isolamento_env/fase4/decisao_fase4.md §4; Achados 1 e 3; P1 = B) ---------------------
# Toda injeção é conferida antes da asserção principal (H4). ORACLE_SANDBOX=1 só no fictício, lido pelo filho
# sem credenciais. Os valores fictícios de "segredo" só existem para provar que não vazam.

_PREFIXO_MALFORMADAS = "Linhas do .env com erro de sintaxe foram ignoradas. Quantidade: "


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_f4a_oserror_antes_da_escrita_permite_nova_tentativa(entrada, tmp_path):
    """(a) Achado 1: PermissionError na 1ª leitura não trava o processo; a subida seguinte carrega o .env."""
    dados = _rodar(
        entrada, tmp_path, "ORACLE_SANDBOX=1\nSENTINELA_FASE2=1\n", runs=2,
        injecoes={"leitura": "PermissionError"},
    )
    runs = dados["por_run"]
    resumo = f"por_run={[r['excecoes'] for r in runs]}, disparos={dados['disparos']}, chamadas={dados['chamadas']}"
    assert dados["disparos"].get("leitura") is True, resumo  # H4
    assert _com(runs[0]["excecoes"], MENSAGEM_FALHA_CARGA, "PermissionError", MENSAGEM_NOVA_TENTATIVA), resumo
    assert runs[1]["excecoes"] == [], resumo  # nova tentativa bem-sucedida
    assert runs[1]["sentinela"] == "1", resumo
    assert [r["sandbox"] for r in runs] == ["AUSENTE", "AUSENTE"], resumo
    descartes = [a for a in dados["avisos"] if "DESCARTADA" in a]
    assert len(descartes) == 1, resumo  # aviso uma vez, na tentativa que deu certo
    if entrada == "cli":
        assert dados["stderr"].count(_PREFIXO_CLI + _TEXTO_DESCARTE) == 1, resumo
    else:
        assert any(_TEXTO_DESCARTE in w for w in runs[1]["warning_tela"]), resumo
    assert len(dados["chamadas"]) == 1, resumo
    assert dados["leituras_efetivas_por_run"] == [1, 1], resumo
    assert dados["leituras_reais"] == []


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_f4b_uma_unica_leitura_do_env(entrada, tmp_path):
    """(b) Achado 1: o .env é lido uma vez por processo (B3 e carga usam o mesmo texto)."""
    dados = _rodar(entrada, tmp_path, "SENTINELA_FASE3=1\n", runs=2)
    resumo = f"leituras={dados['leituras_efetivas_por_run']}, chamadas={dados['chamadas']}"
    assert dados["sentinela_fase3"] == "1", resumo
    assert dados["leituras_efetivas_por_run"] == [1, 0], resumo
    assert [(c["caminho"], c["stream"]) for c in dados["chamadas"]] == [(None, True)], resumo
    assert dados["leituras_reais"] == []


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_f4c_env_diretorio_fail_closed(entrada, tmp_path):
    """(c) Achado 3: .env que não é arquivo regular aborta até reiniciar (sem nova tentativa)."""
    dados = _rodar(entrada, tmp_path, "", runs=2, ficticio_tipo="diretorio")
    runs = dados["por_run"]
    resumo = f"por_run={[r['excecoes'] for r in runs]}, stats={dados['stats_por_run']}"
    for run in runs:
        assert _com(run["excecoes"], MENSAGEM_FALHA_CARGA, "NaoEArquivoRegular", MENSAGEM_REINICIE), resumo
    assert dados["stats_por_run"][1] == 0, resumo  # o run 2 não tenta de novo
    assert dados["chamadas"] == [] and dados["leituras_efetivas_por_run"] == [0, 0], resumo
    assert dados["leituras_reais"] == []


def test_f4c2_env_ausente_nova_tentativa(tmp_path):
    """(c') P1 = B: .env ausente não sobe sem chaves; cada subida tenta de novo."""
    dados = _rodar("cli", tmp_path, "", runs=2, ficticio_tipo="ausente")
    runs = dados["por_run"]
    resumo = f"por_run={[r['excecoes'] for r in runs]}, stats={dados['stats_por_run']}"
    for run in runs:
        assert _com(run["excecoes"], MENSAGEM_FALHA_CARGA, "FileNotFoundError", MENSAGEM_NOVA_TENTATIVA), resumo
    assert dados["stats_por_run"][1] >= 1, resumo  # o run 2 tentou de novo
    assert dados["chamadas"] == [] and dados["leituras_efetivas_por_run"] == [0, 0], resumo
    assert dados["leituras_reais"] == []

@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_f4c2b_env_ausente_preserva_sandbox_do_shell(entrada, tmp_path):
    """(c'') T2 (registro_pos_merge): com .env ausente, a ORACLE_SANDBOX herdada do shell não é removida (o valor
    do shell vale; bloco carga-env) e cada subida tenta de novo. Sentinela "0", só no ambiente do subprocesso: o
    bloco testa só a presença da chave, então "0" exercita o mesmo ramo que "1"."""
    dados = _rodar(entrada, tmp_path, "", sandbox_shell="0", runs=2, ficticio_tipo="ausente")
    runs = dados["por_run"]
    resumo = f"por_run={[(r['sandbox'], r['excecoes']) for r in runs]}, stats={dados['stats_por_run']}"
    assert len(runs) == 2, resumo
    for run in runs:
        assert _com(run["excecoes"], MENSAGEM_FALHA_CARGA, "FileNotFoundError", MENSAGEM_NOVA_TENTATIVA), resumo
        assert run["sandbox"] == "0", resumo
        assert not [w for w in run["warning_tela"] if "DESCARTADA" in w], resumo
    assert dados["sandbox"] == "0", resumo
    assert not [a for a in dados["avisos"] if "DESCARTADA" in a], resumo
    assert dados["stats_por_run"][1] >= 1, resumo  # o run 2 tentou de novo
    assert dados["chamadas"] == [] and dados["leituras_efetivas_por_run"] == [0, 0], resumo
    assert dados["leituras_reais"] == []


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_f4d_linhas_malformadas_so_contagem(entrada, tmp_path):
    """(d) Achado 3: linhas malformadas não abortam; aviso só com a contagem, sem o conteúdo."""
    dados = _rodar(
        entrada, tmp_path,
        "SENTINELA_FASE3=1\nLINHA MALFORMADA_FICTICIA texto_secreto_ficticio\n"
        'CHAVE_ABERTA="segredo_ficticio_aberto\n',
        runs=2,
    )
    runs = dados["por_run"]
    resumo = f"avisos={dados['avisos']}, stderr={dados['stderr']!r}, por_run={[r['excecoes'] for r in runs]}"
    assert [r["excecoes"] for r in runs] == [[], []], resumo
    assert dados["sentinela_fase3"] == "1", resumo
    malformadas = [a for a in dados["avisos"] if _PREFIXO_MALFORMADAS in a]
    assert malformadas == [_PREFIXO_MALFORMADAS + "2"], resumo
    tela = "".join(r["tela_texto"] + "".join(r["warning_tela"]) for r in runs)
    saidas = "\n".join(dados["log_total"]) + dados["stderr"] + dados["stdout_resto"] + tela
    assert "secreto" not in saidas and "segredo" not in saidas, "conteúdo de linha malformada vazou"
    if entrada == "cli":
        assert dados["stderr"].count(_PREFIXO_CLI + _PREFIXO_MALFORMADAS + "2") == 1, resumo
    else:
        for run in runs:
            assert _PREFIXO_MALFORMADAS + "2" in run["warning_tela"], resumo
    assert dados["leituras_reais"] == []


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_f4e_escrita_parcial_fail_closed(entrada, tmp_path):
    """(e) Achado 1: OSError depois de começar a escrever em os.environ trava até reiniciar."""
    dados = _rodar(
        entrada, tmp_path, "SENTINELA_FASE2=1\nSENTINELA_FASE3=1\n", runs=2,
        injecoes={"putenv": "SENTINELA_FASE3"},
    )
    runs = dados["por_run"]
    resumo = f"por_run={[r['excecoes'] for r in runs]}, disparos={dados['disparos']}"
    assert dados["disparos"].get("putenv") is True, resumo  # H4
    assert runs[0]["sentinela"] == "1", resumo  # a 1ª chave já tinha sido escrita (escrita parcial)
    assert _com(runs[1]["excecoes"], MENSAGEM_FALHA_CARGA, MENSAGEM_REINICIE), resumo
    assert runs[1]["sentinela_fase3"] == "AUSENTE", resumo  # o run 2 não recarregou
    assert dados["leituras_efetivas_por_run"] == [1, 0], resumo
    assert len(dados["chamadas"]) == 1, resumo
    assert dados["leituras_reais"] == []


@pytest.mark.parametrize("entrada", ["cli", "web"])
def test_f4g_ok_so_depois_do_descarte(entrada, tmp_path):
    """(g) R2: falha ao remover ORACLE_SANDBOX do arquivo não deixa o estado "ok"; o run 2 continua recusado."""
    dados = _rodar(
        entrada, tmp_path, "ORACLE_SANDBOX=1\nSENTINELA_FASE2=1\n", runs=2,
        injecoes={"unsetenv": "ORACLE_SANDBOX"},
    )
    runs = dados["por_run"]
    resumo = f"por_run={[r['excecoes'] for r in runs]}, disparos={dados['disparos']}"
    assert dados["disparos"].get("unsetenv") is True, resumo  # H4
    assert runs[0]["excecoes"], resumo  # o run 1 falhou no descarte
    assert _com(runs[1]["excecoes"], MENSAGEM_FALHA_CARGA, MENSAGEM_REINICIE), resumo
    assert dados["leituras_reais"] == []


def test_f4h_interrupcao_fica_fail_closed(tmp_path):
    """(h) BaseException durante a leitura deixa "falhou" (interrompida), sem nova tentativa."""
    dados = _rodar("cli", tmp_path, "SENTINELA_FASE3=1\n", runs=2, injecoes={"leitura": "BaseException"})
    runs = dados["por_run"]
    resumo = f"por_run={[r['excecoes'] for r in runs]}, disparos={dados['disparos']}"
    assert dados["disparos"].get("leitura") is True, resumo  # H4
    assert _com(runs[0]["excecoes"], "InterrupcaoSimulada"), resumo
    assert _com(runs[1]["excecoes"], MENSAGEM_FALHA_CARGA, "interrompida", MENSAGEM_REINICIE), resumo
    assert dados["sentinela_fase3"] == "AUSENTE", resumo
    assert dados["leituras_efetivas_por_run"] == [1, 0], resumo
    assert dados["leituras_reais"] == []


_MARCA_INICIO = b"# >>> carga-env"
_MARCA_FIM = b"# <<< carga-env"


def _bloco_carga_env(caminho):
    """Bytes do bloco carga-env, marcadores incluídos. Exige exatamente um par, na ordem, com conteúdo."""
    linhas = caminho.read_bytes().splitlines(keepends=True)
    inicios = [i for i, linha in enumerate(linhas) if linha.startswith(_MARCA_INICIO)]
    fins = [i for i, linha in enumerate(linhas) if linha.startswith(_MARCA_FIM)]
    assert len(inicios) == 1 and len(fins) == 1, f"{caminho.name}: marcadores >>> {len(inicios)}, <<< {len(fins)}"
    assert inicios[0] + 1 < fins[0], f"{caminho.name}: bloco carga-env vazio ou fora de ordem"
    return b"".join(linhas[inicios[0]:fins[0] + 1])


def test_t1_bloco_carga_env_identico_nas_entradas():
    """T1 (registro_pos_merge): o bloco carga-env é idêntico, byte a byte (fim de linha incluído), em app.py e
    src/main.py, como o comentário do próprio bloco afirma. Só lê os dois arquivos: sem subprocesso, sem .env e
    sem ORACLE_SANDBOX."""
    bloco_app = _bloco_carga_env(RAIZ / "app.py")
    bloco_main = _bloco_carga_env(RAIZ / "src" / "main.py")
    if bloco_app != bloco_main:
        a, m = bloco_app.splitlines(keepends=True), bloco_main.splitlines(keepends=True)
        i = next((k for k, (x, y) in enumerate(zip(a, m)) if x != y), min(len(a), len(m)))
        pytest.fail(f"bloco carga-env divergente: primeira diferença na linha {i + 1} do bloco "
                    f"(app.py {len(a)} linhas, src/main.py {len(m)} linhas)")
