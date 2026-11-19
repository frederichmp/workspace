"""
Guarda dos subagentes do PERSONAL_AGENT: hook PreToolUse declarado no frontmatter de cada agente
(docs/PROCESSO.md §3).

Lê do stdin o JSON do hook (tool_name, tool_input, cwd) e decide: saída 0 libera; saída 2 bloqueia,
com o motivo no stderr, que o agente recebe e deve devolver como PARE, sem contornar. Entrada
inválida ou erro interno também saem com 2. No frontmatter, `onFailure: block` e `|| exit 2` cobrem
falha do próprio hook. Regras do CLAUDE.md: R1 git fora da lista de liberação (só leitura, também
nas opções e sem configuração injetada); R2 conteúdo do .env; R3 ORACLE_SANDBOX=1; R4 onde o
verificador e o seguranca gravam. É guarda contra acidente, não sandbox: subprocesso, glob sem
recursão no PowerShell, nome 8.3, link simbólico, archive -o, HOME com .gitconfig próprio, GIT_CONFIG
antigo e subcomando futuro do reflog ainda contornam (residuais aceitos pelo responsável em 2026-11-19).
Código de segurança (PROCESSO §2).

Uso: python -I "$CLAUDE_PROJECT_DIR/tools/guarda_agentes.py" --perfil <mecanico|seguranca|verificador> || exit 2
"""
import argparse
import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PERFIS = ("mecanico", "seguranca", "verificador")
FERRAMENTAS = ("Bash", "PowerShell", "Read", "Grep", "Glob", "Write", "Edit")

# R1 por lista de liberação (decisão do responsável, 2026-11-19): só git de leitura passa; o resto, inclusive
# alias e subcomando desconhecido, é bloqueado. Os de uso real nas transcrições estão todos aqui.
GIT_LEITURA = frozenset((
    "status", "diff", "log", "show", "grep", "ls-files", "ls-tree", "rev-parse", "rev-list", "archive", "blame",
    "cat-file", "describe", "shortlog", "show-ref", "for-each-ref", "merge-base", "name-rev", "check-ignore",
    "check-attr", "count-objects", "version", "help", "var", "whatchanged", "range-diff", "cherry", "diff-tree",
    "diff-files", "diff-index", "show-branch", "verify-commit", "verify-tag",
))
CHAVES_C_SEGURAS = frozenset(("core.quotepath", "i18n.logoutputencoding", "color.ui"))
# O git aceita abreviação de opção longa: o prefixo (6+ caracteres) de uma destas também conta.
OPCOES_PERIGOSAS = ("--no-index", "--no-exclude-standard", "--open-files-in-pager", "--output")
SYMBOLIC_REF_LEITURA = frozenset(("-q", "--quiet", "--short", "--no-recurse", "--recurse"))
REFLOG_GRAVA = frozenset(("expire", "delete", "drop", "write"))
CONFIG_GRAVA = frozenset(("--add", "--unset", "--unset-all", "--replace-all", "--rename-section", "--remove-section",
                          "--edit", "-e", "set", "unset", "rename-section", "remove-section", "edit"))
# Configuração injetada pelo ambiente: com grep.fallbackToNoIndex, o git grep fora de repositório lê arquivo
# ignorado (o .env). Medido em 2026-11-19 (conferencia_r1_r3_v2.md, sonda p13).
RE_CONFIG_POR_AMBIENTE = re.compile(
    r"fallbacktonoindex|\bGIT_CONFIG_(?:PARAMETERS|COUNT|KEY_\d+|VALUE_\d+|GLOBAL|SYSTEM|NOSYSTEM)\b", re.IGNORECASE)
# Opções globais do git com valor no token seguinte.
OPCOES_COM_VALOR = frozenset(("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix",
                              "--attr-source"))
RE_GIT_PALAVRA = re.compile(r"(?<![\w.-])git(?:\.exe)?[\"']?(?=\s|$)", re.IGNORECASE)
BRANCH_ALTERA = frozenset(("-d", "-D", "-m", "-M", "-c", "-C", "-f", "-u", "--delete", "--move", "--copy", "--force",
                           "--set-upstream-to", "--unset-upstream", "--edit-description", "--track", "--no-track"))
BRANCH_LISTA = frozenset(("--list", "-l", "--contains", "--no-contains", "--merged", "--no-merged", "--points-at"))

NOME_ENV = re.compile(r"^\.env(\..+)?$", re.IGNORECASE)
# .env como palavra num comando: bloqueia .env, .env.local e .env.; não .env.example, x.env nem o \.env$ de regex.
RE_ENV_EM_COMANDO = re.compile(r"(?<![\w.-])\.env(?!\.example\b)(?![\w$-])", re.IGNORECASE)
# Leitores do .env que não citam o nome do arquivo.
RE_LEITOR_DOTENV = re.compile(r"-m\s*dotenv\b|\bdotenv\s+(?:list|get|run)\b|\b(?:dotenv_values|load_dotenv|find_dotenv)\s*\(")

# R3 em comando: atribuição, setx, SetEnvironmentVariable, Set-Item/New-Item e as formas do grep 3.5.
PADROES_SANDBOX_COMANDO = (
    re.compile(r"ORACLE_SANDBOX\s*=\s*[\"']?1\b", re.IGNORECASE),
    re.compile(r"\bsetx\s+ORACLE_SANDBOX\s+[\"']?1\b", re.IGNORECASE),
    re.compile(r"SetEnvironmentVariable\(\s*[\"']ORACLE_SANDBOX[\"']\s*,\s*[\"']1", re.IGNORECASE),
    re.compile(r"(?:Set|New)-Item\s+(?:-Path\s+)?Env:ORACLE_SANDBOX\b[^;|\n]*[\"'\s]1\b", re.IGNORECASE),
)
# R3 em arquivo de teste: só as formas do grep 3.5 do §5 (o .env fictício com ORACLE_SANDBOX=1 é permitido).
PADROES_SANDBOX_TESTE = (
    re.compile(r"setenv\(\s*[\"']ORACLE_SANDBOX[\"']\s*,\s*[\"']1", re.IGNORECASE),
    re.compile(r"environ\[\s*[\"']ORACLE_SANDBOX[\"']\s*\]\s*=\s*[\"']1", re.IGNORECASE),
)
NOME_DECISAO = re.compile(r"^(?:decisao|conferencia)[^/\\]*\.md$", re.IGNORECASE)


# ---------- funções puras (testadas em tests/test_guarda_agentes.py) ----------

def _nome(caminho):
    """Nome final como o Windows o abre: sem fluxo alternativo (:$DATA) nem ponto ou espaço no fim."""
    nome = str(caminho).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return nome.split(":", 1)[0].rstrip(" .")


def e_env(caminho):
    """Nome .env ou .env.* (sem diferenciar maiúsculas), salvo .env.example."""
    nome = _nome(caminho)
    return bool(NOME_ENV.match(nome)) and nome.lower() != ".env.example"


def glob_cobre_env(padrao):
    if not padrao:
        return False
    ultimo = padrao.replace("\\", "/").rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(alvo, p) for alvo, p in ((".env", padrao), ("a/.env", padrao), (".env", ultimo)))


def sem_comentarios(comando):
    """Tira o '# comentário' fora de aspas (as linhas do §5 têm comentário). O estado das aspas segue entre
    linhas e o escape \\ vale como no bash. Comentário com aspas ou crase não é cortado: na dúvida, o texto
    fica e é conferido (cortar a mais esconderia código que roda). Antes, junta a continuação de linha
    (\\ no Bash, crase no PowerShell), como o shell faz."""
    comando = re.sub(r"[\\`]\r?\n", "", comando)
    saida, aspas, i, n = [], None, 0, len(comando)
    while i < n:
        ch = comando[i]
        if aspas == "'":
            if ch == "'":
                aspas = None
        elif ch == "\\" and i + 1 < n:
            saida.append(ch)
            i += 1
            ch = comando[i]
        elif aspas == '"':
            if ch == '"':
                aspas = None
        elif ch in "'\"":
            aspas = ch
        elif ch == "#" and (i == 0 or comando[i - 1].isspace()):
            fim = comando.find("\n", i)
            fim = n if fim == -1 else fim
            if not re.search(r"[\"'`]", comando[i:fim]):
                i = fim
                continue
        saida.append(ch)
        i += 1
    return "".join(saida)


def _tokens(texto):
    try:
        return shlex.split(texto, posix=True)
    except ValueError:
        return texto.split()


def _branch_altera(args):
    if any(a in BRANCH_ALTERA or a.startswith(("--set-upstream-to=", "--track=")) for a in args):
        return True
    posicionais = [a for a in args if not a.startswith("-")]
    return bool(posicionais) and not any(a in BRANCH_LISTA or a.startswith(("--contains=", "--merged=")) for a in args)


def _symbolic_ref_leitura(args):
    opcoes = [a for a in args if a.startswith("-")]
    posicionais = [a for a in args if not a.startswith("-")]
    return len(posicionais) == 1 and all(o in SYMBOLIC_REF_LEITURA for o in opcoes)


def _config_grava(args):
    """Ação de gravação do git config em qualquer posição, inclusive opção longa abreviada (4+ caracteres)."""
    for a in args:
        if a in CONFIG_GRAVA:
            return True
        if a.startswith("--"):
            nome = a.split("=", 1)[0]
            if len(nome) >= 4 and any(o.startswith(nome) for o in CONFIG_GRAVA if o.startswith("--")):
                return True
    return False


def _opcao_perigosa(args):
    """Opção longa que é prefixo (6+ caracteres) de OPCOES_PERIGOSAS, ou -O em grupo curto (abre programa)."""
    for a in args:
        if a.startswith("--"):
            nome = a.split("=", 1)[0]
            if len(nome) >= 6 and any(p.startswith(nome) for p in OPCOES_PERIGOSAS):
                return a
        elif re.match(r"^-[A-Za-z]*O", a):
            return a
    return None


def git_nao_liberado(comando):
    """Primeiro uso de git fora da lista de liberação (subcomando, opção global ou opção do subcomando), ou None."""
    for m in RE_GIT_PALAVRA.finditer(comando):
        trecho = re.split(r"[;&|\n)`]", comando[m.end():], maxsplit=1)[0]
        tokens = _tokens(trecho)
        i = 0
        while i < len(tokens) and tokens[i].startswith("-"):
            t = tokens[i]
            if t == "-c":
                chave = (tokens[i + 1] if i + 1 < len(tokens) else "").split("=", 1)[0].lower()
                if chave not in CHAVES_C_SEGURAS:
                    return f"git -c {chave or '?'} (configuração fora da lista)"
            elif t.startswith(("-c", "--config-env", "--exec-path=")):
                return f"git {t.split('=', 1)[0]} (opção global fora da lista)"
            i += 2 if t in OPCOES_COM_VALOR else 1
        if i >= len(tokens):
            antes = re.split(r"[;&|\n]", comando[:m.start()])[-1]
            if re.search(r"\b(?:xargs|-exec(?:dir)?)\b", antes):
                return "git com subcomando indeterminado (vindo do xargs ou do -exec)"
            continue  # só opções (git --version, git -h) ou o nome sozinho (which git): não grava
        sub, args = tokens[i], tokens[i + 1:]
        if not re.fullmatch(r"[a-z][a-z0-9-]*", sub):
            return f"git com subcomando indeterminado ({sub[:30]})"
        if sub in GIT_LEITURA:
            achado = _opcao_perigosa(args)
            if achado:
                return f"git {sub} {achado} (lê fora do índice, grava arquivo ou abre programa)"
            continue
        if sub == "branch" and not _branch_altera(args):
            continue
        if sub == "config" and not _config_grava(args) and (
                not args or any(a in ("--list", "-l") or a.startswith("--get") for a in args)):
            continue
        if sub == "remote":
            posicionais = [a for a in args if a not in ("-v", "--verbose")]
            if not posicionais or posicionais[0] in ("show", "get-url"):
                continue
        if sub == "reflog" and not any(a in REFLOG_GRAVA for a in args):
            continue
        if sub == "hash-object" and not any(a.startswith("-") and not a.startswith("--") and "w" in a for a in args):
            continue
        if sub == "symbolic-ref" and _symbolic_ref_leitura(args):
            continue
        return f"git {sub} (fora da lista de liberação)"
    return None


def _abs(caminho, cwd):
    caminho = re.sub(r"^/([A-Za-z])(?:/|$)", r"\1:/", str(caminho))  # /c e /c/Users/... (Git Bash) viram C:/...
    p = Path(caminho)
    if not p.is_absolute():
        p = Path(cwd) / p
    return os.path.normcase(os.path.abspath(p))


def cobre_a_raiz(caminho, cwd, raiz):
    """Caminho não expandido ($, %, crase, parêntese, ~ no início) ou que é a raiz do projeto ou um ancestral dela."""
    if not caminho or re.search(r"[$%`(]", caminho) or caminho.startswith("~") or caminho.rstrip("/\\") in (
            "", ".", "*", ".."):
        return True
    alvo, base = _abs(caminho, cwd), os.path.normcase(os.path.abspath(raiz))
    return base == alvo or base.startswith(alvo.rstrip(os.sep) + os.sep)


def busca_recursiva_ampla(comando, cwd, raiz):
    """grep -r sem caminho ou sobre a raiz, findstr /s, Select-String com -Recurse, rg com --hidden/--no-ignore/-u."""
    if re.search(r"\bSelect-String\b", comando, re.IGNORECASE) and re.search(r"-Recurse\b", comando, re.IGNORECASE):
        return "Select-String com -Recurse"
    for trecho in re.split(r"[;&\n]|\|\|", comando):
        if re.search(r"\bfindstr\b[^|]*\s/s\b", trecho, re.IGNORECASE):
            return "findstr /s"
        if re.search(r"\brg\b[^|]*\s(?:--hidden|--no-ignore\S*|-u+)\b", trecho):
            return "rg com --hidden, --no-ignore ou -u"
        for parte in trecho.split("|"):
            tokens = _tokens(parte)
            if not tokens or os.path.basename(tokens[0]) not in ("grep", "egrep", "fgrep"):
                continue
            opcoes = [t for t in tokens[1:] if t.startswith("-")]
            recursivo = any(o in ("--recursive", "--dereference-recursive") or
                            (not o.startswith("--") and re.search(r"[rR]", o[1:])) for o in opcoes)
            if not recursivo:
                continue
            operandos = [t for t in tokens[1:] if not t.startswith("-")]
            padrao_por_opcao = any(o in ("-e", "-f") or o.startswith(("--regexp", "--file")) for o in opcoes)
            caminhos = operandos if padrao_por_opcao else operandos[1:]
            if not caminhos or any(cobre_a_raiz(c, cwd, raiz) for c in caminhos):
                return "grep recursivo sem caminho ou sobre a raiz do projeto"
    return None


def liga_sandbox_comando(texto):
    return any(p.search(texto) for p in PADROES_SANDBOX_COMANDO + PADROES_SANDBOX_TESTE)


def liga_sandbox_teste(texto):
    return any(p.search(texto) for p in PADROES_SANDBOX_TESTE)


def texto_depois_do_edit(caminho, entrada, cwd):
    """Conteúdo do arquivo depois do Edit (para pegar troca de '0' por '1' com contexto); sem o arquivo, o new_string."""
    novo = str(entrada.get("new_string", ""))
    try:
        atual = Path(_abs(caminho, cwd)).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return novo
    velho = str(entrada.get("old_string", ""))
    if not velho:
        return novo
    return atual.replace(velho, novo) if entrada.get("replace_all") else atual.replace(velho, novo, 1)


def dentro_de(caminho, pasta, cwd):
    base = os.path.normcase(os.path.abspath(pasta))
    return _abs(caminho, cwd).startswith(base + os.sep)


def decidir(perfil, ferramenta, entrada, cwd, raiz=None):
    """(bloqueia, motivo). Ferramenta de leitura fora da lista é liberada (o tools: do agente já limita)."""
    raiz = Path(raiz or RAIZ)

    def bloqueio(regra, detalhe, explicacao):
        return True, (f"BLOQUEADO pelo guarda dos subagentes ({regra}, perfil {perfil}): {detalhe}. {explicacao} "
                      "Não contorne: devolva PARE com este motivo.")

    if ferramenta in ("Bash", "PowerShell"):
        limpo = sem_comentarios(str(entrada.get("command", "")))
        if RE_CONFIG_POR_AMBIENTE.search(limpo):
            return bloqueio("R1", "configuração do git injetada pelo ambiente (GIT_CONFIG_*, fallbackToNoIndex)",
                            "Subagente só usa git de leitura, sem configuração injetada.")
        achado = git_nao_liberado(limpo)
        if achado:
            return bloqueio("R1", achado, "Subagente só usa git de leitura (lista de liberação); quem grava e "
                            "commita é a sessão principal.")
        if RE_ENV_EM_COMANDO.search(limpo) or RE_LEITOR_DOTENV.search(limpo):
            return bloqueio("R2", "comando lê ou cita o .env", "Nunca ler, editar ou imprimir o .env.")
        achado = busca_recursiva_ampla(limpo, cwd, raiz)
        if achado:
            return bloqueio("R2", achado, "A busca leria o .env; use a ferramenta Grep (respeita o .gitignore) ou "
                            "limite o caminho.")
        if liga_sandbox_comando(limpo):
            return bloqueio("R3", "ORACLE_SANDBOX=1", "Teste nunca liga o sandbox; só a sessão autorizada.")
        return False, ""

    if ferramenta not in FERRAMENTAS:
        if perfil in ("verificador", "seguranca") and re.search(r"Edit|Write", ferramenta):
            return bloqueio("R4", f"ferramenta de escrita {ferramenta}", f"O {perfil} só grava com Write.")
        return False, ""

    if ferramenta in ("Read", "Write", "Edit") and e_env(entrada.get("file_path", "")):
        return bloqueio("R2", f"{ferramenta} em {entrada.get('file_path')}", "Nunca ler, editar ou imprimir o .env.")
    if ferramenta == "Grep" and (e_env(entrada.get("path", "")) or glob_cobre_env(entrada.get("glob", ""))):
        return bloqueio("R2", "Grep sobre o .env", "Nunca ler, editar ou imprimir o .env.")

    if ferramenta in ("Write", "Edit"):
        caminho = str(entrada.get("file_path", ""))
        texto = str(entrada.get("content", "")) if ferramenta == "Write" else texto_depois_do_edit(caminho, entrada, cwd)
        if dentro_de(caminho, raiz / "tests", cwd) and liga_sandbox_teste(texto):
            return bloqueio("R3", f"{ferramenta} em teste com ORACLE_SANDBOX=1 (forma do grep 3.5)",
                            "Teste nunca define ORACLE_SANDBOX=1 no processo (só \"0\" ou ausente).")
        if perfil in ("verificador", "seguranca"):
            if not dentro_de(caminho, raiz / "docs" / "entregas", cwd):
                return bloqueio("R4", f"{ferramenta} em {caminho}", f"O {perfil} só grava em docs/entregas/<tarefa>/.")
            if perfil == "seguranca" and not NOME_DECISAO.match(Path(caminho).name):
                return bloqueio("R4", f"{ferramenta} em {caminho}",
                                "O seguranca só grava decisao*.md e conferencia*.md.")
    return False, ""


# ---------- execução ----------

def main(argv=None, entrada=None):
    """0 libera; 2 bloqueia (também em entrada inválida ou erro interno)."""
    ap = argparse.ArgumentParser(description="Guarda PreToolUse dos subagentes.")
    ap.add_argument("--perfil", required=True, choices=PERFIS)
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        print("guarda: --perfil inválido; bloqueado por segurança", file=sys.stderr)
        return 2
    try:
        bruto = entrada if entrada is not None else sys.stdin.buffer.read().decode("utf-8", "replace")
        dados = json.loads(bruto)
        ferramenta = dados["tool_name"]
        params = dados.get("tool_input") or {}
        if not isinstance(params, dict) or not isinstance(ferramenta, str):
            raise TypeError("tool_input ou tool_name com tipo inesperado")
        bloqueia, motivo = decidir(args.perfil, ferramenta, params, dados.get("cwd") or str(RAIZ))
    except Exception as e:  # noqa: BLE001  falha fechado
        print(f"guarda: entrada inválida ({type(e).__name__}); bloqueado por segurança", file=sys.stderr)
        return 2
    if bloqueia:
        print(motivo, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
