"""
Guarda dos subagentes do PERSONAL_AGENT: hook PreToolUse declarado no frontmatter de cada agente
(docs/PROCESSO.md §3).

Lê do stdin o JSON do hook (tool_name, tool_input, cwd) e decide: saída 0 libera; saída 2 bloqueia,
com o motivo no stderr, que o agente recebe e deve devolver como PARE, sem contornar. Entrada
inválida ou erro interno também saem com 2. No frontmatter, `onFailure: block` e `|| exit 2` cobrem
falha do próprio hook. Regras do CLAUDE.md: R1 git fora da lista de liberação (só leitura, também
nas opções e sem configuração injetada); R2 conteúdo do .env; R3 ORACLE_SANDBOX=1; R4 onde o
verificador e o seguranca gravam (Write, Edit e, desde o guarda-r4-r5, Bash e PowerShell); R5 nenhum perfil
grava na fiação do guarda (.claude/, este arquivo e o interpretador do hook), checado antes do R4. No shell,
gravação por interpretador (python -c, script), programa que grava por opção própria fora da lista e, no
mecanico, destino não resolvido sem citar a fiação são residuais aceitos (N1, N6). É guarda contra acidente, não sandbox: subprocesso, glob sem
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
import tempfile
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

# R5, fiação do guarda (guarda-r4-r5, decisões do responsável de 2026-11-19): nenhum perfil grava em .claude/
# (qualquer um, também o do usuário), em tools/guarda_agentes.py nem no interpretador do hook (N8: o site roda
# mesmo com -I), nem com autorização literal. Leitura passa.
NOMES_FIACAO = ("sitecustomize.py", "usercustomize.py")
RE_INTERPRETADOR = re.compile(r"^(?:python|pythonw|py|pyw)[\w.-]*\.(?:exe|bat|cmd|ps1)$")
RE_NOME_CURTO_FIACAO = re.compile(r"(?:claude|guarda)~\d", re.IGNORECASE)
MSG_R5 = ("Nenhum subagente grava na fiação do guarda (.claude/, tools/guarda_agentes.py, interpretador do hook), "
          "nem com autorização literal; quem grava é a sessão principal (Opus).")


# ---------- funções puras (testadas em tests/test_guarda_agentes.py) ----------

def _nome(caminho):
    """Nome final como o Windows o abre: sem fluxo alternativo (:$DATA) nem ponto ou espaço no fim."""
    nome = str(caminho).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return nome.split(":", 1)[0].rstrip(" .")


def e_env(caminho):
    """Nome .env ou .env.* (sem diferenciar maiúsculas), salvo .env.example."""
    nome = _nome(caminho)
    return bool(NOME_ENV.match(nome)) and nome.lower() != ".env.example"


def e_documentacao(caminho):
    """Documentação (.md, .txt) pode citar código que liga o sandbox; o R3 não vale para ela."""
    return _nome(caminho).lower().endswith((".md", ".txt"))


def glob_cobre_env(padrao):
    if not padrao:
        return False
    ultimo = padrao.replace("\\", "/").rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(alvo, p) for alvo, p in ((".env", padrao), ("a/.env", padrao), (".env", ultimo)))


def sem_comentarios(comando, dialeto="bash"):
    """Tira o '# comentário' fora de aspas (as linhas do §5 têm comentário). O estado das aspas segue entre
    linhas e o escape \\ vale como no bash. Comentário com aspas ou crase não é cortado: na dúvida, o texto
    fica e é conferido (cortar a mais esconderia código que roda). Antes, junta a continuação de linha do
    dialeto, como o shell faz: \\ só no Bash, crase só no PowerShell. Juntar a do outro dialeto colava a
    palavra anterior ao comando da linha seguinte (A1, guarda-r4-r5). Comentário logo depois da continuação
    do outro dialeto também não é cortado."""
    comando = re.sub(r"`\r?\n" if dialeto == "powershell" else r"\\\r?\n", "", comando)
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
            if not re.search(r"[\"'`]", comando[i:fim]) and not re.search(r"[\\`]\r?\n$", comando[:i]):
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


def _resolvido(caminho, resolver=os.path.realpath):
    """realpath (resolve 8.3, junção e symlink existentes); sem resolver, None."""
    try:
        return os.path.normcase(resolver(caminho))
    except (OSError, ValueError):
        return None


def dentro_de(caminho, pasta, cwd, resolver=os.path.realpath):
    """Estritamente dentro da pasta pelo realpath (resolve 8.3, .., junção e symlink existentes). Sem resolver, fora."""
    base_r = _resolvido(os.path.normcase(os.path.abspath(pasta)), resolver)
    alvo_r = _resolvido(_abs(caminho, cwd), resolver)
    return base_r is not None and alvo_r is not None and alvo_r.startswith(base_r.rstrip(os.sep) + os.sep)


def _componentes(caminho):
    """Componentes como o Windows abre: / no lugar de \\, sem \\\\?\\, sem :fluxo nem ponto ou espaço no fim."""
    texto = str(caminho).replace("\\", "/")
    for prefixo in ("//?/", "//./"):
        if texto.startswith(prefixo):
            texto = texto[len(prefixo):]
    partes = []
    for i, c in enumerate(texto.split("/")):
        if c in (".", ".."):
            partes.append(c)
            continue
        if not (i == 0 and re.fullmatch(r"[A-Za-z]:", c)):
            c = c.split(":", 1)[0]
        c = c.rstrip(" .")
        if c:
            partes.append(c.casefold())
    return partes


def _sob(componentes, base):
    return len(componentes) >= len(base) and componentes[:len(base)] == base


def e_fiacao(caminho, cwd, raiz=None, resolver=os.path.realpath, prefixos=None):
    """R5: o caminho (texto, absoluto ou realpath) é .claude/**, tools/guarda_agentes.py ou o interpretador do hook.
    Casa por nome (também glob no componente e nome curto) e por pasta."""
    raiz = Path(raiz or RAIZ)
    texto = str(caminho)
    if RE_NOME_CURTO_FIACAO.search(texto):
        return True
    formas = [texto]
    try:
        absoluto = _abs(texto, cwd)
        formas.append(absoluto)
    except (OSError, ValueError):
        absoluto = None
    if absoluto:
        resolvido = _resolvido(absoluto, resolver)
        if resolvido:
            formas.append(resolvido)
    prefixos = prefixos if prefixos is not None else {sys.prefix, sys.base_prefix}
    bases = [_componentes(os.path.abspath(raiz / ".claude")),
             _componentes(os.path.abspath(raiz / "tools" / "guarda_agentes.py"))]
    bases += [_componentes(os.path.abspath(p)) for p in prefixos if p]
    for forma in formas:
        comps = _componentes(forma)
        if not comps:
            continue
        if any(fnmatch.fnmatchcase(".claude", c) for c in comps):
            return True
        ultimo = comps[-1]
        if fnmatch.fnmatchcase("guarda_agentes.py", ultimo) or ultimo in NOMES_FIACAO or RE_INTERPRETADOR.match(ultimo):
            return True
        if ultimo.endswith(".pth") and "site-packages" in comps:
            return True
        if any(_sob(comps, b) for b in bases):
            return True
    return False


# ---------- R4 e R5 no shell (guarda-r4-r5: decisao.md §2 e §3, escopo reduzido e fechado) ----------
# Lexer simples por dialeto sobre o comando cru (não usa _tokens nem sem_comentarios: o shlex posix trata \ como
# escape, o que o PowerShell não faz). Variável só do prefixo de atribuições literais; cd só com alvo literal. O
# que não se analisa (shell aninhado, eval, xargs com gravação, splat, .NET, aspas abertas) vira nao_analisavel:
# bloqueia R4 no seguranca e no verificador e, se o texto citar a fiação, R5 em todo perfil. Gravação por
# interpretador (python -c, script) e programa que grava por opção própria fora da lista são residuais (N1, N6).

DESCONHECIDO = "\x00desconhecido"
NULO = "\x00nulo"
ASPAS_SIMPLES_PS = "'\u2018\u2019\u201a\u201b"
ASPAS_DUPLAS_PS = "\"\u201c\u201d\u201e"
LIBERADOS_SEMPRE = frozenset(("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "/dev/fd/0", "/dev/fd/1",
                              "/dev/fd/2", "nul", "nul:"))
RE_FIACAO_TEXTO = re.compile(r"(?i)(?<![\w.-])\.claude(?![\w-])|guarda_agentes\.py|(?:claude|guarda)~\d|"
                             r"site-packages|sitecustomize|usercustomize|\.pth\b|\bpythonw?[\w.-]*\.(?:exe|bat|cmd|ps1)\b")
RE_DOTNET_GRAVA = re.compile(
    r"(?i)\[(?:System\.)?IO\.(?:File|Directory|FileInfo|DirectoryInfo|StreamWriter|FileStream|Path)\]::"
    r"(?!(?:Read\w*|Exists|Get\w*|Enumerate\w*|OpenRead|OpenText|Combine|Join|GetFullPath|GetTempPath)\b)\w+|"
    r"New-Object\s+(?:-TypeName\s+)?(?:System\.)?IO\.(?:StreamWriter|FileStream|FileInfo|DirectoryInfo)|"
    r"\.(?:Delete|MoveTo|CopyTo|Create|CreateText|AppendText|OpenWrite|WriteAllText|WriteAllBytes|WriteAllLines)\s*\(|"
    r"\[scriptblock\]::Create|\$ExecutionContext\.InvokeCommand|\.InvokeScript\s*\(|NewScriptBlock")
RE_TEMP_ATRIBUIDO = re.compile(r"(?i)\$env:te?mp\s*=|(?<![$\w])env:\\?te?mp\b|SetEnvironmentVariable\(\s*['\"]te?mp"
                               r"|(?<![\w$])te?mp=")
SHELLS = frozenset(("bash", "sh", "dash", "zsh", "ksh"))
PWSH = frozenset(("powershell", "pwsh"))
EMBRULHOS = frozenset(("command", "builtin", "exec", "nohup", "time", "winpty", "sudo"))
NOMES_GRAVA_BASH = frozenset(("tee", "cp", "install", "mv", "rm", "rmdir", "mkdir", "touch", "truncate", "dd", "sed",
                              "perl", "ln", "tar", "unzip", "rsync", "curl", "wget", "robocopy", "xcopy"))
CMDLETS = {
    "set-content": "conteudo", "sc": "conteudo", "add-content": "conteudo", "ac": "conteudo",
    "clear-content": "conteudo", "clc": "conteudo", "export-csv": "conteudo", "epcsv": "conteudo",
    "export-clixml": "conteudo", "out-file": "conteudo", "tee-object": "conteudo",
    "new-item": "novo", "ni": "novo", "md": "pasta",
    "copy-item": "copia", "cpi": "copia", "copy": "copia",
    "move-item": "move", "mi": "move", "move": "move",
    "remove-item": "remove", "ri": "remove", "del": "remove", "erase": "remove", "rd": "remove",
    "rename-item": "renomeia", "rni": "renomeia", "ren": "renomeia",
    "expand-archive": "expande", "compress-archive": "comprime",
    "invoke-webrequest": "baixa", "iwr": "baixa", "invoke-restmethod": "baixa", "irm": "baixa",
    "start-process": "opaco", "saps": "opaco", "start": "opaco", "start-transcript": "opaco",
    "set-alias": "opaco", "new-alias": "opaco", "sal": "opaco", "nal": "opaco",
    "invoke-expression": "opaco", "iex": "opaco", "eval": "opaco",
}
# Aliases do PowerShell que no Bash são o programa de mesmo nome.
CMDLETS_SO_PS = {"tee": "conteudo", "mkdir": "pasta", "cp": "copia", "mv": "move", "rm": "remove", "rmdir": "remove"}
PARAMS_DESTINO = ("path", "literalpath", "pspath", "lp", "filepath", "destination", "destinationpath", "outfile",
                  "name", "newname", "target")
PARAMS_VALOR = ("value", "encoding", "delimiter", "filter", "include", "exclude", "itemtype", "type", "stream", "width",
                "inputobject", "variable", "erroraction", "ea", "errorvariable", "ev", "outvariable", "ov",
                "warningaction", "wa", "informationaction", "credential", "childpath", "compressionlevel",
                "outbuffer", "ob", "pipelinevariable", "pv", "warningvariable", "wv", "informationvariable", "iv",
                "progressaction", "uri", "method", "headers", "body", "contenttype", "timeoutsec", "usequotes",
                "quotefields", "session", "fromsession", "tosession")
# Lista fechada de switches dos cmdlets que gravam: parâmetro fora das duas listas torna o comando não analisável
# (senão o valor dele viraria o 1º posicional; D13 da conferência).
SWITCHES_PS = ("force", "append", "noclobber", "nonewline", "passthru", "recurse", "whatif", "confirm", "asbytestream",
               "container", "notypeinformation", "includetypeinformation", "useculture", "verbose", "debug", "raw",
               "update", "usebasicparsing", "skipcertificatecheck")
NOMES_CD = frozenset(("cd", "pushd", "chdir", "set-location", "sl", "push-location"))
PREFIXOS_BASH = frozenset(("!", "if", "then", "elif", "else", "do", "while", "until", "coproc"))
PREFIXOS_PS = frozenset((".", "return", "throw", "exit"))
PALAVRAS_CHAVE_BASH = frozenset(("if", "then", "elif", "else", "fi", "for", "while", "until", "do", "done", "case",
                                 "esac", "select", "function", "coproc"))
PALAVRAS_CHAVE_PS = frozenset(("if", "elseif", "else", "foreach", "for", "while", "do", "until", "switch", "try",
                               "catch", "finally", "trap", "function", "filter", "workflow", "param", "begin",
                               "process", "end"))
NOMES_VOLTA = frozenset(("popd", "pop-location"))


class _Palavra:
    """Palavra do lexer: partes ('lit', texto) | ('var', nome) | ('env', nome) | ('nulo',) | ('sub', corpo) | ('x',)."""
    __slots__ = ("partes", "bruto", "inicio", "chaves")

    def __init__(self, inicio):
        self.partes, self.bruto, self.inicio, self.chaves = [], "", inicio, False


def _fecha_par(texto, i, ps):
    """Índice do ')' que fecha o '(' anterior a i, com aspas; -1 se não fecha."""
    prof, n = 1, len(texto)
    while i < n:
        ch = texto[i]
        if ch in (ASPAS_SIMPLES_PS if ps else "'"):
            fim = _fim_simples(texto, i + 1, ps)
            if fim < 0:
                return -1
            i = fim
        elif ch in (ASPAS_DUPLAS_PS if ps else '"'):
            j = i + 1
            while j < n and texto[j] not in (ASPAS_DUPLAS_PS if ps else '"'):
                j += 2 if texto[j] == ("`" if ps else "\\") else 1
            if j >= n:
                return -1
            i = j
        elif ch == ("`" if ps else "\\"):
            i += 1
        elif ch == "(":
            prof += 1
        elif ch == ")":
            prof -= 1
            if prof == 0:
                return i
        i += 1
    return -1


def _fim_simples(texto, i, ps):
    """Índice da aspa simples que fecha (no PowerShell, '' é aspa literal); -1 se não fecha."""
    n = len(texto)
    while i < n:
        if texto[i] in (ASPAS_SIMPLES_PS if ps else "'"):
            if ps and i + 1 < n and texto[i + 1] in ASPAS_SIMPLES_PS:
                i += 2
                continue
            return i
        i += 1
    return -1


def _lexar(cmd, ps):
    """(itens, falha). Itens: ('w', palavra) | ('op', s) | ('redir', palavra, op) | ('abre',) | ('fecha',)."""
    itens, n, i = [], len(cmd), 0
    estado = {"atual": None, "redir": None, "falha": False}
    heredocs = []

    def palavra():
        if estado["atual"] is None:
            estado["atual"] = _Palavra(i)
        return estado["atual"]

    def fecha(fim):
        p = estado["atual"]
        if p is None:
            return
        p.bruto = cmd[p.inicio:fim]
        juntas = []
        for parte in p.partes:  # literais vizinhos viram um só (NOME=valor é reconhecido pelo 1º literal)
            if parte[0] == "lit" and juntas and juntas[-1][0] == "lit":
                juntas[-1] = ("lit", juntas[-1][1] + parte[1])
            else:
                juntas.append(parte)
        p.partes = juntas
        if estado["redir"] is not None:
            itens.append(("redir", p, estado["redir"]))
            estado["redir"] = None
        else:
            itens.append(("w", p))
        estado["atual"] = None

    def lit(texto):
        palavra().partes.append(("lit", texto))

    def expansao(j, em_aspas):
        """Lê a expansão que começa no $ em j; devolve o índice seguinte."""
        p = palavra()
        if j + 1 >= n:
            p.partes.append(("lit", "$"))
            return j + 1
        nx = cmd[j + 1]
        if nx == "(":
            fim = _fecha_par(cmd, j + 2, ps)
            if fim < 0:
                estado["falha"] = True
                return n
            p.partes.append(("sub", cmd[j + 2:fim]))
            return fim + 1
        if nx == "{":
            fim = cmd.find("}", j + 2)
            if fim < 0:
                estado["falha"] = True
                return n
            dentro = cmd[j + 2:fim]
            p.partes.append(("var", dentro.lower() if ps else dentro) if re.fullmatch(r"[A-Za-z_]\w*", dentro)
                            else ("x",))
            return fim + 1
        if ps:
            m = re.match(r"([A-Za-z_]\w*)(:([A-Za-z_]\w*))?", cmd[j + 1:])
            if not m:
                p.partes.append(("x",) if nx in "?$^_" else ("lit", "$"))
                return j + 2 if nx in "?$^_" else j + 1
            if m.group(2):
                escopo = m.group(1).lower()
                p.partes.append(("env", m.group(3).upper()) if escopo == "env" else ("x",))
            elif m.group(1).lower() == "null":
                p.partes.append(("nulo",))
            else:
                p.partes.append(("var", m.group(1).lower()))
            return j + 1 + m.end()
        if nx == "'" and not em_aspas:
            k = j + 2
            while k < n and cmd[k] != "'":
                k += 2 if cmd[k] == "\\" else 1
            if k >= n:
                estado["falha"] = True
                return n
            p.partes.append(("x",))
            return k + 1
        m = re.match(r"[A-Za-z_]\w*", cmd[j + 1:])
        if m:
            p.partes.append(("var", m.group(0)))
            return j + 1 + m.end()
        if nx in "0123456789@*#?$!-":
            p.partes.append(("x",))
            return j + 2
        if nx == '"' and not em_aspas:
            p.partes.append(("x",))  # $"..." (tradução de locale): a string, sem o $ (D5 da conferência)
            return j + 1
        p.partes.append(("lit", "$"))
        return j + 1

    def heredoc_corpos(j):
        """Consome os corpos dos heredocs pendentes a partir da linha depois de j; devolve o fim do último."""
        for delim, com_aspas, tira in heredocs:
            achou = False
            while j < n:
                ini = j + 1
                fim = cmd.find("\n", ini)
                fim = n if fim < 0 else fim
                linha = cmd[ini:fim].rstrip("\r")
                if (linha.lstrip("\t") if tira else linha) == delim:
                    j, achou = fim, True
                    break
                if not com_aspas and ("$(" in linha or "`" in linha):
                    estado["falha"] = True
                j = fim
            if not achou:
                estado["falha"] = True
                return n
        heredocs.clear()
        return j

    while i < n and not estado["falha"]:
        ch = cmd[i]
        if ch == "\n":
            fecha(i)
            if heredocs:
                i = heredoc_corpos(i)
            itens.append(("op", "\n"))
            i += 1
            continue
        if ch in " \t\r":
            fecha(i)
            i += 1
            continue
        if ps and cmd.startswith("<#", i):
            fim = cmd.find("#>", i + 2)
            if fim < 0:
                estado["falha"] = True
                break
            fecha(i)
            i = fim + 2
            continue
        if ch == "#" and estado["atual"] is None:
            fim = cmd.find("\n", i)
            i = n if fim < 0 else fim
            continue
        if not ps and ch == "\\":
            if i + 1 < n and cmd[i + 1] == "\n":
                i += 2
                continue
            if i + 1 < n:
                lit(cmd[i + 1])
            i += 2
            continue
        if ps and ch == "`":
            if i + 1 < n and cmd[i + 1] in "\r\n":
                i += 3 if cmd[i + 1:i + 3] == "\r\n" else 2
                continue
            if i + 1 < n:
                lit(cmd[i + 1])
            i += 2
            continue
        if ch in (ASPAS_SIMPLES_PS if ps else "'"):
            fim = _fim_simples(cmd, i + 1, ps)
            if fim < 0:
                estado["falha"] = True
                break
            texto = cmd[i + 1:fim]
            lit(re.sub("[" + ASPAS_SIMPLES_PS + "]{2}", "'", texto) if ps else texto)
            i = fim + 1
            continue
        if ch in (ASPAS_DUPLAS_PS if ps else '"'):
            palavra()
            j = i + 1
            while j < n and cmd[j] not in (ASPAS_DUPLAS_PS if ps else '"'):
                c = cmd[j]
                if c == ("`" if ps else "\\") and j + 1 < n:
                    seguinte = cmd[j + 1]
                    if ps and seguinte not in "`\"$'" + ASPAS_DUPLAS_PS:
                        estado["atual"].partes.append(("x",))
                    elif not ps and seguinte not in "$`\"\\\n":
                        lit(c + seguinte)
                    elif seguinte != "\n":
                        lit(seguinte)
                    j += 2
                elif c == "$":
                    j = expansao(j, True)
                elif not ps and c == "`":
                    fim = cmd.find("`", j + 1)
                    if fim < 0:
                        estado["falha"] = True
                        break
                    estado["atual"].partes.append(("sub", cmd[j + 1:fim]))
                    j = fim + 1
                else:
                    lit(c)
                    j += 1
            if j >= n:
                estado["falha"] = True
                break
            i = j + 1
            continue
        if ch == "$":
            i = expansao(i, False)
            continue
        if not ps and ch == "`":
            fim = cmd.find("`", i + 1)
            if fim < 0:
                estado["falha"] = True
                break
            palavra().partes.append(("sub", cmd[i + 1:fim]))
            i = fim + 1
            continue
        if ps and ch == "@" and estado["atual"] is None and i + 1 < n and cmd[i + 1] in "'\"(":
            if cmd[i + 1] == "(":
                fim = _fecha_par(cmd, i + 2, ps)
                if fim < 0:
                    estado["falha"] = True
                    break
                palavra().partes.append(("sub", cmd[i + 2:fim]))
                i = fim + 1
                continue
            m = re.match(r"@(['\"])[ \t]*\r?\n", cmd[i:])
            if m:
                q = m.group(1)
                fim = re.search(r"\n" + q + "@", cmd[i + m.end() - 1:])
                if not fim:
                    estado["falha"] = True
                    break
                corpo = cmd[i + m.end():i + m.end() - 1 + fim.start()]
                if q == '"' and "$(" in corpo:
                    estado["falha"] = True
                palavra().partes.append(("x",))
                i = i + m.end() - 1 + fim.end()
                continue
        # Redirecionamentos.
        if ch in "<>" or (ch == "&" and i + 1 < n and cmd[i + 1] == ">") or (
                ps and ch == "*" and i + 1 < n and cmd[i + 1] == ">"):
            atual = estado["atual"]
            if atual is not None and re.fullmatch(r"\d+", cmd[atual.inicio:i]) or (
                    atual is not None and ps and cmd[atual.inicio:i] == "*"):
                estado["atual"] = None  # descritor colado ao operador
            elif atual is not None and not ps and re.fullmatch(r"\{\w+\}", cmd[atual.inicio:i]):
                estado["atual"] = None
            else:
                fecha(i)
            if ch in "&*":
                i += 1
            if cmd.startswith("<<<", i):
                estado["redir"] = "<"
                i += 3
                continue
            if not ps and cmd.startswith("<<", i):
                m = re.match(r"<<(-?)[ \t]*((?:'[^'\n]*'|\"[^\"\n]*\"|\\.|[^\s;&|<>()])+)", cmd[i:])
                if not m:
                    estado["falha"] = True
                    break
                bruto = m.group(2)
                heredocs.append((re.sub(r"[\"'\\]", "", bruto), bool(re.search(r"[\"'\\]", bruto)),
                                 m.group(1) == "-"))
                i += m.end()
                continue
            if cmd.startswith("<(", i) or cmd.startswith(">(", i):
                fim = _fecha_par(cmd, i + 2, ps)  # process substitution: o comando de dentro é analisado
                if fim < 0:
                    estado["falha"] = True
                    break
                estado["atual"] = None
                palavra().partes.append(("sub", cmd[i + 2:fim]))
                i = fim + 1
                continue
            if ch == "<" and not cmd.startswith("<>", i):
                estado["redir"] = "<"
                i += 1
                continue
            m = re.match(r"(?:<>|>>?\|?)(&)?", cmd[i:])
            i += m.end()
            if m.group(1):
                m2 = re.match(r"(?:\d+|-)(?=[\s;|&()<>]|$)", cmd[i:])  # >&1/../x é arquivo (D6)
                if m2:
                    i += m2.end()  # junção (2>&1, >&-): não é destino
                    continue
            estado["redir"] = ">"
            continue
        if ch in ";|&()":
            fecha(i)
            if cmd.startswith("&&", i) or cmd.startswith("||", i):
                itens.append(("op", cmd[i:i + 2]))
                i += 2
            elif ch == "|":
                itens.append(("op", "|"))
                i += 2 if cmd.startswith("|&", i) else 1
            elif ch == "&" and ps:
                p = _Palavra(i)
                p.partes.append(("lit", "&"))
                p.bruto = "&"
                itens.append(("w", p))
                i += 1
            elif ch in ";&":
                itens.append(("op", ch))
                i += 1
            else:
                itens.append(("abre",) if ch == "(" else ("fecha",))
                i += 1
            continue
        if ch in "{}":
            seguinte = cmd[i + 1] if i + 1 < n else " "
            if ps or (estado["atual"] is None and seguinte in " \t\r\n;") or (ch == "}" and estado["atual"] is None):
                fecha(i)
                itens.append(("abre",) if ch == "{" else ("fecha",))
                i += 1
                continue
            palavra().chaves = True
        lit(ch)
        i += 1
    fecha(n)
    if heredocs or estado["redir"] is not None:
        estado["falha"] = True
    return itens, estado["falha"]


class _Comando:
    __slots__ = ("palavras", "redirs", "op", "prof", "inicio", "fim", "segmento")

    def __init__(self, op, prof, segmento):
        self.palavras, self.redirs, self.op, self.prof = [], [], op, prof
        self.inicio, self.fim, self.segmento = None, None, segmento


QUEBRAS = frozenset((";", "\n", "||", "&", "|"))


def _comandos(itens):
    """Agrupa os itens em comandos simples, com o operador anterior, a profundidade e o segmento: o número de
    separadores do nível 0 que não são && (;, newline, ||, &, |). No mesmo segmento, o comando só roda se os
    anteriores da cadeia && rodaram."""
    cmds, prof, op, segmento = [], 0, None, 0
    atual = _Comando(op, prof, segmento)
    for item in itens:
        tipo = item[0]
        if tipo in ("w", "redir"):
            p = item[1]
            if atual.inicio is None:
                atual.inicio = p.inicio
            atual.fim = max(atual.fim or 0, p.inicio + len(p.bruto))
            (atual.palavras.append(p) if tipo == "w" else atual.redirs.append((item[2], p)))
            continue
        if atual.palavras or atual.redirs:
            cmds.append(atual)
        if tipo == "op":
            op = item[1]
            if prof == 0 and op in QUEBRAS:
                segmento += 1
        else:
            prof += 1 if tipo == "abre" else -1
            op = "(" if tipo == "abre" else ")"
        atual = _Comando(op, max(prof, 0), segmento)
    if atual.palavras or atual.redirs:
        cmds.append(atual)
    return cmds, prof != 0


def _expandir(p, variaveis, ambiente, temp_atribuido, ps):
    """Valor da palavra, ou None se tem expansão que não se resolve."""
    if p.chaves:
        return None
    partes = p.partes
    if len(partes) == 1 and partes[0][0] == "nulo":
        return NULO
    saida = []
    for k, parte in enumerate(partes):
        tipo = parte[0]
        if tipo == "lit":
            if k == 0 and parte[1].startswith("~") and not p.bruto.startswith(("'", '"')):
                return None
            saida.append(parte[1])
        elif tipo == "var":
            valor = variaveis.get(parte[1])
            if valor is None:
                return None
            saida.append(valor)
        elif tipo == "env" and ps and parte[1] in ("TEMP", "TMP") and not temp_atribuido:
            valor = ambiente.get(parte[1])
            if not valor:
                return None
            saida.append(valor)
        else:
            return None
    return "".join(saida)


def _atribuicao(cmd, ps, expandir):
    """[(nome, valor ou None)] se o comando é só atribuição; senão None."""
    w = cmd.palavras
    if not w or cmd.redirs:
        return None
    if ps and w[0].partes and w[0].partes[0][0] == "var":
        nome, partes = w[0].partes[0][1], w[0].partes[1:]
        if not partes and len(w) >= 2 and w[1].bruto == "=":
            resto = w[2:]
        elif partes and partes[0][0] == "lit" and partes[0][1].startswith("=") and len(w) == 1:
            colado = _Palavra(w[0].inicio)
            colado.partes = ([("lit", partes[0][1][1:])] if partes[0][1][1:] else []) + partes[1:]
            colado.bruto = w[0].bruto.split("=", 1)[1]
            resto = [colado]
        else:
            return None
        if ps and resto and resto[0].bruto.lower() == "join-path":
            args = [a for a in resto[1:] if not a.bruto.startswith("-")]
            valores = [expandir(a) for a in args]
            valor = None if not valores or any(v is None for v in valores) else "\\".join(valores)
        elif len(resto) == 1:
            valor = expandir(resto[0])
        else:
            valor = None
        return [(nome, valor)]
    if ps:
        return None
    saida = []
    for k, p in enumerate(w):
        if k == 0 and p.bruto == "export":
            continue
        primeira = p.partes[0] if p.partes else None
        m = re.match(r"([A-Za-z_]\w*)(\+?)=", primeira[1]) if primeira and primeira[0] == "lit" else None
        if not m:
            return None
        resto = _Palavra(p.inicio)
        resto.partes = [("lit", primeira[1][m.end():])] + p.partes[1:]
        resto.bruto = p.bruto[m.end():]
        resto.chaves = p.chaves
        saida.append((m.group(1), None if m.group(2) else expandir(resto)))
    return saida or None


def _nome_comando(valor):
    if valor is None:
        return None
    base = re.split(r"[\\/]", valor)[-1].lower()
    return base[:-4] if base.endswith(".exe") else base


def _opcoes_bash(args, com_valor=(), com_valor_longo=()):
    """(curtas, longas, valores, operandos) de uma lista de (bruto, valor) no estilo getopt."""
    curtas, longas, valores, operandos, k, fim_opcoes = set(), set(), {}, [], 0, False
    while k < len(args):
        bruto, valor = args[k]
        v = valor or ""
        if fim_opcoes or not v.startswith("-") or v == "-":
            operandos.append(args[k])
        elif v == "--":
            fim_opcoes = True
        elif v.startswith("--"):
            nome, _, inline = v[2:].partition("=")
            longas.add(nome)
            if nome in com_valor_longo:
                if inline:
                    valores[nome] = (inline, inline)
                elif k + 1 < len(args):
                    valores[nome] = args[k + 1]
                    k += 1
        else:
            for pos, letra in enumerate(v[1:]):
                curtas.add(letra)
                if letra in com_valor:
                    resto = v[2 + pos:]
                    if resto:
                        valores[letra] = (resto, resto)
                    elif k + 1 < len(args):
                        valores[letra] = args[k + 1]
                        k += 1
                    break
        k += 1
    return curtas, longas, valores, operandos


def _parametros_ps(args):
    """(nomeados {param: [(bruto, valor)]}, posicionais, switches) com abreviação pelo prefixo único."""
    conhecidos = PARAMS_DESTINO + PARAMS_VALOR
    nomeados, posicionais, switches, k, desconhecido = {}, [], set(), 0, False
    while k < len(args):
        bruto, valor = args[k]
        m = re.fullmatch(r"-([A-Za-z][\w-]*)(?::(.*))?", valor or "") if not bruto.startswith(("'", '"')) else None
        if not m:
            posicionais.append(args[k])
            k += 1
            continue
        nome = m.group(1).lower()
        if nome in SWITCHES_PS:
            switches.add(nome)
            k += 1
            continue
        candidatos = [c for c in conhecidos if c == nome] or [c for c in conhecidos if c.startswith(nome)]
        de_switch = [s for s in SWITCHES_PS if s.startswith(nome)]
        # Abreviação que casa switch e parâmetro ao mesmo tempo (-D, -N) é ambígua: não analisável (E10). Nome exato
        # de parâmetro conhecido vale como ele (-Include não é -IncludeTypeInformation).
        if nome not in conhecidos and (not candidatos or de_switch):
            if de_switch and not candidatos:
                switches.add(nome)
            else:
                desconhecido = True
            k += 1
            continue
        destino = next((c for c in candidatos if c in PARAMS_DESTINO), None)
        chave = candidatos[0] if len(candidatos) == 1 else (destino or candidatos[0])
        if m.group(2) is not None:
            nomeados.setdefault(chave, []).append((m.group(2), m.group(2)))
        elif k + 1 < len(args):
            nomeados.setdefault(chave, []).append(args[k + 1])
            k += 1
        k += 1
    return nomeados, posicionais, switches, desconhecido


def analisar_gravacao(comando, dialeto, cwd, ambiente=None, prof=0, cands=None, variaveis=None):
    """(destinos, nao_analisavel). Destino: dict(bruto, valor, valores (set de absolutos ou None), tipo, so_r5,
    fora). Tipo: grava, remove, recursivo, pasta. Função pura (ambiente injetável)."""
    ps = dialeto == "powershell"
    ambiente = os.environ if ambiente is None else ambiente
    destinos = []
    if prof > 8:
        return destinos, True
    itens, falha = _lexar(comando, ps)
    cmds, desbalanceado = _comandos(itens)
    falha = falha or desbalanceado or bool(RE_DOTNET_GRAVA.search(comando))
    temp_atribuido = bool(RE_TEMP_ATRIBUIDO.search(comando))
    variaveis = dict(variaveis or {})
    cands = set(cands) if cands else {os.path.abspath(cwd)}
    cadeia = None

    def expandir(p):
        return _expandir(p, variaveis, ambiente, temp_atribuido, ps)

    def resolver(bruto, valor, base, tipo, so_r5=False):
        d = {"bruto": bruto, "valor": valor, "valores": None, "tipo": tipo, "so_r5": so_r5, "fora": False}
        if valor == NULO or (valor is not None and valor.lower() in LIBERADOS_SEMPRE):
            return
        if valor is not None:
            v = re.sub(r"(?i)^(?:Microsoft\.PowerShell\.Core\\)?FileSystem::", "", valor)
            if re.match(r"(?i)^(?:env|variable|function|alias):", v):
                return
            if re.match(r"(?i)^(?:hkcu|hklm|cert|wsman):|^registry::", v):
                d["fora"] = True
            elif v and not re.match(r"(?i)^[A-Za-z]{2,}:", v) and not v.startswith("~"):
                componentes = re.split(r"[\\/]", v)
                if not any(re.search(r"[*?\[]", c) for c in componentes[:-1]):
                    absoluto = re.match(r"^(?:[A-Za-z]:|[\\/])", v)
                    if absoluto:
                        d["valores"] = {_abs(v, cwd)}
                    elif DESCONHECIDO not in base:
                        d["valores"] = {_abs(v, b) for b in base}
        destinos.append(d)

    def aninhar(texto, dialeto_dentro):
        """bash -c, powershell -Command com texto literal: analisa o texto como comando do dialeto."""
        sub_d, sub_f = analisar_gravacao(texto, dialeto_dentro, cwd, ambiente, prof + 1, base, None)
        destinos.extend(sub_d)
        return sub_f

    # Atribuição vale se for do nível 0, depois de ;, newline, && ou do início, e antes de qualquer palavra-chave
    # ou atribuição recusada (encerrado). Depois de um comando que pode falhar no mesmo segmento, ela é condicional:
    # só vale no mesmo segmento (se o comando falhou, a atribuição e o resto da cadeia && não rodaram).
    condicionais, segmento_atual, pode_falhar, encerrado = {}, None, False, False
    palavras_chave = PALAVRAS_CHAVE_PS if ps else PALAVRAS_CHAVE_BASH
    base = cands
    # CDPATH (citado no comando ou no ambiente) muda o alvo do cd relativo do Bash (D8 da conferência).
    cdpath = not ps and bool(re.search(r"\bCDPATH\b", comando) or ambiente.get("CDPATH"))
    for k, c in enumerate(cmds):
        proximo = cmds[k + 1].op if k + 1 < len(cmds) else None
        if c.op != "&&" and cadeia is not None:
            cands |= cadeia
            cadeia = None
        base = cadeia if cadeia is not None else cands
        if c.segmento != segmento_atual:
            segmento_atual, pode_falhar = c.segmento, False
        for nome, seg in list(condicionais.items()):
            if seg != c.segmento:
                variaveis[nome] = None
                del condicionais[nome]
        for p in c.palavras + [r[1] for r in c.redirs]:
            for parte in p.partes:
                if parte[0] == "sub":
                    sub_d, sub_f = analisar_gravacao(parte[1], dialeto, cwd, ambiente, prof + 1, base, variaveis)
                    destinos.extend(sub_d)
                    falha = falha or sub_f
        trecho = comando[c.inicio:c.fim] if c.inicio is not None else ""
        if ps and c.palavras and c.palavras[0].bruto.startswith("$"):
            # $x = Set-Content ... e $null = ...: o lado direito também é comando (D2, D3 da conferência).
            m = re.match(r"\s*\$[\w:{}]+\s*[-+*/]?=(?!=)\s*(\S.*)", trecho, re.S)
            if m:
                falha = aninhar(m.group(1), "powershell") or falha
        primeira = (c.palavras[0].bruto if c.palavras else "").lower()
        if primeira in palavras_chave:
            encerrado = True
        atrib = _atribuicao(c, ps, expandir)
        aceita = not encerrado and c.prof == 0 and c.op in (None, ";", "\n", "&&")
        if atrib is not None and aceita:
            for nome, valor in atrib:
                variaveis[nome] = valor
                if pode_falhar:
                    condicionais[nome] = c.segmento
                else:
                    condicionais.pop(nome, None)
            if any(parte[0] == "sub" for p in c.palavras for parte in p.partes):
                pode_falhar = True  # X=$(false) falha e encerra a cadeia &&
            continue
        if atrib is not None:
            encerrado = True
            for nome, _ in atrib:
                variaveis[nome] = None
            continue
        # cd seguido de & ou |, ou numa lista &&/|| que termina em &, roda em subshell no Bash e não muda o cwd
        # (D7 e E2 das conferências).
        j = k + 1
        while j < len(cmds) and cmds[j].op in ("&&", "||", "|"):
            j += 1
        fim_lista = cmds[j].op if j < len(cmds) else None
        cd_fixo = (_cd_para_pasta_existente(c, ps, expandir, base)
                   if aceita and not pode_falhar and not c.redirs and not cdpath and
                   (ps or (proximo not in ("|", "&") and fim_lista != "&")) else None)
        if cd_fixo is not None:
            cands, cadeia = cd_fixo, None  # cd incondicional para pasta literal que existe: não falha
            continue
        pode_falhar = True
        for nome in list(variaveis):  # variável citada como palavra solta (for X, read X, -OutVariable X)
            nome_re = re.escape(nome)
            if re.search(r"(?<![^\s;(|&])" + nome_re + r"(?![^\s;)=|&+])", trecho, re.IGNORECASE if ps else 0) or (
                    ps and re.search(r"\$" + nome_re + r"\s*(?:[-+*/]?=(?!=)|\s+in\b)", trecho, re.IGNORECASE)):
                variaveis[nome] = None
        for op, p in c.redirs:
            if op != "<":
                resolver(p.bruto, expandir(p), base, "grava")
        args = [(p.bruto, expandir(p)) for p in c.palavras]
        if not ps:
            while args and re.match(r"[A-Za-z_]\w*\+?=", args[0][0]):
                args = args[1:]  # NOME=v cmd: ambiente só do comando
        # Palavras que só introduzem o comando (then cp ..., ! touch ..., . Set-Content ..., return sc ...): D1, D4, D9.
        prefixos = PREFIXOS_PS if ps else PREFIXOS_BASH
        while args and args[0][0].lower() in prefixos:
            args = args[1:]
        falha = _despachar(args, ps, base, resolver, aninhar) or falha
        nome = _nome_comando(args[0][1]) if args else None
        if nome in NOMES_CD:
            alvo = next((a for a in args[1:] if not (a[1] or "").startswith("-") or a[1] == "-"), None)
            if alvo is None or alvo[1] is None or alvo[1] in ("-", "") or alvo[1].startswith("~") or \
                    DESCONHECIDO in base or (cdpath and not re.match(r"(?:\.\.?(?:[\\/]|$)|[A-Za-z]:|[\\/])",
                                                                       alvo[1])):
                novo = {DESCONHECIDO}
            else:
                novo = {_abs(alvo[1], b) for b in base}
            if c.prof > 0:
                cands |= novo
                cadeia = None
            else:
                cadeia = novo
        elif nome in NOMES_VOLTA:
            cands |= {DESCONHECIDO}
    return destinos, falha


def _cd_para_pasta_existente(c, ps, expandir, base):
    """Novos candidatos de cwd se o comando é cd para pasta literal que já existe em toda a base; senão None."""
    args = [(p.bruto, expandir(p)) for p in c.palavras]
    if not args or _nome_comando(args[0][1]) not in NOMES_CD or DESCONHECIDO in base:
        return None
    resto = [a for a in args[1:] if (a[1] or "").lower() not in ("-literalpath", "-path", "-lp")]
    if len(resto) != 1:
        return None
    alvo = resto[0][1]
    if alvo is None or alvo in ("", "-") or alvo.startswith(("~", "-")):
        return None
    novo = {_abs(alvo, b) for b in base}
    return novo if all(os.path.isdir(d) for d in novo) else None


def _despachar(args, ps, base, resolver, aninhar):
    """Registra os destinos do comando; devolve True se o comando não se analisa."""
    if not args:
        return False
    bruto0, valor0 = args[0]
    if ps and valor0 == "&":
        args = args[1:]
        if not args:
            return True
        bruto0, valor0 = args[0]
    if valor0 is None:
        if ps and bruto0.startswith(("$", "'", '"', "@")):
            return False  # expressão do PowerShell ($s | ..., $x = ...): não executa programa
        return not (len(args) >= 2 and args[1][1] == "=")  # $x = ... passado como Bash
    nome = _nome_comando(valor0)
    resto = args[1:]
    if nome == "env":
        k = 0
        while k < len(resto):
            v = resto[k][1] or ""
            if v in ("-C", "-S") or v.startswith(("--chdir", "--split-string")):
                return True
            if v in ("-u",):
                k += 2
            elif v.startswith("-") or re.match(r"[A-Za-z_]\w*=", v):
                k += 1
            else:
                break
        return _despachar(resto[k:], ps, base, resolver, aninhar)
    if nome in EMBRULHOS:
        if resto and (resto[0][1] or "").startswith("-"):
            # command -v/-V só consulta; outro embrulho com opção (command -p, exec -a, time -p) é opaco (D15).
            return not (nome == "command" and resto[0][1] in ("-v", "-V"))
        return _despachar(resto, ps, base, resolver, aninhar)
    if nome in ("nice", "timeout", "stdbuf") and any(
            (a[1] or "") in ("-s", "-k", "-i", "-o", "-e", "--signal", "--kill-after", "--input", "--output",
                             "--error", "--adjustment") for a in resto):
        return True  # opção com valor separado: o guarda não sabe onde começa o comando (E12)
    if nome == "nice":
        k = 2 if resto and resto[0][1] == "-n" else (1 if resto and (resto[0][1] or "").startswith("-") else 0)
        return _despachar(resto[k:], ps, base, resolver, aninhar)
    if nome in ("timeout", "stdbuf"):
        k = 0
        while k < len(resto) and (resto[k][1] or "").startswith("-"):
            k += 1
        return _despachar(resto[k + (1 if nome == "timeout" else 0):], ps, base, resolver, aninhar)
    if nome in SHELLS:
        # O -c vale em qualquer posição (bash -o pipefail -c ...). Sem -c: com script é interpretador (residual);
        # sem script ou com -s, lê o comando da entrada (| bash, <<<): opaco (E5, E6).
        if any(a[1] is None for a in resto):
            return True
        for k, a in enumerate(resto):
            if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", a[1]):
                if k + 1 >= len(resto):
                    return True
                return aninhar(resto[k + 1][1], "bash")
        k = 0
        while k < len(resto) and resto[k][1].startswith(("-", "+")):
            if resto[k][1] in ("-s", "--"):
                return True
            k += 2 if resto[k][1] in ("-o", "+o", "-O", "+O") else 1
        return k >= len(resto)
    if nome in PWSH:
        valores = [(a[1] or "").lower() for a in resto]
        if any(a[1] is None for a in resto) or any(re.fullmatch(r"-e(?:c|n\w*)?", v) for v in valores):
            return True  # -EncodedCommand e abreviações: opaco
        for k, v in enumerate(valores):
            if re.fullmatch(r"-c(?:o\w*)?", v):  # -Command em qualquer posição (-ExecutionPolicy Bypass -Command)
                texto = resto[k + 1:]
                if not texto or texto[0][1] == "-":
                    return True  # -Command -: lê da entrada (E5)
                return aninhar(" ".join(t[1] for t in texto), "powershell")
        return not any(v in ("-file", "-f") for v in valores)  # -File: interpretador; o resto, opaco
    if nome == "cmd":
        texto = " ".join(a[0] for a in resto)
        # cmd /c (e //c do Git Bash) é shell aninhado: não analisável (D10, D11 da conferência).
        return bool(re.search(r"(?i)(?:^|\s)/{1,2}[ckr]\b", texto))
    if nome in ("xargs",) or (nome == "find" and any((a[1] or "") in ("-exec", "-execdir", "-ok", "-okdir")
                                                       for a in resto)):
        nomes = {_nome_comando(a[1]) for a in resto}
        return bool(nomes & (NOMES_GRAVA_BASH | SHELLS | PWSH | set(CMDLETS) | {"cmd"})) or any(
            a[1] is None for a in resto)
    if nome == "find":
        return any((a[1] or "") in ("-delete", "-fprint", "-fprint0", "-fprintf", "-fls") for a in resto)
    if nome == "fsutil":
        return any((a[1] or "").lower() == "hardlink" for a in resto)
    tipo_ps = CMDLETS.get(nome) or (CMDLETS_SO_PS.get(nome) if ps else None)
    if tipo_ps:
        return _cmdlet(tipo_ps, resto, base, resolver)
    if nome in NOMES_GRAVA_BASH:
        return _utilitario(nome, resto, base, resolver, ps)
    return False


def _e_pasta(destino, base):
    """Destino de cópia que é pasta: termina em / ou \\, é . ou .., ou já existe como pasta (na dúvida, pasta)."""
    bruto, valor = destino
    limpo = re.sub(r"[\"'`]", "", bruto)
    if limpo.endswith(("/", "\\")) or (valor or "") in (".", "..") or valor is None:
        return True
    return any(b != DESCONHECIDO and os.path.isdir(_abs(valor, b)) for b in base)


def _registrar_junto(destino, fonte, registrar):
    """dest/basename(fonte), só para o R5 (cp x tools/ com fonte chamada guarda_agentes.py)."""
    nome_fonte = re.split(r"[\\/]", re.sub(r"[\"'`]", "", fonte[0]).rstrip("\\/"))[-1]
    junto = None if destino[1] is None or "$" in nome_fonte else destino[1].rstrip("\\/") + "/" + nome_fonte
    registrar((destino[0] + "/" + nome_fonte, junto), "grava", so_r5=True)


def _cmdlet(tipo, resto, base, resolver):
    if tipo == "opaco" or any(re.match(r"@\w", a[0]) for a in resto):
        return True
    if any(not a[0].startswith(("'", '"')) and (a[0].startswith(",") or a[0].endswith(",")) for a in resto):
        return True  # lista com vírgula separada por espaço (a ,b): o guarda não monta a lista (E11)
    nomeados, posicionais, switches, desconhecido = _parametros_ps(resto)
    if desconhecido:
        return True
    recursivo = any("recurse".startswith(s) and len(s) >= 2 for s in switches) or "r" in switches

    def lista(chaves):
        saida = []
        for chave in chaves:
            for bruto, valor in nomeados.get(chave, []):
                saida.extend((bruto, v) for v in (valor.split(",") if valor is not None else [None]))
        return saida

    def registrar(par, t, so_r5=False):
        for v in (par[1].split(",") if par[1] is not None else [None]):  # lista com vírgula (D12)
            resolver(v if v is not None else par[0], v, base, t, so_r5)

    caminhos = lista(("path", "literalpath", "pspath", "lp", "filepath"))
    if tipo == "conteudo":
        for par in caminhos + posicionais[:1]:
            registrar(par, "grava")
        return not (caminhos or posicionais or "variable" in nomeados)
    if tipo in ("novo", "pasta"):
        tipo_item = ((nomeados.get("itemtype") or nomeados.get("type") or [("", "")])[-1][1] or "").lower()
        alvos = caminhos or posicionais[:1] or [(".", ".")]
        nomes = nomeados.get("name", [])
        t = "pasta" if tipo == "pasta" or tipo_item.startswith("dir") else "grava"
        for par in alvos:
            if nomes:
                for nb, nv in nomes:
                    junto = None if par[1] is None or nv is None else par[1].rstrip("\\/") + "/" + nv
                    registrar((par[0] + "/" + nb, junto), t)
            else:
                registrar(par, t)
        if re.match(r"(?:sym|junc|hard)", tipo_item):
            for par in lista(("target",)) + nomeados.get("value", []):
                registrar(par, "grava")
        return False
    if tipo in ("copia", "move"):
        fontes = caminhos or posicionais[:1]
        destinos = lista(("destination",)) or posicionais[1:2] or [(".", ".")]
        for d in destinos:
            registrar(d, "recursivo" if recursivo else "grava")
            if _e_pasta(d, base):
                for f in fontes:
                    _registrar_junto(d, f, registrar)
        if tipo == "move":
            for f in fontes:
                registrar(f, "recursivo")
        return not fontes
    if tipo == "remove":
        alvos = caminhos + posicionais
        for par in alvos:
            for v in (par[1].split(",") if par[1] is not None else [None]):
                registrar((par[0], v), "recursivo" if recursivo else "remove")
        return not alvos
    if tipo == "renomeia":
        alvo = (caminhos or posicionais[:1])
        novo = nomeados.get("newname") or posicionais[1:2]
        for par in alvo:
            registrar(par, "recursivo")
            for nb, nv in novo:
                pasta = None if par[1] is None else os.path.dirname(par[1].replace("\\", "/"))
                registrar((nb, None if pasta is None or nv is None else (pasta + "/" + nv if pasta else nv)), "grava")
        return not alvo
    if tipo == "expande":
        for par in lista(("destinationpath",)) or posicionais[1:2] or [(".", ".")]:
            registrar(par, "recursivo")
        return False
    if tipo == "comprime":
        for par in lista(("destinationpath",)) or posicionais[1:2]:
            registrar(par, "grava")
        return not (lista(("destinationpath",)) or posicionais[1:2])
    if tipo == "baixa":
        for par in lista(("outfile",)):
            registrar(par, "grava")
        return False
    return True


def _utilitario(nome, resto, base, resolver, ps=False):
    def registrar(par, t, so_r5=False):
        resolver(par[0], par[1], base, t, so_r5)

    if nome == "tee":
        _, _, _, operandos = _opcoes_bash(resto)
        for par in operandos:
            registrar(par, "grava")
        return False
    if nome in ("cp", "install", "mv", "ln"):
        curtas, longas, valores, operandos = _opcoes_bash(resto, com_valor="tSm" if nome != "ln" else "tS",
                                                          com_valor_longo=("target-directory", "suffix"))
        recursivo = bool(curtas & set("rRa")) or bool(longas & {"recursive", "archive"})
        alvo = valores.get("t") or valores.get("target-directory")
        if alvo is None and operandos:
            alvo, operandos = operandos[-1], operandos[:-1]
        if alvo is None:
            return False
        registrar(alvo, "recursivo" if recursivo else "grava")
        e_pasta = bool(valores.get("t") or valores.get("target-directory")) or _e_pasta(alvo, base)
        for f in operandos:
            if e_pasta:
                _registrar_junto(alvo, f, registrar)
            if nome == "mv":
                registrar(f, "recursivo")
            elif nome == "ln":
                registrar(f, "grava")  # o alvo do link também conta (hardlink na fiação)
        return False
    if nome in ("rm", "rmdir"):
        curtas, longas, _, operandos = _opcoes_bash(resto)
        recursivo = nome == "rmdir" or bool(curtas & set("rR")) or "recursive" in longas
        for par in operandos:
            registrar(par, "recursivo" if recursivo else "remove")
        return False
    if nome == "mkdir":
        _, _, _, operandos = _opcoes_bash(resto, com_valor="m", com_valor_longo=("mode",))
        for par in operandos:
            registrar(par, "pasta")
        return False
    if nome in ("touch", "truncate"):
        _, _, _, operandos = _opcoes_bash(resto, com_valor="dtrs", com_valor_longo=("date", "reference", "size"))
        for par in operandos:
            registrar(par, "grava")
        return False
    if nome == "dd":
        for bruto, valor in resto:
            if valor is None:
                return True
            if valor.startswith("of="):
                registrar((bruto[3:], valor[3:]), "grava")
        return False
    if nome in ("sed", "perl"):
        curtas, longas, valores, operandos = _opcoes_bash(resto, com_valor="ef" if nome == "sed" else "eE",
                                                          com_valor_longo=("expression", "file"))
        no_lugar = "i" in curtas or any(a.startswith("in-place") for a in longas)
        if not no_lugar:
            return False
        arquivos = operandos if (valores.get("e") or valores.get("f") or valores.get("E") or
                                 valores.get("expression") or valores.get("file")) else operandos[1:]
        for par in arquivos:
            registrar(par, "grava")
        return False
    if nome == "tar":
        texto = " ".join(v or "" for _, v in resto)
        primeiro = (resto[0][1] or "") if resto else ""
        extrai = bool(re.search(r"(?:^|\s)(?:-[A-Za-z]*x|--extract|--get)", texto)) or bool(
            re.fullmatch(r"[A-Za-z]*x[A-Za-z]*", primeiro))
        if not extrai:
            return bool(re.search(r"(?:^|\s)(?:-[A-Za-z]*[cru]|--create|--append|--update)", texto)) or bool(
                re.fullmatch(r"[A-Za-z]*[cru][A-Za-z]*", primeiro))
        alvo = None
        for k, (bruto, valor) in enumerate(resto):
            if valor in ("-C", "--directory") and k + 1 < len(resto):
                alvo = resto[k + 1]
            elif valor is not None and valor.startswith("--directory="):
                alvo = (bruto, valor.split("=", 1)[1])
        registrar(alvo or (".", "."), "recursivo")
        return False
    if nome == "unzip":
        alvo = next((resto[k + 1] for k, a in enumerate(resto[:-1]) if a[1] == "-d"), (".", "."))
        registrar(alvo, "recursivo")
        return False
    if nome == "rsync":
        _, _, _, operandos = _opcoes_bash(resto)
        if operandos:
            registrar(operandos[-1], "recursivo")
        return False
    if nome == "curl":
        for k, (bruto, valor) in enumerate(resto):
            if valor in ("-O", "--remote-name", "--remote-name-all", "--output-dir") or valor is None:
                return True
            if valor in ("-o", "--output") and k + 1 < len(resto):
                registrar(resto[k + 1], "grava")
        return False
    if nome == "wget":
        alvo = next((resto[k + 1] for k, a in enumerate(resto[:-1]) if a[1] in ("-O", "--output-document")), None)
        if alvo is None:
            return True
        registrar(alvo, "grava")
        return False
    if nome in ("robocopy", "xcopy"):
        # R1 (responsável, 2026-11-23): 2º posicional é o destino, recursivo. Opção é /X ou /X:valor; sem destino
        # reconhecível no robocopy, não analisável. xcopy com um só posicional copia para o cwd.
        opcao = r"/{1,2}[A-Za-z0-9?+-]+(?::\S*)?"
        if not ps and any(a[1] and re.fullmatch(r"/[A-Za-z0-9?+-]+(?::\S*)?", a[1]) for a in resto):
            return True  # N29f: no Git Bash, /E vira E:/ e desloca os posicionais (medido); use //E
        for a in resto:
            m = re.fullmatch(r"(?i)/{1,2}(?:uni)?log\+?:(.+)", a[1] or "")
            if m:
                registrar((m.group(1), m.group(1)), "grava")  # /LOG:arq grava o arquivo (E13)
        posicionais = [a for a in resto if a[1] is None or not re.fullmatch(opcao, a[1])]
        if nome == "robocopy" and posicionais and any(re.fullmatch(r"(?i)/{1,2}mov(?:e)?", a[1] or "") for a in resto):
            registrar(posicionais[0], "recursivo")  # /MOV e /MOVE removem a origem (E13)
        if len(posicionais) >= 2:
            registrar(posicionais[1], "recursivo")
            return False
        if nome == "xcopy" and len(posicionais) == 1:
            registrar((".", "."), "recursivo")
            return False
        return True
    return False


def _fiacao_raizes(raiz):
    return [_componentes(os.path.abspath(p)) for p in
            (raiz / ".claude", raiz / "tools" / "guarda_agentes.py", Path.home() / ".claude")]


def r5_no_shell(comando, destinos, falha, cwd, raiz):
    """Motivo do R5 no shell, ou None."""
    raizes = _fiacao_raizes(raiz)
    pendente = falha
    for d in destinos:
        sem_aspas = re.sub("[\"'`" + ASPAS_SIMPLES_PS + ASPAS_DUPLAS_PS + "]", "", d["bruto"])
        if e_fiacao(sem_aspas, cwd, raiz) or (d["valor"] not in (None, NULO) and e_fiacao(d["valor"], cwd, raiz)):
            return f"gravação em {d['bruto'][:80]}"
        if d["valores"] is None:
            pendente = pendente or not d["fora"]
            continue
        for v in d["valores"]:
            if e_fiacao(v, cwd, raiz):
                return f"gravação em {d['bruto'][:80]}"
            if d["tipo"] == "recursivo":
                formas = [_componentes(v)] + ([_componentes(r)] if (r := _resolvido(v)) else [])
                if any(_sob(f_raiz, forma) for f_raiz in raizes for forma in formas):
                    return f"operação recursiva sobre {d['bruto'][:80]}, que contém a fiação"
    if pendente and RE_FIACAO_TEXTO.search(comando):
        return "comando com destino não resolvido ou não analisável que cita a fiação"
    return None


def r4_no_shell(perfil, destinos, falha, cwd, raiz, temp):
    """Motivo do R4 no shell (seguranca e verificador), ou None."""
    if falha:
        return "comando que grava de forma não analisável (aninhado, eval, xargs, splat, .NET ou aspas abertas)"
    entregas = raiz / "docs" / "entregas"
    temp_vale = temp is not None
    if temp_vale:
        t, r = _resolvido(os.path.abspath(temp)), _resolvido(os.path.abspath(raiz))
        if t is None or r is None or t == r or t.startswith(r + os.sep) or r.startswith(t.rstrip(os.sep) + os.sep):
            temp_vale = False
    for d in destinos:
        if d["so_r5"]:
            continue
        if d["fora"] or d["valores"] is None:
            return f"destino não resolvido ou fora do disco: {d['bruto'][:80]}"
        for v in d["valores"]:
            em_entregas = dentro_de(v, entregas, cwd)
            if not em_entregas and not (temp_vale and dentro_de(v, temp, cwd)):
                return f"gravação em {d['bruto'][:80]}"
            if perfil == "seguranca" and em_entregas and d["tipo"] != "pasta" and not NOME_DECISAO.match(_nome(v)):
                return f"gravação em {d['bruto'][:80]} (o seguranca só grava decisao*.md e conferencia*.md)"
    return None


def _textos(obj, prof=0):
    """Todas as strings de um JSON (dict, lista), para achar destino em chave que o guarda não conhece."""
    if prof > 5:
        return []
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [t for v in obj.values() for t in _textos(v, prof + 1)]
    if isinstance(obj, (list, tuple)):
        return [t for v in obj for t in _textos(v, prof + 1)]
    return []


def decidir(perfil, ferramenta, entrada, cwd, raiz=None, temp=None, ambiente=None):
    """(bloqueia, motivo). Ferramenta de leitura fora da lista é liberada (o tools: do agente já limita)."""
    raiz = Path(raiz or RAIZ)

    def bloqueio(regra, detalhe, explicacao):
        return True, (f"BLOQUEADO pelo guarda dos subagentes ({regra}, perfil {perfil}): {detalhe}. {explicacao} "
                      "Não contorne: devolva PARE com este motivo.")

    if ferramenta in ("Bash", "PowerShell"):
        limpo = sem_comentarios(str(entrada.get("command", "")), "powershell" if ferramenta == "PowerShell" else "bash")
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
        comando = str(entrada.get("command", ""))
        destinos, falha = analisar_gravacao(comando, "powershell" if ferramenta == "PowerShell" else "bash", cwd,
                                            ambiente)
        achado = r5_no_shell(comando, destinos, falha, cwd, raiz)
        if achado:
            return bloqueio("R5", achado, MSG_R5)
        if perfil in ("verificador", "seguranca"):
            achado = r4_no_shell(perfil, destinos, falha, cwd, raiz, tempfile.gettempdir() if temp is None else temp)
            if achado:
                return bloqueio("R4", achado, f"O {perfil} só grava em docs/entregas/<tarefa>/ ou na pasta temporária "
                                "(scratchpad), com destino que o guarda resolva.")
        return False, ""

    if ferramenta not in FERRAMENTAS:
        if re.search(r"(?i)edit|write|create|move|delete|rename|copy|append|put|save|upload", ferramenta):  # D16, E14
            caminhos = [str(entrada[k]) for k in ("file_path", "notebook_path", "path") if entrada.get(k)]
            if not caminhos:
                return bloqueio("R5", f"ferramenta de escrita {ferramenta} sem caminho conhecido", MSG_R5)
            for caminho in caminhos + _textos(entrada):  # destino em qualquer chave (destination, target...)
                if e_fiacao(caminho, cwd, raiz):
                    return bloqueio("R5", f"{ferramenta} em {caminho[:80]}", MSG_R5)
            if perfil in ("verificador", "seguranca"):
                return bloqueio("R4", f"ferramenta de escrita {ferramenta}", f"O {perfil} só grava com Write.")
        return False, ""

    if ferramenta in ("Read", "Write", "Edit") and e_env(entrada.get("file_path", "")):
        return bloqueio("R2", f"{ferramenta} em {entrada.get('file_path')}", "Nunca ler, editar ou imprimir o .env.")
    if ferramenta == "Grep" and (e_env(entrada.get("path", "")) or glob_cobre_env(entrada.get("glob", ""))):
        return bloqueio("R2", "Grep sobre o .env", "Nunca ler, editar ou imprimir o .env.")

    if ferramenta in ("Write", "Edit"):
        caminho = str(entrada.get("file_path", ""))
        texto = str(entrada.get("content", "")) if ferramenta == "Write" else texto_depois_do_edit(caminho, entrada, cwd)
        if not e_documentacao(caminho) and liga_sandbox_teste(texto):
            return bloqueio("R3", f"{ferramenta} com ORACLE_SANDBOX=1 (forma do grep 3.5) em {caminho}",
                            "Código nunca define ORACLE_SANDBOX=1 no processo (só \"0\" ou ausente); só a "
                            "documentação (.md, .txt) pode citar.")
        if e_fiacao(caminho, cwd, raiz):
            return bloqueio("R5", f"{ferramenta} em {caminho}", MSG_R5)
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
