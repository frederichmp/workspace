"""
Verificação padrão do PERSONAL_AGENT: passos 0 a 3 do docs/PROCESSO.md §5.

Somente leitura. Não lê o .env, não imprime valor de variável, não define ORACLE_SANDBOX
e só grava em docs/entregas/<tarefa>/. Código de segurança (PROCESSO §2). Os comandos são
os do §5; tests/test_verificacao_padrao.py confere a igualdade.

Uso (na raiz do projeto ou fora dela):
  python -I tools/verificacao_padrao.py --tarefa <t> --base <commit> --esperado <P>/<S>
      [--previsto <padrão> ...] [--rotulo <r>] [--registry-pendente]

Código de saída: 0 OK, 1 FALHA, 2 PARE ou NÃO VERIFICADO (inclusive erro inesperado).
"""
import argparse
import fnmatch
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

OK = "OK"
FALHA = "FALHA"
PARE = "PARE"
NAO_VERIFICADO = "NÃO VERIFICADO"
ERRO = "ERRO"
NAO_RODOU = "NÃO RODOU"

PREFIXOS_PROIBIDOS = re.compile(r"^(ORACLE_|EMAIL_|GEMINI_|AGENTDBA_|SCRIPTS_)", re.IGNORECASE)
MOTIVO_SKIP = "Teste ignorado: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)"
SEGMENTO = re.compile(r"^[A-Za-z0-9._-]+$")
ROTULO = re.compile(r"^[A-Za-z0-9_-]+$")
BASE = re.compile(r"^[0-9A-Za-z._/~^-]+$")
AREAS_SO_LITERAL = ("tests/", "src/", "registry/", "db/")
RE_ENV = r"(^|/)\.env$"
TIMEOUT_PYTEST = 560
ARGS_PYTEST = ["-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider"]

# Passo 0: o comando do §5 sem o filtro (o filtro fica em filtrar_perfil). Com 'Stop', erro de
# leitura do registro sai com código 1 em vez de 0 e saída vazia.
CMD_PERFIL_NUCLEO = (
    "@((Get-Item 'HKCU:\\Environment').Property) + "
    "@((Get-Item 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment').Property)"
)
CMD_PERFIL = "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'; " + CMD_PERFIL_NUCLEO

# Passo 3: greps do §5 que esperam nenhuma linha. Os padrões 3.1, 3.2 e 3.3 estão partidos
# em dois literais para o texto deste arquivo (tools/*.py e *.py estão no escopo) não casar com eles.
GREPS = (
    ("3.1", "conta Oracle legada", ["-n", "-E", "ORACLE_" "USER\\b", "--", "src/*.py", "app.py", "tools/*.py"]),
    ("3.2", "SQL de sessão no Python", ["-n", "-i", "-E", "alter" "[[:space:]]+(system|session)", "--", "*.py"]),
    ("3.3", "recarga do .env", ["-n", "override" "=True", "--", "src/*.py", "app.py", "tools/*.py"]),
    ("3.5", "código que liga o sandbox",
     ["-n", "-E", "setenv\\(['\"]ORACLE_SANDBOX['\"], *['\"]1|environ\\[['\"]ORACLE_SANDBOX['\"]\\] *= *['\"]1",
      "--", "*.py"]),
    ("3.6", "credencial em print ou log",
     ["-n", "-i", "-E", "(print|logger\\.\\w+)\\(.*(passw|senha|pwd|secret|token|api_key)", "--", "*.py"]),
)
GREP_LOAD_DOTENV = ["-n", "-E", "load_dotenv\\(", "--", "src/*.py", "app.py"]

RE_CONTAGEM = re.compile(r"(\d+) (failed|passed|skipped|deselected|xfailed|xpassed|errors?|warnings?)\b")
RE_SKIP = re.compile(r"^SKIPPED \[(\d+)\] (.+?:\d+): (.*)$")
# Só as 2 formas que o tests/conftest.py produz (medidas em 2026-11-19): o print do pytest_sessionfinish,
# no início da linha, e o pytest.exit ("! _pytest.outcomes.Exit: ..."). O mesmo texto citado na fonte ou
# no repr de um teste que falhou fica indentado e não conta.
RE_GOVERNANCA = re.compile(r"^(?:FALHA DE GOVERNANCA:|!+ _pytest\.outcomes\.Exit: FALHA DE GOVERNANCA:)", re.MULTILINE)


# ---------- funções puras (testadas em tests/test_verificacao_padrao.py) ----------

def validar_tarefa(tarefa):
    """Aceita só segmentos [A-Za-z0-9._-] separados por /, sem '.', '..' ou segmento vazio."""
    segmentos = tarefa.split("/")
    if not tarefa or any(s in ("", ".", "..") or not SEGMENTO.match(s) for s in segmentos):
        raise ValueError(f"--tarefa inválida: {tarefa!r}")
    return tarefa


def validar_base(base):
    """Recusa valor vazio, iniciado por '-' (seria opção do git) ou com caractere fora de [0-9A-Za-z._/~^-]."""
    if not base or base.startswith("-") or not BASE.match(base):
        raise ValueError(f"--base inválida: {base!r}")
    return base


def validar_previsto(padrao):
    """Caminho literal vale sempre. Padrão com curinga precisa de prefixo literal com '/', fora da raiz,
    de tests/, src/, registry/ e db/: nessas áreas, só caminho literal."""
    posicoes = [padrao.find(c) for c in "*?[" if c in padrao]
    if not posicoes:
        return padrao
    prefixo = padrao[:min(posicoes)]
    if "/" not in prefixo or prefixo.startswith(AREAS_SO_LITERAL):
        raise ValueError(f"--previsto amplo demais: {padrao!r} (na raiz, em tests/, src/, registry/ ou db/, "
                         "use o caminho literal)")
    return padrao


def interpretar_perfil(codigo, stdout, stderr):
    """Nomes do perfil, ou None (NÃO VERIFICADO) com código diferente de 0, stderr ou lista vazia."""
    if codigo != 0 or stderr.strip():
        return None
    nomes = [n.strip() for n in stdout.splitlines() if n.strip()]
    return nomes or None


def filtrar_perfil(nomes):
    """Nomes do perfil com prefixo proibido, sem diferenciar maiúsculas. Só nomes, nunca valores."""
    return sorted({n.strip() for n in nomes if PREFIXOS_PROIBIDOS.match(n.strip())})


def ler_status_z(saida, prefixo):
    """Converte `git status --porcelain=v1 -z` em [(XY, caminho relativo ao projeto)].
    Em renomeação ou cópia, entram o destino e a origem: os dois precisam estar previstos."""
    campos = saida.split("\0")
    itens, i = [], 0
    while i < len(campos):
        campo = campos[i]
        i += 1
        if len(campo) < 4:
            continue
        xy, caminhos = campo[:2], [campo[3:]]
        if "R" in xy or "C" in xy:
            if i < len(campos) and campos[i]:
                caminhos.append(campos[i])  # origem, que também precisa estar prevista
            i += 1
        for caminho in caminhos:
            if prefixo and caminho.startswith(prefixo):
                caminho = caminho[len(prefixo):]
            itens.append((xy, caminho))
    return itens


def classificar_status(itens, previstos, tarefa):
    """Devolve (fora do previsto, os que mandam parar antes do pytest: tests/, src/ ou raiz)."""
    proprios = f"docs/entregas/{tarefa}/"
    fora = []
    for xy, caminho in itens:
        if caminho.startswith(proprios):
            continue
        if any(fnmatch.fnmatchcase(caminho, p) for p in previstos):
            continue
        fora.append((xy, caminho))
    parar = [(xy, c) for xy, c in fora if c.startswith(("tests/", "src/")) or "/" not in c]
    return fora, parar


def _erro_import_oracledb(saida):
    return "DLL load failed" in saida or (
        "oracledb" in saida and re.search(r"\b(ImportError|ModuleNotFoundError)\b", saida) is not None)


def analisar_pytest(saida, codigo, esperado_p, esperado_s):
    """Classifica a saída do pytest -q -rs. Falha fechado: OK só com tudo conferido."""
    if codigo is None:
        return NAO_VERIFICADO, "pytest excedeu o tempo limite", {}
    if RE_GOVERNANCA.search(saida):
        return PARE, "o conftest acusou FALHA DE GOVERNANCA; não rode de novo", {}
    resumo = next((l for l in reversed(saida.splitlines()) if RE_CONTAGEM.search(l) and " in " in l), None)
    if codigo not in (0, 1) or resumo is None:
        if _erro_import_oracledb(saida):
            return NAO_VERIFICADO, "erro ao importar o oracledb (L4); o pytest não rodou", {}
        return NAO_VERIFICADO, f"pytest sem resultado (código {codigo})", {}
    cont = {}
    for n, tipo in RE_CONTAGEM.findall(resumo):
        cont[{"errors": "error", "warnings": "warning"}.get(tipo, tipo)] = int(n)
    passed, skipped = cont.get("passed", 0), cont.get("skipped", 0)
    if skipped < esperado_s:
        return PARE, f"POSSÍVEL EXECUÇÃO EM SANDBOX: skipped {skipped}, esperado {esperado_s}", cont
    if cont.get("failed", 0) or cont.get("error", 0):
        return FALHA, f"{cont.get('failed', 0)} failed, {cont.get('error', 0)} error", cont
    if codigo != 0:
        return FALHA, f"código {codigo} sem failed; conferir a saída", cont
    if skipped != esperado_s:
        return FALHA, f"skipped {skipped}, esperado {esperado_s}", cont
    if passed != esperado_p:
        return FALHA, f"passed {passed}, esperado {esperado_p}", cont
    soma, outros = 0, []
    for linha in saida.splitlines():
        m = RE_SKIP.match(linha.strip())
        if m:
            soma += int(m.group(1))
            if m.group(3).strip() != MOTIVO_SKIP:
                outros.append(m.group(3).strip())
    if outros:
        return FALHA, f"skip com outro motivo: {outros[0][:100]}", cont
    if soma != skipped:
        return FALHA, f"SKIPPED listados somam {soma}; a contagem diz {skipped}", cont
    return OK, f"{passed} passed, {skipped} skipped, 0 failed", cont


def classificar_grep(codigo, linhas):
    """git grep: código 1 sem linhas é OK; 0 é FALHA (linhas achadas); outro código é ERRO, nunca OK."""
    if codigo == 1 and not linhas:
        return OK, "nenhuma linha"
    if codigo == 0:
        return FALHA, f"{len(linhas)} linha(s)"
    return ERRO, f"git grep terminou com código {codigo}"


def classificar_load_dotenv(codigo, linhas):
    """Esperado: exatamente app.py e src/main.py, ambos com override=False."""
    if codigo not in (0, 1):
        return ERRO, f"git grep terminou com código {codigo}"
    arquivos = sorted(l.split(":", 1)[0] for l in linhas)
    if arquivos != ["app.py", "src/main.py"]:
        return FALHA, f"esperado app.py e src/main.py; obtido {arquivos}"
    if not all("override=False" in l for l in linhas):
        return FALHA, "linha sem override=False"
    return OK, "app.py e src/main.py, override=False"


def tem_marca_pendente(mensagem):
    """Mensagem de commit com 'PENDENTE APROVAÇÃO' (com ou sem acento)."""
    sem_acento = unicodedata.normalize("NFKD", mensagem).encode("ascii", "ignore").decode().upper()
    return "PENDENTE APROVACAO" in sem_acento


def classificar_registry(diff_stat, pendente, sem_marca, local):
    """registry/ e db/: vazio é OK; alterado só com --registry-pendente, tudo commitado e todo commit marcado."""
    if not diff_stat.strip():
        return OK, "vazio"
    if not pendente:
        return FALHA, "registry/ ou db/ alterado sem plano PENDENTE APROVAÇÃO"
    if local.strip():
        return FALHA, "alteração não commitada em registry/ ou db/"
    if sem_marca:
        return FALHA, f"commit sem PENDENTE APROVAÇÃO: {', '.join(sem_marca)}"
    return OK, "alterado só em commit PENDENTE APROVAÇÃO"


def env_versionado(arquivos):
    return [a for a in arquivos if re.search(RE_ENV, a)]


def codigo_de_saida(statuses):
    if any(s in (PARE, NAO_VERIFICADO, ERRO) for s in statuses):
        return 2
    return 1 if FALHA in statuses else 0


# ---------- execução ----------

def _git(*args, timeout=120):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=off", "-c", "i18n.logOutputEncoding=UTF-8", *args],
                           cwd=RAIZ, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return r.returncode, r.stdout.decode("utf-8", "replace")


def _ler_perfil():
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", CMD_PERFIL],
                           capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return interpretar_perfil(r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace"))


def _matar_arvore(pid, run=subprocess.run, windows=None):
    """No Windows, o kill do subprocess mata só o processo de cima e a espera segue até o fim dos filhos;
    taskkill /T leva a árvore inteira (medido em 2026-11-19: um estouro de 560 s esperou 43 min)."""
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


def _rodar_pytest():
    env = {k: v for k, v in os.environ.items() if k.upper() != "ORACLE_SANDBOX"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return _executar([sys.executable, *ARGS_PYTEST], RAIZ, env, TIMEOUT_PYTEST)


def _local(linha):
    return ":".join(linha.split(":", 2)[:2])


def _celula(texto):
    return str(texto).replace("|", "\\|").replace("\n", " ")


def _gravar(caminho, texto):
    with open(caminho, "x", encoding="utf-8") as f:  # 'x': nunca sobrescreve, nem em execução paralela
        f.write(texto)


def _greps(base_hash, registry_pendente, tabela, blocos):
    for ident, descr, grep_args in GREPS:
        codigo, saida = _git("grep", *grep_args)
        linhas = [l for l in saida.splitlines() if l.strip()]
        st, obtido = classificar_grep(-1 if codigo is None else codigo, linhas)
        if linhas:
            obtido += f" (1ª: {_local(linhas[0])})"
        registro = [_local(l) for l in linhas] if ident == "3.6" else linhas  # 3.6: só arquivo:linha
        blocos.append(f"## {ident} {descr} (código {codigo})\n" + ("\n".join(registro) or "(nenhuma linha)"))
        tabela.append((ident, descr, "nenhuma linha", obtido, st))

    codigo, saida = _git("grep", *GREP_LOAD_DOTENV)
    linhas = [l for l in saida.splitlines() if l.strip()]
    st, obtido = classificar_load_dotenv(-1 if codigo is None else codigo, linhas)
    blocos.append(f"## 3.4 load_dotenv (código {codigo})\n" + ("\n".join(linhas) or "(nenhuma linha)"))
    tabela.append(("3.4", "load_dotenv", "app.py e src/main.py, override=False", obtido, st))

    c1, diff_stat = _git("diff", "--stat", base_hash, "--", "registry/", "db/")
    c2, local = _git("diff", "--stat", "HEAD", "--", "registry/", "db/")
    c3, log = _git("log", "--format=%h%x00%B%x01", f"{base_hash}..HEAD", "--", "registry/", "db/")
    if c1 != 0 or c2 != 0 or c3 != 0:
        st, obtido = ERRO, f"git diff/log falhou (códigos {c1}, {c2}, {c3})"
    else:
        sem_marca = [c.split("\0")[0].strip() for c in log.split("\x01") if c.strip() and not tem_marca_pendente(c)]
        st, obtido = classificar_registry(diff_stat, registry_pendente, sem_marca, local)
    blocos.append(f"## 3.7 git diff --stat {base_hash[:7]} -- registry/ db/\n{diff_stat.strip() or '(vazio)'}")
    tabela.append(("3.7", "registry/ e db/", "vazio, salvo PENDENTE APROVAÇÃO", obtido, st))

    codigo, saida = _git("ls-files")
    if codigo != 0:
        st, obtido = ERRO, f"git ls-files terminou com código {codigo}"
    else:
        achados = env_versionado(saida.splitlines())
        st, obtido = (OK, "nenhum") if not achados else (FALHA, ", ".join(achados))
    blocos.append(f"## 3.8 .env versionado\n{obtido}")
    tabela.append(("3.8", ".env versionado", "nenhum", obtido, st))


def _main(argv):
    ap = argparse.ArgumentParser(description="Passos 0 a 3 do docs/PROCESSO.md §5.")
    ap.add_argument("--tarefa", required=True, help="saídas em docs/entregas/<tarefa>/")
    ap.add_argument("--base", required=True, help="commit-base do git diff de registry/ e db/")
    ap.add_argument("--esperado", required=True, help="P/S: passed e skipped esperados")
    ap.add_argument("--previsto", action="append", default=[], help="caminho literal, ou padrão fnmatch com prefixo")
    ap.add_argument("--rotulo", default="padrao", help="prefixo dos arquivos de saída")
    ap.add_argument("--registry-pendente", action="store_true", help="plano com PENDENTE APROVAÇÃO em registry/ ou db/")
    args = ap.parse_args(argv)
    try:
        tarefa = validar_tarefa(args.tarefa)
        base = validar_base(args.base)
        previstos = [validar_previsto(p) for p in args.previsto]
        if not ROTULO.match(args.rotulo):
            raise ValueError(f"--rotulo inválido: {args.rotulo!r}")
        esperado_p, esperado_s = (int(x) for x in args.esperado.split("/"))
    except ValueError as e:
        print(f"ERRO: {e}")
        return 2
    codigo, base_hash = _git("rev-parse", "--verify", "--quiet", "--end-of-options", f"{base}^{{commit}}")
    base_hash = base_hash.strip()
    if codigo != 0 or not re.fullmatch(r"[0-9a-f]{40,64}", base_hash):
        print(f"ERRO: --base não é um commit: {base!r}")
        return 2

    destino = RAIZ / "docs" / "entregas" / tarefa
    nomes = ("perfil", "git_status", "pytest", "greps")
    arquivos = {n: destino / f"{args.rotulo}_{n}.txt" for n in nomes}
    relatorio = destino / f"{args.rotulo}.md"
    existentes = [p for p in (*arquivos.values(), relatorio) if p.exists()]
    if existentes:
        print(f"ERRO: saída já existe ({existentes[0].name}); use outro --rotulo")
        return 2

    _, head = _git("rev-parse", "--short", "HEAD")
    _, ramo = _git("branch", "--show-current")
    _, prefixo = _git("rev-parse", "--show-prefix")
    sandbox_shell = "presente" if any(k.upper() == "ORACLE_SANDBOX" for k in os.environ) else "ausente"
    tabela, textos = [], {n: "" for n in nomes}

    nomes_perfil = _ler_perfil()
    if nomes_perfil is None:
        tabela.append(("0", "perfil do Windows (só nomes)", "nenhum nome proibido",
                       "leitura do perfil falhou ou veio vazia", NAO_VERIFICADO))
    else:
        proibidos = filtrar_perfil(nomes_perfil)
        textos["perfil"] = "\n".join(proibidos) or "nenhum nome com prefixo proibido"
        tabela.append(("0", "perfil do Windows (só nomes)", "nenhum nome proibido",
                       ", ".join(proibidos) or "nenhum", PARE if proibidos else OK))

    if tabela[-1][4] == OK:
        codigo, saida = _git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--", ".")
        if codigo != 0:
            tabela.append(("1", "git status", "só o previsto", f"git status terminou com código {codigo}", NAO_VERIFICADO))
        else:
            itens = ler_status_z(saida, prefixo.strip())
            textos["git_status"] = "\n".join(f"{xy} {c}" for xy, c in itens) or "(limpo)"
            fora, parar = classificar_status(itens, previstos, tarefa)
            obtido = "só o previsto" if not fora else "fora: " + ", ".join(c for _, c in fora[:5]) + (
                f" (+{len(fora) - 5})" if len(fora) > 5 else "")
            tabela.append(("1", "git status", "só o previsto", obtido, PARE if parar else FALHA if fora else OK))

    if tabela[-1][0] == "1" and tabela[-1][4] in (OK, FALHA):
        codigo, saida = _rodar_pytest()
        textos["pytest"] = saida
        st, motivo, _ = analisar_pytest(saida, codigo, esperado_p, esperado_s)
        tabela.append(("2", "pytest sem conexão", f"0 failed, {esperado_p} passed, {esperado_s} skipped", motivo, st))

    if tabela[-1][0] == "2" and tabela[-1][4] == OK:
        blocos = []
        _greps(base_hash, args.registry_pendente, tabela, blocos)
        textos["greps"] = "\n\n".join(blocos)
    else:
        tabela.append(("-", "passos seguintes", "-", "não rodaram: o §5 para no passo acima", NAO_RODOU))

    statuses = [linha[4] for linha in tabela]
    resultado = {0: OK, 1: FALHA, 2: "PARE ou NÃO VERIFICADO"}[codigo_de_saida(statuses)]
    destino.mkdir(parents=True, exist_ok=True)
    gravados = []
    for n in nomes:
        if textos[n]:
            _gravar(arquivos[n], textos[n])
            gravados.append(arquivos[n].relative_to(RAIZ).as_posix())
    linhas_md = [
        "# Verificação padrão (docs/PROCESSO.md §5, passos 0 a 3)",
        "",
        f"HEAD `{head.strip()}` (branch `{ramo.strip()}`); base `{args.base}`; esperado {esperado_p} passed e "
        f"{esperado_s} skipped; `ORACLE_SANDBOX` no shell: {sandbox_shell}.",
        "",
        "| Passo | Checagem | Esperado | Obtido | Status |",
        "|---|---|---|---|---|",
        *[f"| {' | '.join(_celula(c) for c in linha)} |" for linha in tabela],
        "",
        f"Resultado: {resultado}. Saídas: {', '.join(gravados) or 'nenhuma'}.",
    ]
    texto = "\n".join(linhas_md) + "\n"
    _gravar(relatorio, texto)
    print(texto + f"Relatório: {relatorio.relative_to(RAIZ).as_posix()}")
    return codigo_de_saida(statuses)


def main(argv=None):
    """Erro inesperado sai com 2 (NÃO VERIFICADO), nunca com 1, que seria lido como FALHA."""
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    try:
        return _main(argv)
    except Exception as e:  # noqa: BLE001  falha fechado
        print(f"ERRO inesperado ({type(e).__name__}): {e}. Resultado: NÃO VERIFICADO.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
