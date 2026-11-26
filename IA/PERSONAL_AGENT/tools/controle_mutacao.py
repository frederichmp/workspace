"""
Controle de mutação do PERSONAL_AGENT (docs/PROCESSO.md §5; lições L3, L14, L16, L18 e L20).

Numa cópia `git archive HEAD` do projeto (sem .env), aplica cada mutação ao alvo, roda só os
testes indicados e classifica: DETECTADA (algum teste falhou), PASSOU (nenhum falhou, o teste
está cego ou o controle está mal desenhado) ou INVÁLIDA (a coleta quebrou, tempo esgotado etc.).
O m0, sem mutação, roda antes e precisa passar. Código de segurança (PROCESSO §2).

Uso:
  python -I tools/controle_mutacao.py --tarefa <t> --rotulo <r> --alvo <arquivo> --teste <caminho> [--teste ...]
      (--mutacao <nome> <de> <para> ... | --mutacoes-json <arquivo>) [--incluir <arquivo do working tree> ...]
      [--esperado-coletados <n>]

KM2 (plano 9.10): antes do m0, a coleta (--collect-only) do projeto e a da cópia têm de bater, sem deselecionados, e
o m0 tem de executar exatamente o coletado; senão a rodada é INVÁLIDA. Mutante morto (DETECTADA) só com rc 1 e ao
menos 1 teste falho.

O JSON é uma lista de {"nome", "de", "para"}; use-o para troca com aspas ou várias linhas.
Código de saída: 0 todas detectadas, 1 alguma passou, 2 controle inválido ou erro.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

DETECTADA = "DETECTADA"
PASSOU = "PASSOU"
INVALIDA = "INVÁLIDA"
ERRO = "ERRO"

SEGMENTO = re.compile(r"^[A-Za-z0-9._-]+$")
ROTULO = re.compile(r"^[A-Za-z0-9_-]+$")
NOME_MUTACAO = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
NOME_ENV = re.compile(r"^\.env(\..+)?$", re.IGNORECASE)
ARGS_PYTEST = ["-m", "pytest", "-q", "-rfEs", "-p", "no:cacheprovider"]
TIMEOUT_TESTE = 560
RE_CONTAGEM = re.compile(r"(\d+) (failed|passed|errors?)\b")
# Só as 2 formas que o tests/conftest.py produz (medidas em 2026-11-19): o print do pytest_sessionfinish,
# no início da linha, e o pytest.exit ("! _pytest.outcomes.Exit: ..."). O mesmo texto citado na fonte ou
# no repr de um teste que falhou fica indentado e não conta.
RE_GOVERNANCA = re.compile(r"^(?:FALHA DE GOVERNANCA:|!+ _pytest\.outcomes\.Exit: FALHA DE GOVERNANCA:)", re.MULTILINE)
# Norma dos mutantes (docs/plans/1.11-R1-ampliada.md 9.9, passo KM): o filho que roda os testes da cópia não recebe
# ORACLE_* (inclui ORACLE_SANDBOX), EMAIL_*, GEMINI_*, OPS_KILL_*, OLLAMA_* nem *_PROXY, sem diferenciar maiúsculas.
PREFIXOS_FORA_DO_FILHO = ("ORACLE_", "EMAIL_", "GEMINI_", "OPS_KILL_", "OLLAMA_")
SUFIXOS_FORA_DO_FILHO = ("_PROXY",)
# KM2 (plano 9.10): variáveis que mudam a seleção ou os plugins do pytest do filho (um "-k" herdado esvaziaria a
# rodada sem invalidá-la). Nome exato, sem diferenciar maiúsculas.
NOMES_FORA_DO_FILHO = frozenset({"PYTEST_ADDOPTS", "PYTEST_PLUGINS"})
# KM2: contagem da coleta ("565 tests collected", "3/565 tests collected (562 deselected)") e da execução.
RE_COLETADOS = re.compile(r"\b(\d+)(?:/(\d+))? tests? collected(?: \((\d+) deselected\))?")
RE_CONTAGEM_TOTAL = re.compile(r"(\d+) (failed|passed|skipped|deselected|xfailed|xpassed|errors?)\b")


# ---------- funções puras (testadas em tests/test_controle_mutacao.py) ----------

def validar_tarefa(tarefa):
    """Igual a verificacao_padrao.validar_tarefa: segmentos [A-Za-z0-9._-] separados por /."""
    segmentos = tarefa.split("/")
    if not tarefa or any(s in ("", ".", "..") or not SEGMENTO.match(s) for s in segmentos):
        raise ValueError(f"--tarefa inválida: {tarefa!r}")
    return tarefa


def e_env(caminho):
    """Nome .env ou .env.* (sem diferenciar maiúsculas), salvo .env.example."""
    nome = caminho.replace("\\", "/").rsplit("/", 1)[-1]
    return bool(NOME_ENV.match(nome)) and nome.lower() != ".env.example"


def validar_caminho(caminho):
    """Caminho relativo ao projeto, em /, sem '..', sem unidade e sem .env. Aceita nodeid (a::b)."""
    arquivo, sep, resto = caminho.replace("\\", "/").partition("::")
    partes = arquivo.split("/")
    if (not arquivo or arquivo.startswith("/") or re.match(r"^[A-Za-z]:", arquivo)
            or any(p in ("", ".", "..") for p in partes) or any(p.startswith("-") for p in partes)
            or not all(SEGMENTO.match(p) for p in partes) or e_env(arquivo)):
        raise ValueError(f"caminho inválido: {caminho!r} (relativo ao projeto, sem '..', sem '-' no início e sem .env)")
    return arquivo + sep + resto


def incluir_seguro(real, raiz_real):
    """--incluir já resolvido (realpath): dentro do projeto e sem .env, mesmo atrás de link simbólico."""
    real, raiz_real = os.path.normcase(real), os.path.normcase(raiz_real)
    return real.startswith(raiz_real.rstrip(os.sep) + os.sep) and not e_env(real)


def validar_mutacoes(mutacoes):
    """Lista de (nome, de, para): nome válido e único, m0 reservado, de diferente de para."""
    vistos = set()
    for nome, de, para in mutacoes:
        if not NOME_MUTACAO.match(nome) or nome == "m0" or nome in vistos:
            raise ValueError(f"nome de mutação inválido ou repetido: {nome!r} (m0 é reservado)")
        if not de or de == para:
            raise ValueError(f"mutação {nome}: 'de' vazio ou igual a 'para'")
        vistos.add(nome)
    if not mutacoes:
        raise ValueError("nenhuma mutação")
    return mutacoes


def aplicar_troca(texto, de, para):
    """Troca 'de' por 'para' em bytes UTF-8. Exige exatamente 1 ocorrência (L3, L16).
    Devolve (novo texto, CRLF, LF só) para registro."""
    crlf = texto.count(b"\r\n")
    lf_so = texto.count(b"\n") - crlf
    alvo = de.encode("utf-8")
    n = texto.count(alvo)
    if n != 1:
        raise ValueError(f"'de' aparece {n} vez(es); precisa de 1 (alvo com {crlf} CRLF e {lf_so} LF só)")
    return texto.replace(alvo, para.encode("utf-8")), crlf, lf_so


def classificar(codigo, saida):
    """Saída do pytest de uma execução: (status, resumo)."""
    if codigo is None:
        return INVALIDA, "tempo esgotado"
    if RE_GOVERNANCA.search(saida):
        return INVALIDA, "o conftest acusou FALHA DE GOVERNANCA; pare e informe"
    resumo = next((l.strip() for l in reversed(saida.splitlines()) if RE_CONTAGEM.search(l) and " in " in l), "")
    cont = {t.rstrip("s") if t.startswith("error") else t: int(n) for n, t in RE_CONTAGEM.findall(resumo)}
    if codigo == 0 and cont.get("passed", 0) > 0 and not cont.get("failed") and not cont.get("error"):
        return PASSOU, resumo
    # KM2: mutante morto só com rc 1 e ao menos 1 teste falho. Só "error" (coleta, setup, teardown), rc 2/3/4/5,
    # tempo esgotado ou falta da contagem: INVÁLIDA, nunca contada como morta.
    if codigo == 1 and cont.get("failed", 0) >= 1:
        return DETECTADA, resumo
    return INVALIDA, f"pytest terminou com código {codigo}: {resumo or 'sem linha de contagem'}"


def coletados(saida):
    """(selecionados, deselecionados) da linha do --collect-only; None se a linha não existir."""
    for linha in reversed(saida.splitlines()):
        achado = RE_COLETADOS.search(linha)
        if achado:
            return int(achado.group(1)), int(achado.group(3) or 0)
    return None


def executados(saida):
    """(executados, deselecionados) da linha final de uma execução: passed + skipped + failed + error + x*."""
    resumo = next((l for l in reversed(saida.splitlines()) if RE_CONTAGEM_TOTAL.search(l) and " in " in l), "")
    cont = {t.rstrip("s") if t.startswith("error") else t: int(n) for n, t in RE_CONTAGEM_TOTAL.findall(resumo)}
    total = sum(cont.get(k, 0) for k in ("passed", "skipped", "failed", "error", "xfailed", "xpassed"))
    return total, cont.get("deselected", 0)


def validar_coleta(no_projeto, na_copia, esperado=None):
    """KM2: None se a coleta é válida; senão o motivo. As duas coletas existem, sem deselecionados, iguais entre
    si e, se dado, iguais ao esperado."""
    if no_projeto is None or na_copia is None:
        return f"coleta sem linha de contagem (projeto {no_projeto}, cópia {na_copia})"
    if no_projeto[1] or na_copia[1]:
        return f"coleta com deselecionados (projeto {no_projeto}, cópia {na_copia})"
    if no_projeto[0] != na_copia[0]:
        return f"coleta diverge: projeto {no_projeto[0]}, cópia {na_copia[0]}"
    if esperado is not None and na_copia[0] != esperado:
        return f"coleta {na_copia[0]} diferente do esperado {esperado}"
    if na_copia[0] == 0:
        return "nenhum teste coletado"
    return None


def testes_que_cairam(saida):
    return [l.split(" - ")[0].split(" ", 1)[1] for l in saida.splitlines() if l.startswith(("FAILED ", "ERROR "))]


def codigo_de_saida(status_m0, status_mutacoes):
    if status_m0 != PASSOU or any(s in (INVALIDA, ERRO) for s in status_mutacoes):
        return 2
    return 1 if PASSOU in status_mutacoes else 0


# ---------- execução ----------

def _git(*args, cwd=None, timeout=120):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=cwd or RAIZ, capture_output=True,
                           timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return r.returncode, r.stdout.decode("utf-8", "replace")


def _criar_copia(tmp):
    """Extrai o HEAD do projeto em tmp com tarfile (filtro 'data'); devolve a pasta do projeto na cópia."""
    c1, topo = _git("rev-parse", "--show-toplevel")
    c2, prefixo = _git("rev-parse", "--show-prefix")
    if c1 != 0 or c2 != 0:
        raise RuntimeError("git rev-parse falhou")
    prefixo = prefixo.strip().rstrip("/")
    arquivo_tar = tmp / "copia.tar"
    codigo, _ = _git("archive", "--format=tar", "-o", str(arquivo_tar), "HEAD", "--", prefixo or ".", cwd=topo.strip())
    if codigo != 0:
        raise RuntimeError(f"git archive terminou com código {codigo}")
    with tarfile.open(arquivo_tar) as tar:
        tar.extractall(tmp / "copia", filter="data")
    return tmp / "copia" / prefixo


def _criar_tmp():
    return Path(tempfile.mkdtemp(prefix="controle_mutacao_"))


def _matar_arvore(pid, run=subprocess.run, windows=None):
    """No Windows, o kill do subprocess mata só o processo de cima; taskkill /T leva a árvore inteira."""
    if (os.name == "nt") if windows is None else windows:
        run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=30)
    else:
        try:
            os.killpg(os.getpgid(pid), 9)
        except (ProcessLookupError, PermissionError):
            pass


def _executar(cmd, cwd, env, timeout, popen=subprocess.Popen):
    """(código, saída). No estouro do tempo, mata a árvore de processos e devolve (None, saída parcial)."""
    p = popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
              start_new_session=(os.name != "nt"))
    try:
        saida, _ = p.communicate(timeout=timeout)
        return p.returncode, saida.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        _matar_arvore(p.pid)
        try:
            saida, _ = p.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()
            saida = b""
        return None, (saida or b"").decode("utf-8", "replace")


def ambiente_do_filho(ambiente):
    """Cópia de `ambiente` para o filho: sem credenciais, ORACLE_SANDBOX, gate do kill, Ollama e proxy (norma KM)."""
    env = {}
    for chave, valor in ambiente.items():
        nome = chave.upper()
        if nome.startswith(PREFIXOS_FORA_DO_FILHO) or nome.endswith(SUFIXOS_FORA_DO_FILHO) or nome in NOMES_FORA_DO_FILHO:
            continue
        env[chave] = valor
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _rodar_testes(copia, testes):
    return _executar([sys.executable, *ARGS_PYTEST, *testes], copia, ambiente_do_filho(os.environ), TIMEOUT_TESTE)


def _coletar_testes(pasta, testes):
    """KM2: (selecionados, deselecionados) do --collect-only em `pasta`, com o ambiente do filho; None se falhar."""
    codigo, saida = _executar([sys.executable, "-m", "pytest", "-q", "--collect-only", "-p", "no:cacheprovider", *testes],
                              pasta, ambiente_do_filho(os.environ), TIMEOUT_TESTE)
    return coletados(saida) if codigo == 0 else None


def _gravar(caminho, texto):
    with open(caminho, "x", encoding="utf-8") as f:  # 'x': nunca sobrescreve
        f.write(texto)


def _celula(texto, limite=70):
    texto = str(texto).replace("\n", "\\n").replace("|", "\\|")
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def _ler_mutacoes(args):
    mutacoes = [tuple(m) for m in args.mutacao]
    if args.mutacoes_json:
        if e_env(args.mutacoes_json):
            raise ValueError("--mutacoes-json não pode ser .env")
        caminho = Path(args.mutacoes_json)
        if not caminho.is_absolute():
            caminho = RAIZ / validar_caminho(args.mutacoes_json)
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        mutacoes += [(str(d["nome"]), str(d["de"]), str(d["para"])) for d in dados]
    return validar_mutacoes(mutacoes)


def _main(argv):
    ap = argparse.ArgumentParser(description="Controle de mutação numa cópia git archive do projeto.")
    ap.add_argument("--tarefa", required=True)
    ap.add_argument("--rotulo", required=True)
    ap.add_argument("--alvo", required=True, help="arquivo mutado, relativo ao projeto")
    ap.add_argument("--teste", action="append", required=True, help="caminho ou nodeid, relativo ao projeto")
    ap.add_argument("--mutacao", action="append", nargs=3, default=[], metavar=("NOME", "DE", "PARA"))
    ap.add_argument("--mutacoes-json", help="lista de {nome, de, para}")
    ap.add_argument("--incluir", action="append", default=[], help="arquivo do working tree copiado para a cópia")
    ap.add_argument("--esperado-coletados", type=int, default=None,
                    help="KM2: número de testes que a coleta tem de dar (opcional; projeto e cópia sempre comparados)")
    args = ap.parse_args(argv)
    try:
        tarefa = validar_tarefa(args.tarefa)
        if not ROTULO.match(args.rotulo):
            raise ValueError(f"--rotulo inválido: {args.rotulo!r}")
        alvo = validar_caminho(args.alvo)
        testes = [validar_caminho(t) for t in args.teste]
        incluir = [validar_caminho(i) for i in args.incluir]
        mutacoes = _ler_mutacoes(args)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as e:
        print(f"ERRO: {e}")
        return 2

    destino = RAIZ / "docs" / "entregas" / tarefa
    nomes = ["m0"] + [m[0] for m in mutacoes]
    saidas = {n: destino / f"{args.rotulo}_{n}.txt" for n in nomes}
    relatorio = destino / f"{args.rotulo}.md"
    existentes = [p for p in (*saidas.values(), relatorio) if p.exists()]
    if existentes:
        print(f"ERRO: saída já existe ({existentes[0].name}); use outro --rotulo")
        return 2
    for i in incluir:
        if not (RAIZ / i).is_file() or not incluir_seguro(os.path.realpath(RAIZ / i), os.path.realpath(RAIZ)):
            print(f"ERRO: --incluir não é arquivo do projeto (ou aponta para .env ou para fora): {i}")
            return 2

    tmp = _criar_tmp()
    linhas, textos, status = [], {}, {}
    nota_coleta = "Coletados: não medido."
    try:
        copia = _criar_copia(tmp)
        for i in incluir:
            (copia / i).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RAIZ / i, copia / i)
        if any(e_env(p.name) for p in copia.rglob(".env*")):
            print("ERRO: a cópia contém .env; nada foi executado")
            return 2
        caminho_alvo = copia / alvo
        if not caminho_alvo.is_file():
            print(f"ERRO: --alvo não existe na cópia (falta --incluir?): {alvo}")
            return 2
        original = caminho_alvo.read_bytes()

        # KM2: a coleta do projeto e a da cópia, com o ambiente do filho, têm de bater entre si (e com o esperado, se
        # dado), sem deselecionados; e o m0 tem de executar exatamente o que foi coletado. Senão, a rodada é INVÁLIDA.
        coleta_projeto, coleta_copia = _coletar_testes(RAIZ, testes), _coletar_testes(copia, testes)
        nota_coleta = (f"Coletados (selecionados, deselecionados): projeto {coleta_projeto}, cópia {coleta_copia}"
                       + (f", esperado {args.esperado_coletados}" if args.esperado_coletados is not None else "") + ".")
        problema = validar_coleta(coleta_projeto, coleta_copia, args.esperado_coletados)
        if problema:
            st, resumo, saida = INVALIDA, problema, ""
        else:
            codigo, saida = _rodar_testes(copia, testes)
            st, resumo = classificar(codigo, saida)
            if st == PASSOU and executados(saida) != (coleta_copia[0], 0):
                st, resumo = INVALIDA, f"m0 executou {executados(saida)}, a coleta é {coleta_copia}: {resumo}"
        status["m0"] = st
        textos["m0"] = f"# controle m0: sem mutação\n# local: cópia git archive HEAD + {incluir}\n# {nota_coleta}\n\n{saida}"
        linhas.append(("m0", "sem mutação", "-", resumo, "OK" if st == PASSOU else INVALIDA))
        if st == PASSOU:
            for nome, de, para in mutacoes:
                try:
                    novo, crlf, lf_so = aplicar_troca(original, de, para)
                except ValueError as e:
                    status[nome] = ERRO
                    linhas.append((nome, f"{de} -> {para}", str(e), "-", ERRO))
                    continue
                caminho_alvo.write_bytes(novo)
                try:
                    codigo, saida = _rodar_testes(copia, testes)
                finally:
                    caminho_alvo.write_bytes(original)
                st, resumo = classificar(codigo, saida)
                caidos = testes_que_cairam(saida)
                status[nome] = st
                textos[nome] = (f"# controle {nome}: {de!r} -> {para!r}\n# 1 substituição; alvo {alvo} com "
                                f"{crlf} CRLF e {lf_so} LF só\n\n{saida}")
                linhas.append((nome, f"{de} -> {para}", "1 substituição",
                               resumo + (f" | caíram: {', '.join(caidos[:3])}" if caidos else ""), st))
        else:
            linhas.append(("-", "mutações", "-", "não rodaram: o m0 precisa passar", INVALIDA))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    codigo_final = codigo_de_saida(status.get("m0"), [status.get(m[0], ERRO) for m in mutacoes])
    resultado = {0: "todas DETECTADAS", 1: "alguma PASSOU (teste cego ou controle mal desenhado: L14, L18)",
                 2: "controle INVÁLIDO ou ERRO"}[codigo_final]
    destino.mkdir(parents=True, exist_ok=True)
    for nome, texto in textos.items():
        _gravar(saidas[nome], texto)
    md = "\n".join([
        f"# Controle de mutação `{args.rotulo}`",
        "",
        f"Alvo `{alvo}`; testes {', '.join(f'`{t}`' for t in testes)}; cópia `git archive HEAD`"
        + (f" + {', '.join(f'`{i}`' for i in incluir)}" if incluir else "") + ".",
        "",
        nota_coleta,
        "",
        "| Mutação | Troca | Contagem | Resultado | Status |",
        "|---|---|---|---|---|",
        *[f"| {' | '.join(_celula(c) for c in linha)} |" for linha in linhas],
        "",
        "Mutações: " + ", ".join(
            f"{rotulo} {sum(1 for m in mutacoes if status.get(m[0], ERRO) == chave)}"
            for rotulo, chave in (("DETECTADAS", DETECTADA), ("PASSOU", PASSOU), ("INVÁLIDAS", INVALIDA), ("ERRO", ERRO))
        ) + " (INVÁLIDA e ERRO nunca contam como mortas).",
        f"Resultado: {resultado}.",
    ]) + "\n"
    _gravar(relatorio, md)
    print(md + f"Relatório: {relatorio.relative_to(RAIZ).as_posix()}")
    return codigo_final


def main(argv=None):
    """Erro inesperado sai com 2 (controle inválido), nunca com 0 ou 1."""
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    try:
        return _main(argv)
    except Exception as e:  # noqa: BLE001  falha fechado
        print(f"ERRO inesperado ({type(e).__name__}): {e}. Resultado: controle INVÁLIDO.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
