"""Testes de tools/guarda_agentes.py (hook PreToolUse dos subagentes): só a decisão, sem rodar comando."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("guarda_agentes", _RAIZ / "tools" / "guarda_agentes.py")
gs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gs)

CWD = str(gs.RAIZ)
# Partidos em dois literais para o grep 3.5 do PROCESSO §5 não casar com este arquivo.
SET1 = "monkeypatch.set" + "env('ORACLE_SANDBOX', '1')"
ENV1 = "os.environ" + "['ORACLE_SANDBOX'] = '1'"
SET0 = "monkeypatch.set" + "env('ORACLE_SANDBOX', '0')"
# A raiz no estilo do Git Bash (/c/Users/...), quando a raiz tem unidade.
_UNIDADE = re.match(r"^([A-Za-z]):[\\/](.*)$", CWD)
RAIZ_GIT_BASH = f"/{_UNIDADE.group(1).lower()}/{_UNIDADE.group(2).replace(chr(92), '/')}" if _UNIDADE else CWD


def _decide(perfil, ferramenta, **entrada):
    return gs.decidir(perfil, ferramenta, entrada, CWD)


# ---------- comandos ----------

COMANDOS_LIBERADOS = [
    "git status --short -- .",
    "git -C \"$R\" archive --format=tar -o \"$T/copia.tar\" HEAD IA/PERSONAL_AGENT",
    "git --no-pager diff --cached --stat",
    "git -c core.quotepath=off log -1 --format=%h",
    "git branch --show-current",
    "git branch --list 'feat*'",
    "git remote -v",
    "git --version",
    "git config --get user.name",
    "git cat-file -t HEAD",
    "git ls-tree HEAD",
    "git describe --tags",
    "git merge-base main HEAD",
    "git check-ignore -v docs/x.md",
    "git check-attr -a docs/x.md",
    "git remote show origin",
    "git reflog -5",
    "git symbolic-ref HEAD",
    "git hash-object a.py",
    "git rev-list --count HEAD",
    "git symbolic-ref -q HEAD",
    "git symbolic-ref --short HEAD",
    "git remote -v show origin",
    "git reflog show HEAD",
    "git grep --untracked ORACLE",
    "git hash-object --stdin",
    "which git",
    "command -v git",
    "git -c core.quotepath=off status",
    "git diff --no-color",
    "git log --no-merges --oneline -5",
    "git grep -n -E 'load_dotenv\\(' -- 'src/*.py' app.py",
    "git ls-files | grep -E '(^|/)\\.env$'                                             # .env versionado",
    "git grep -n 'override=True' -- 'src/*.py' app.py 'tools/*.py'                    # recarga do .env",
    "git status  # depois: git commit",
    "R=\"$(git rev-parse --show-toplevel)\"",
    "env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider",
    "python -I tools/verificacao_padrao.py --tarefa t --base 0e3fd62 --esperado 1/0 --previsto 'docs/entregas/x/*'",
    "python -I tools/controle_mutacao.py --tarefa t --rotulo r --alvo tools/x.py --teste tests/test_x.py",
    "grep -rn ORACLE src/",
    f"grep -rn ORACLE \"{CWD}/src\"",
    "grep -rn X \"C:/Users/FREDER~1/AppData/Local/Temp/sonda\"",
    "grep -n ORACLE app.py",
    "rg ORACLE src",
    "ls .gitignore .env.example",
    "Remove-Item Env:ORACLE_SANDBOX -ErrorAction SilentlyContinue; $env:PYTHONDONTWRITEBYTECODE = '1'",
    "cat docs/legit.md",
]


@pytest.mark.parametrize("comando", COMANDOS_LIBERADOS)
def test_comandos_liberados(comando):
    assert _decide("verificador", "Bash", command=comando) == (False, "")


@pytest.mark.parametrize("comando, regra", [
    ("git commit -m x", "R1"),
    ("git add -- a.py", "R1"),
    ("git stage a.py", "R1"),
    ("cd x && git stash list", "R1"),
    ("git -C \"/c/x y\" reset --hard", "R1"),
    ("git -c core.x=y push", "R1"),
    ("git -c \"user.name=a b\" commit -m x", "R1"),
    ("git --git-dir .git commit -m x", "R1"),
    ("git --work-tree /x commit -m x", "R1"),
    ("Git commit -m x", "R1"),
    ("git branch -D velho", "R1"),
    ("git branch novo", "R1"),
    ("git config user.name x", "R1"),
    ("git checkout -- a.py", "R1"),
    ("git bisect start", "R1"),
    ("git update-index --assume-unchanged a.py", "R1"),
    ("git remote add origem url", "R1"),
    ("git hash-object -w a.py", "R1"),
    ("git symbolic-ref HEAD refs/heads/x", "R1"),
    ("git $SUB", "R1"),
    ("git ci -m x", "R1"),
    ("git worktree list", "R1"),
    ("git notes list", "R1"),
    ("git grep --no-index ORACLE .", "R1"),
    ("git diff --no-index a.txt b.txt", "R1"),
    ("git reflog expire --all", "R1"),
    ("git lfs ls-files", "R1"),
    ("git grep --untracked --no-exclude PADRAO", "R1"),
    ("git grep --no-ind PADRAO", "R1"),
    ("git grep --no-exclude-standard PADRAO", "R1"),
    ("git --git-dir=/x -c grep.fallbackToNoIndex=true grep -n PADRAO", "R1"),
    ("git symbolic-ref -qd HEAD", "R1"),
    ("git symbolic-ref --del HEAD", "R1"),
    ("git remote -v add x URL", "R1"),
    ("git remote --verbose set-url origin URL", "R1"),
    ("git reflog drop --all", "R1"),
    ("git reflog write HEAD a b msg", "R1"),
    ("git hash-object -wt blob a.py", "R1"),
    ("git --attr-source status commit -m x", "R1"),
    ("echo commit -m x | xargs git", "R1"),
    ("git -c core.pager=less log", "R1"),
    ("git --config-env=core.pager=VAR log", "R1"),
    ("git -cfoo=bar status", "R1"),
    ("git --exec-path=/x status", "R1"),
    ("git grep -Ocat ORACLE", "R1"),
    ("git grep -iO ORACLE", "R1"),
    ("git diff --output=x.txt", "R1"),
    ("git log --outp=x.txt", "R1"),
    ("GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=grep.fallbackToNoIndex GIT_CONFIG_VALUE_0=true git --git-dir=/nao/existe "
     "grep -n X", "R1"),
    ("GIT_CONFIG_PARAMETERS=\"'grep.fallbacktonoindex'='true'\" git grep X", "R1"),
    ("$env:GIT_CONFIG_COUNT = 1; git status", "R1"),
    ("git config --get user.name --add a.b c", "R1"),
    ("git config set a.b c --get", "R1"),
    ("git config --get user.name --un", "R1"),
    ("R=\"$(git commit -m x)\"", "R1"),
    ("\"C:/Program Files/Git/cmd/git.exe\" commit -m x", "R1"),
    ("cat .env", "R2"),
    ("cat .env.local", "R2"),
    ("cat .env.", "R2"),
    ("type .\\.env", "R2"),
    ("Get-Content C:\\proj\\.env", "R2"),
    ("python -c \"open('.env').read()\"", "R2"),
    ("python -m dotenv list", "R2"),
    ("dotenv get CHAVE", "R2"),
    ("python -c \"from dotenv import dotenv_values; dotenv_values()\"", "R2"),
    ("python -c \"from dotenv import load_dotenv; load_dotenv(override=True)\"", "R2"),
    ("python -mdotenv list", "R2"),
    ("echo \"x\n# \" ; git commit -m y", "R1"),
    ("echo a\\\n#x; git commit -m y", "R1"),
    ("echo a`\n#x; cat .env", "R2"),
    ("echo \"a \\\" # \" ; cat .env", "R2"),
    ("grep -rn X `pwd`", "R2"),
    ("grep -rn X \"$(pwd)\"", "R2"),
    ("grep -rn X /c", "R2"),
    ("grep -rn ORACLE .", "R2"),
    ("grep -r ORACLE", "R2"),
    (f"grep -rn ORACLE \"{CWD}\"", "R2"),
    (f"grep -rn ORACLE \"{RAIZ_GIT_BASH}\"", "R2"),
    ("grep -rn ORACLE ../PERSONAL_AGENT", "R2"),
    ("grep -rn ORACLE \"$P\"", "R2"),
    ("findstr /s /i chave *.*", "R2"),
    ("Get-ChildItem -Recurse | Select-String ORACLE", "R2"),
    ("rg --hidden ORACLE", "R2"),
    ("ORACLE_SANDBOX=1 python -m pytest -q", "R3"),
    ("oracle_sandbox=1 python -m pytest -q", "R3"),
    ("export ORACLE_SANDBOX=1", "R3"),
    ("$env:ORACLE_SANDBOX = '1'", "R3"),
    ("$env:oracle_sandbox = '1'", "R3"),
    ("Set-Item Env:ORACLE_SANDBOX 1", "R3"),
    ("setx ORACLE_SANDBOX 1", "R3"),
    ("python -c \"import os; " + ENV1 + "\"", "R3"),
])
def test_comandos_bloqueados(comando, regra):
    bloqueia, motivo = _decide("mecanico", "Bash", command=comando)
    assert bloqueia
    assert f"({regra}," in motivo and "PARE" in motivo


@pytest.mark.parametrize("perfil", gs.PERFIS)
def test_r1_r2_e_r3_valem_para_todos_os_perfis(perfil):
    assert _decide(perfil, "Bash", command="git commit -m x")[0]
    assert _decide(perfil, "PowerShell", command="git push")[0]
    assert _decide(perfil, "Read", file_path=".env")[0]
    assert _decide(perfil, "Bash", command="ORACLE_SANDBOX=1 pytest")[0]


def test_sem_comentarios_respeita_aspas():
    assert gs.sem_comentarios("git status  # comentário") == "git status  "
    assert gs.sem_comentarios("echo '# não é comentário' # é") == "echo '# não é comentário' "
    assert gs.sem_comentarios("curl http://x/#frag") == "curl http://x/#frag"


@pytest.mark.parametrize("comando", [
    "echo \"x\n# \" ; git commit -m y",
    "echo \"a \\\" # \" ; cat .env",
    "git status # \"comentário com aspas\"",
])
def test_sem_comentarios_nao_corta_o_que_pode_ser_codigo(comando):
    assert gs.sem_comentarios(comando) == comando


def test_sem_comentarios_trata_o_escape_fora_de_aspas():
    assert gs.sem_comentarios("echo \\\" # x") == "echo \\\" "


# A1 (guarda-r4-r5, S1): a continuação de linha é \ só no Bash e crase só no PowerShell. Juntar a do outro
# dialeto colava a palavra anterior ao git ou ao grep da linha seguinte (agit), que escapavam do R1 e do R2.
@pytest.mark.parametrize("ferramenta, comando, regra", [
    ("PowerShell", "Write-Output a\\\ngit com" + "mit -m x", "R1"),
    ("PowerShell", "Write-Output a\\\ngrep -rn X .", "R2"),
    ("Bash", "echo a`\ngit com" + "mit -m x`", "R1"),
    ("PowerShell", "git `\ncom" + "mit -m x", "R1"),
    ("Bash", "git \\\ncom" + "mit -m x", "R1"),
    ("PowerShell", "echo a\\\n#x; cat .env", "R2"),
])
def test_continuacao_de_linha_por_dialeto(ferramenta, comando, regra):
    bloqueia, motivo = _decide("mecanico", ferramenta, command=comando)
    assert bloqueia
    assert f"({regra}," in motivo


@pytest.mark.parametrize("ferramenta, comando", [
    ("PowerShell", "git status `\n--short"),
    ("Bash", "git status \\\n--short"),
])
def test_continuacao_de_linha_do_proprio_dialeto_continua_liberada(ferramenta, comando):
    assert _decide("verificador", ferramenta, command=comando) == (False, "")


# ---------- ferramentas ----------

@pytest.mark.parametrize("ferramenta, entrada", [
    ("Read", {"file_path": ".env"}),
    ("Read", {"file_path": "C:\\proj\\.env"}),
    ("Read", {"file_path": "docs/.ENV"}),
    ("Read", {"file_path": ".env.local"}),
    ("Read", {"file_path": CWD + "\\.env."}),
    ("Read", {"file_path": CWD + "\\.env::$DATA"}),
    ("Grep", {"pattern": "ORACLE", "path": ".env"}),
    ("Grep", {"pattern": "ORACLE", "glob": "*.env"}),
    ("Grep", {"pattern": "ORACLE", "glob": ".env*"}),
    ("Write", {"file_path": ".env", "content": "X=1"}),
    ("Edit", {"file_path": ".env", "old_string": "a", "new_string": "b"}),
])
def test_ferramentas_no_env_bloqueadas(ferramenta, entrada):
    bloqueia, motivo = gs.decidir("mecanico", ferramenta, entrada, CWD)
    assert bloqueia and "(R2," in motivo


@pytest.mark.parametrize("ferramenta, entrada", [
    ("Read", {"file_path": ".env.example"}),
    ("Read", {"file_path": "docs/PROCESSO.md"}),
    ("Grep", {"pattern": "ORACLE"}),
    ("Grep", {"pattern": "ORACLE", "glob": "*.py", "path": "src"}),
    ("Glob", {"pattern": "**/.env*"}),
    ("SubagentHandback", {"message": "x"}),
])
def test_ferramentas_liberadas(ferramenta, entrada):
    assert gs.decidir("verificador", ferramenta, entrada, CWD) == (False, "")


def test_ferramenta_de_escrita_desconhecida_bloqueada_no_verificador_e_no_seguranca():
    for perfil in ("verificador", "seguranca"):
        bloqueia, motivo = gs.decidir(perfil, "NotebookEdit", {"notebook_path": "src/x.ipynb"}, CWD)
        assert bloqueia and "(R4," in motivo
    assert gs.decidir("mecanico", "NotebookEdit", {"notebook_path": "src/x.ipynb"}, CWD) == (False, "")


def test_teste_que_liga_o_sandbox_e_bloqueado():
    assert gs.decidir("mecanico", "Write", {"file_path": "tests/test_x.py", "content": SET1}, CWD)[0]
    assert gs.decidir("mecanico", "Edit", {"file_path": "tests/test_x.py", "old_string": "a", "new_string": ENV1},
                      CWD)[0]


def test_edit_que_troca_0_por_1_com_contexto_e_bloqueado(tmp_path):
    (tmp_path / "tests").mkdir()
    alvo = tmp_path / "tests" / "test_y.py"
    alvo.write_text(SET0 + "\n", encoding="utf-8")
    entrada = {"file_path": str(alvo), "old_string": "'0'", "new_string": "'1'"}
    bloqueia, motivo = gs.decidir("mecanico", "Edit", entrada, str(tmp_path), raiz=tmp_path)
    assert bloqueia and "(R3," in motivo


@pytest.mark.parametrize("caminho, conteudo, bloqueia", [
    ("src/conftest.py", ENV1, True),
    ("tools/x.py", SET1, True),
    ("C:/Users/x/scratch/sonda.py", SET1, True),
    ("docs/x.md", SET1, False),
    ("docs/notas.txt", ENV1, False),
    ("tests/test_x.py", '_rodar(e, t, "ORACLE_SANDBOX=1\\n")\n', False),
])
def test_r3_vale_em_todo_codigo_salvo_documentacao(caminho, conteudo, bloqueia):
    resultado = gs.decidir("mecanico", "Write", {"file_path": caminho, "content": conteudo}, CWD)
    assert resultado[0] is bloqueia
    if bloqueia:
        assert "(R3," in resultado[1]


def test_env_ficticio_com_sandbox_1_em_teste_e_permitido():
    conteudo = '_rodar(entrada, tmp, "ORACLE_SANDBOX=1\\n")\n'
    assert gs.decidir("mecanico", "Write", {"file_path": "tests/test_x.py", "content": conteudo}, CWD) == (False, "")


def test_sandbox_0_em_teste_e_texto_fora_de_tests_passam():
    assert gs.decidir("mecanico", "Write", {"file_path": "tests/test_x.py", "content": SET0}, CWD) == (False, "")
    assert gs.decidir("mecanico", "Write", {"file_path": "docs/nota.md", "content": SET1}, CWD) == (False, "")


@pytest.mark.parametrize("perfil, caminho, bloqueia", [
    ("verificador", "docs/entregas/t/verificacao.md", False),
    ("verificador", str(_RAIZ / "docs" / "entregas" / "t" / "x.txt"), False),
    ("verificador", "docs/_sonda.md", True),
    ("verificador", "tools/x.py", True),
    ("verificador", "docs/entregas/../PROCESSO.md", True),
    ("seguranca", "docs/entregas/t/decisao_x.md", False),
    ("seguranca", "docs/entregas/t/conferencia_script.md", False),
    ("seguranca", "docs/entregas/t/notas.md", True),
    ("seguranca", "src/x.py", True),
    ("mecanico", "tools/x.py", False),
    ("mecanico", "tests/test_x.py", False),
])
def test_onde_cada_perfil_grava(perfil, caminho, bloqueia):
    resultado = gs.decidir(perfil, "Write", {"file_path": caminho, "content": "x"}, CWD)
    assert resultado[0] is bloqueia
    if bloqueia:
        assert "(R4," in resultado[1]


# ---------- R5: fiação do guarda (guarda-r4-r5, decisao.md §3) ----------

_PREFIXO_PY = Path(gs.sys.prefix)
_WORKSPACE = str(_RAIZ.parent.parent)
CAMINHOS_FIACAO = [
    ".claude/agents/x.md",                                        # F1
    ".claude/settings.json",                                      # F2
    str(_RAIZ / ".claude" / "settings.local.json"),               # F5
    RAIZ_GIT_BASH + "/.claude/x",                                 # F6
    ".CLAUDE/Settings.json",                                      # F8
    ".claude./x.md",
    "tools/guarda_agentes.py",                                    # F4
    "tools/guarda_agentes.py.",                                   # F9
    "tools/guarda_agentes.py::$DATA",                             # F9
    "\\\\?\\" + str(_RAIZ / "tools" / "guarda_agentes.py"),       # F12
    str(Path.home() / ".claude" / "settings.json"),               # F10
    str(_PREFIXO_PY / "Lib" / "site-packages" / "x.pth"),         # N8
    str(_PREFIXO_PY / "Lib" / "site-packages" / "sitecustomize.py"),
    "docs/entregas/t/usercustomize.py",
    "docs/entregas/t/python.bat",
    str(_PREFIXO_PY / "python.exe"),
    str(_PREFIXO_PY / "Lib" / "os.py"),
    "$X/tools/guarda_agentes.py",                                 # caminho não resolvido: vale o nome
    "C:/outro/venv/Lib/site-packages/x.pth",                      # .pth fora do prefixo do hook
]


@pytest.mark.parametrize("perfil", gs.PERFIS)
@pytest.mark.parametrize("caminho", CAMINHOS_FIACAO)
def test_r5_write_na_fiacao_bloqueado_em_todo_perfil(perfil, caminho):
    bloqueia, motivo = gs.decidir(perfil, "Write", {"file_path": caminho, "content": "x"}, CWD)
    assert bloqueia and "(R5," in motivo and "PARE" in motivo


@pytest.mark.parametrize("perfil", gs.PERFIS)
def test_r5_edit_do_settings_local_tem_rotulo_r5(perfil):  # F3 e F38
    entrada = {"file_path": ".claude/settings.local.json", "old_string": "a", "new_string": "b"}
    bloqueia, motivo = gs.decidir(perfil, "Edit", entrada, CWD)
    assert bloqueia and "(R5," in motivo


def test_r5_com_cwd_no_workspace():  # F7
    entrada = {"file_path": "IA/PERSONAL_AGENT/.claude/x", "content": "x"}
    assert "(R5," in gs.decidir("mecanico", "Write", entrada, _WORKSPACE)[1]


@pytest.mark.parametrize("perfil", gs.PERFIS)
@pytest.mark.parametrize("ferramenta, entrada", [
    ("MultiEdit", {"file_path": ".claude/agents/x.md", "edits": []}),   # F11
    ("NotebookEdit", {"notebook_path": ".claude/x.ipynb"}),
    ("NotebookEdit", {"notebook_path": "tools/guarda_agentes.py"}),
    ("MultiEdit", {"edits": []}),                                       # sem caminho conhecido
])
def test_r5_ferramenta_de_escrita_desconhecida(perfil, ferramenta, entrada):
    bloqueia, motivo = gs.decidir(perfil, ferramenta, entrada, CWD)
    assert bloqueia and "(R5," in motivo


def test_r5_resolve_nome_curto_pelo_resolver():  # F13: o resolver vê o 8.3 que o texto não mostra
    alvo = str(_RAIZ / "tools" / "guarda_agentes.py")

    def falso(caminho):
        return alvo if caminho.upper().endswith("ABCDEF~1.PY") else caminho

    assert gs.e_fiacao("tools/ABCDEF~1.PY", CWD, resolver=falso)
    assert not gs.e_fiacao("tools/ABCDEF~1.PY", CWD, resolver=lambda c: c)
    assert gs.e_fiacao("tools/GUARDA~1.PY", CWD, resolver=lambda c: c)   # nome curto da fiação, pelo texto
    assert gs.e_fiacao(".cl*/agents/x.md", CWD, resolver=lambda c: c)    # glob que casa com .claude
    # Fluxo alternativo sem realpath que o normalize: só o corte do :fluxo revela o nome.
    assert gs.e_fiacao("docs/entregas/t/guarda_agentes.py::$DATA", CWD, resolver=lambda c: c)
    assert gs.e_fiacao("docs/entregas/t/sitecustomize.py:x", CWD, resolver=lambda c: c)


@pytest.mark.parametrize("perfil", gs.PERFIS)
@pytest.mark.parametrize("ferramenta, entrada", [
    ("Read", {"file_path": ".claude/settings.local.json"}),
    ("Read", {"file_path": "tools/guarda_agentes.py"}),
    ("Grep", {"pattern": "R5", "path": ".claude"}),
    ("Glob", {"pattern": ".claude/**"}),
])
def test_r5_leitura_da_fiacao_liberada(perfil, ferramenta, entrada):  # L32
    assert gs.decidir(perfil, ferramenta, entrada, CWD) == (False, "")


def test_componentes_normaliza_como_o_windows_abre():
    # O abspath do Windows já tira ponto e espaço finais (F5); aqui a forma crua, sem ele.
    assert gs._componentes("\\\\?\\C:\\a\\.Claude. \\x.py::$DATA") == ["c:", "a", ".claude", "x.py"]


def test_r4_dentro_de_confere_tambem_o_realpath():  # junção em docs/entregas apontando para fora
    pasta = _RAIZ / "docs" / "entregas"

    def falso(caminho):
        return str(_RAIZ / "src" / "x.py") if "juncao" in caminho else caminho

    assert gs.dentro_de("docs/entregas/t/x.md", pasta, CWD, resolver=lambda c: c)
    assert not gs.dentro_de("docs/entregas/juncao/x.py", pasta, CWD, resolver=falso)


@pytest.mark.parametrize("caminho", [
    "tests/test_guarda_agentes.py", "docs/claude_notas.md", "src/tools/x.py", "docs/entregas/t/python_notas.md",
])
def test_r5_nao_pega_o_que_nao_e_fiacao(caminho):
    assert gs.decidir("mecanico", "Write", {"file_path": caminho, "content": "x"}, CWD) == (False, "")


# ---------- main ----------

def _main(perfil, dados):
    return gs.main(["--perfil", perfil], entrada=json.dumps(dados))


def test_main_libera_com_0(capsys):
    assert _main("verificador", {"tool_name": "Bash", "tool_input": {"command": "git status"}, "cwd": CWD}) == 0
    assert capsys.readouterr().err == ""


def test_main_bloqueia_com_2_e_motivo_no_stderr(capsys):
    assert _main("verificador", {"tool_name": "Bash", "tool_input": {"command": "git stash list"}}) == 2
    assert "R1" in capsys.readouterr().err


@pytest.mark.parametrize("bruto", ["", "nao e json", "[]", json.dumps({"tool_input": {}}),
                                   json.dumps({"tool_name": "Bash", "tool_input": "x"})])
def test_main_entrada_invalida_bloqueia(bruto):
    assert gs.main(["--perfil", "mecanico"], entrada=bruto) == 2


def test_main_perfil_invalido_bloqueia():
    assert gs.main(["--perfil", "outro"], entrada="{}") == 2


# ---------- R4 e R5 no shell (guarda-r4-r5, decisao.md §5, escopo reduzido) ----------

T = gs.tempfile.gettempdir()
# Na cópia do controle de mutação a raiz fica dentro da pasta temporária, que então não vale (B58): os testes
# usam uma pasta fora da raiz.
if gs.os.path.realpath(str(_RAIZ)).lower().startswith(gs.os.path.realpath(T).lower().rstrip("\\/") + gs.os.sep):
    T = str(Path(_RAIZ.anchor) / "guarda_temp_teste")
TL = gs.os.path.realpath(T)
E = "docs/entregas/t"
AMB = {"TEMP": T, "TMP": T}


def _sh(perfil, comando, ferramenta="Bash", **kw):
    return gs.decidir(perfil, ferramenta, {"command": comando}, CWD, temp=kw.get("temp", T), ambiente=AMB)


SHELL_LIBERADOS = [
    ("verificador", "Bash", f"echo x > {E}/a.txt"),                                         # L1
    ("verificador", "Bash", f"cmd >> {E}/a.txt 2>&1"),                                      # L2
    ("verificador", "Bash", "python -m pytest -q > /dev/null 2>&1"),                        # L3
    ("verificador", "Bash", "ls >&2"),                                                      # L4
    ("verificador", "Bash", f"mkdir -p {E}"),                                               # L5
    ("verificador", "Bash", f"S=\"{T}/sonda\"; mkdir -p \"$S\" && cat > \"$S/x.py\" <<'EOF'\n"
                            "if a > 0:\n    print(\"it's\")\nEOF"),                         # L6
    ("verificador", "Bash", f"O={E}/out.txt; git status > $O"),                             # L7
    ("verificador", "Bash", f"cd \"{CWD}\" && env -u ORACLE_SANDBOX python -m pytest -q > {E}/p.txt 2>&1"),  # L8
    ("verificador", "Bash", f"cd \"{CWD}\"; python -m pytest -q > {E}/p.txt 2>&1"),         # L8b
    ("verificador", "Bash", f"rm -rf \"{T}/iso\""),                                         # L9
    ("verificador", "Bash", f"git diff | tee {E}/d.diff"),                                  # L10
    ("verificador", "Bash", f"sed -i 's/a/b/' {E}/v.md"),                                   # L11
    ("verificador", "Bash", f"cd \"{T}\" && echo x > rel.txt"),                             # L12
    ("verificador", "Bash", "echo \"a > src/x.py\""),                                       # L13
    ("verificador", "Bash", f"cp src/x.py {E}/"),                                           # L15
    ("verificador", "Bash", f"echo x > \"{RAIZ_GIT_BASH}/{E}/a.txt\""),                     # L16
    ("verificador", "Bash", f"echo x > \"{TL}/a.txt\""),                                    # L17
    ("verificador", "Bash", f"grep -n R5 .claude/agents/x.md > {E}/g.txt"),                 # L31
    ("verificador", "Bash", f"python -I tools/guarda_agentes.py --perfil mecanico < {E}/e.json"),  # L33
    ("verificador", "Bash", f"R=\"$(git rev-parse --show-toplevel 2>/dev/null)\"; echo $R > {E}/r.txt"),
    ("verificador", "Bash", f"{{ echo a; echo b; }} > {E}/a.txt"),
    ("verificador", "PowerShell", f"Set-Content -Path {E}/a.txt -Value x"),                 # L18
    ("verificador", "PowerShell", "'x' | Out-File docs\\entregas\\t\\a.txt"),               # L19
    ("verificador", "PowerShell", "$out = Join-Path $env:TEMP 'sentinela'; "
                                  "New-Item -ItemType Directory -Force -Path $out"),        # L20
    ("verificador", "PowerShell", "Remove-Item -LiteralPath \"$env:TEMP\\iso\" -Recurse -Force"),  # L21
    ("verificador", "PowerShell", "git status *> $null"),                                   # L22
    ("verificador", "PowerShell", "python x 2>&1 | Out-Null"),                              # L22
    ("verificador", "PowerShell", "Remove-Item Env:ORACLE_SANDBOX -ErrorAction SilentlyContinue; "
                                  "$env:PYTHONDONTWRITEBYTECODE = '1'"),                    # L23
    ("verificador", "PowerShell", f"$s = @'\nit's\n'@\n$s | Set-Content {E}/a.txt"),        # L24
    ("verificador", "PowerShell", "Get-Date | Tee-Object -Variable v"),                     # L25
    ("verificador", "PowerShell", f"<# comentario #> Set-Content {E}/a.txt x"),
    ("seguranca", "Bash", f"git diff > \"{T}/x.diff\""),                                    # L26
    ("seguranca", "Bash", f"echo x > {E}/decisao_y.md"),                                    # L27
    ("seguranca", "Bash", f"mkdir -p {E}"),                                                 # L28
    ("seguranca", "Bash", f"cp tools/guarda_agentes.py \"{T}/g.py\""),                      # L34
    ("mecanico", "Bash", "echo x > src/x.py"),                                              # L29
    ("mecanico", "Bash", "cp a.py tools/b.py"),                                             # L30
    ("mecanico", "Bash", f"cp .claude/agents/x.md {E}/"),                                   # L35
    ("mecanico", "Bash", "X=$(printf a); echo x > \"$X/y.txt\""),                           # N6, residual aceito
    # Regras de segmento e de cd (não regressão: formas reais do verificador, levantamento.md e nao_regressao.md).
    ("verificador", "Bash", f"cd \"{CWD}\" && mkdir -p {E} && O={E} && {{ echo a; git status; }} > $O/01.txt 2>&1"),
    ("verificador", "Bash", f"P=\"{CWD}\"; cd \"$P\" && OUT=\"$P/{E}/v.txt\" && {{\necho a\n}} > \"$OUT\""),
    ("verificador", "Bash", f"diff <(sed -n 1p a.txt) <(sed -n 1p b.txt) > {E}/d.txt"),
    ("verificador", "Bash", f"bash -c \"echo x > {E}/a.txt\""),
    ("verificador", "Bash", "powershell -NoProfile -Command \"Test-Path 'C:\\AgentDBA'\""),
    ("verificador", "PowerShell", f"Set-Location -LiteralPath '{CWD}'\n$out = '{E}/p.txt'\n"
                                  f"python -m pytest 2>&1 | Out-File -FilePath $out -Encoding utf8"),
    ("verificador", "PowerShell", "\"n: $((@($(@((Get-Item 'HKCU:\\Environment').Property)))).Count)\""),
    # Não regressão das correções da conferência do passo 5.
    ("seguranca", "PowerShell", "Set-Location docs | Out-Null; Set-Content entregas/t/conferencia_x.md x"),
    ("verificador", "Bash", f"time python -m pytest -q > {E}/p.txt"),
    ("verificador", "PowerShell", f"$n = (Get-Content {E}/a.txt | Measure-Object).Count"),
    ("verificador", "PowerShell", f"Out-File -FilePath {E}/a.txt -InputObject x -Encoding utf8 -NoNewline"),
    # Não regressão do passo 5c.
    ("verificador", "Bash", f"timeout 600 python -m pytest -q > {E}/p.txt 2>&1"),
    ("verificador", "Bash", f"robocopy src {E} //E //NJH"),
    ("verificador", "PowerShell", f"robocopy src {E} /E /NJH /LOG:{E}/robo.txt"),
    ("verificador", "Bash", f"cd docs && echo x > entregas/t/a.txt"),
    ("verificador", "PowerShell", f"Export-Csv -Path {E}/a.csv -Include x -NoTypeInformation"),
    ("mecanico", "Bash", "bash tools/x.sh"),                             # interpretador: residual aceito
    # Não regressão da conferência do passo 5c (F2, F3) e falsos positivos O1 criados pelo 5c.
    ("verificador", "Bash", "cd docs &&\necho x > entregas/t/a.txt"),
    ("verificador", "PowerShell", f"robocopy src {E} /E /LOG:$env:TEMP\\robo.txt"),
    ("verificador", "Bash", f"timeout 600 python -m pytest -q -k guarda > {E}/p.txt 2>&1"),
    ("verificador", "Bash", f"timeout 60 grep -i foo src/x.py > {E}/g.txt"),
]


@pytest.mark.parametrize("perfil", gs.PERFIS)
@pytest.mark.parametrize("ferramenta", ["BashOutput", "TaskOutput", "mcp__x__get_output"])
def test_ferramenta_de_leitura_com_put_no_nome_e_liberada(perfil, ferramenta):  # O2 da conferência do 5c
    assert gs.decidir(perfil, ferramenta, {"bash_id": "1"}, CWD) == (False, "")


def test_conteudo_que_cita_a_fiacao_nao_e_destino():  # O3 da conferência do 5c
    entrada = {"path": "src/notas.md", "content": "editar .claude/agents/mecanico.md e tools/guarda_agentes.py"}
    assert gs.decidir("mecanico", "mcp__fs__write_file", entrada, CWD) == (False, "")


@pytest.mark.parametrize("perfil", gs.PERFIS)
@pytest.mark.parametrize("ferramenta", ["mcp__fs__update_file", "mcp__fs__replace_in_file", "mcp__fs__apply_patch"])
def test_ferramenta_update_replace_patch_tem_r5(perfil, ferramenta):  # E14, nomes (conferência do 5c §7)
    bloqueia, motivo = gs.decidir(perfil, ferramenta, {"path": ".claude/settings.json"}, CWD)
    assert bloqueia and "(R5," in motivo


@pytest.mark.parametrize("perfil", gs.PERFIS)
@pytest.mark.parametrize("ferramenta, entrada", [
    ("mcp__fs__copy_file", {"path": "src/a.py", "destination": ".claude/settings.json"}),  # E14
    ("mcp__fs__append_file", {"target": [".claude/settings.json"]}),
    ("mcp__fs__put_file", {"arquivo": "tools/guarda_agentes.py"}),
])
def test_ferramenta_de_escrita_com_destino_em_qualquer_chave(perfil, ferramenta, entrada):  # E14
    bloqueia, motivo = gs.decidir(perfil, ferramenta, entrada, CWD)
    assert bloqueia and "(R5," in motivo


def test_ferramenta_que_nao_grava_pode_citar_a_fiacao():
    entrada = {"message": "OK: alterei .claude/agents/mecanico.md e tools/guarda_agentes.py"}
    assert gs.decidir("seguranca", "SubagentHandback", entrada, CWD) == (False, "")


@pytest.mark.parametrize("perfil", gs.PERFIS)
def test_ferramenta_de_escrita_com_nome_minusculo_tem_r5(perfil):  # D16
    bloqueia, motivo = gs.decidir(perfil, "mcp__fs__write_file", {"path": ".claude/settings.json"}, CWD)
    assert bloqueia and "(R5," in motivo
    bloqueia, motivo = gs.decidir(perfil, "mcp__fs__edit_file", {"path": "tools/guarda_agentes.py"}, CWD)
    assert bloqueia and "(R5," in motivo


def test_ferramenta_de_escrita_com_nome_minusculo_tem_r4():  # D16
    bloqueia, motivo = gs.decidir("seguranca", "mcp__fs__write_file", {"path": "src/x.py"}, CWD)
    assert bloqueia and "(R4," in motivo
    assert gs.decidir("mecanico", "mcp__fs__write_file", {"path": "src/x.py"}, CWD) == (False, "")


@pytest.mark.parametrize("perfil, ferramenta, comando", SHELL_LIBERADOS)
def test_shell_liberado(perfil, ferramenta, comando):
    assert _sh(perfil, comando, ferramenta) == (False, "")


SHELL_R4 = [
    ("Bash", "echo x > src/x.py"),                                       # B1
    ("Bash", "echo x>src/x.py"),                                         # B2
    ("Bash", ">src/x.py echo x"),                                        # B3
    ("Bash", "echo x > s\"r\"c/x.py"),                                   # B4
    ("Bash", "echo x | tee -a src/x.py"),                                # B5
    ("Bash", f"cp {E}/a src/x.py"),                                      # B6
    ("Bash", f"mv src/x.py {E}/"),                                       # B7
    ("Bash", "rm -f app.py"),                                            # B8
    ("Bash", "touch x.txt"),                                             # B9
    ("Bash", "sed -i 's/a/b/' src/x.py"),                                # B10
    ("Bash", "dd if=/dev/zero of=src/x.py"),                             # B11
    ("Bash", "truncate -s 0 src/x.py"),                                  # B12
    ("Bash", f"echo x > {E}/$X"),                                        # B13
    ("Bash", "echo x > docs/entregas/../src/x.py"),                      # B14
    ("Bash", f"cd {E}/nao_existe; echo x > app.py"),                     # B15
    ("Bash", f"S=src; false && S={E}; echo x > $S/a"),                   # B16
    ("Bash", f"(S={E}); echo x > $S/a"),                                 # B17
    ("Bash", "cd \"$X\" && echo x > a.txt"),                             # B18
    ("Bash", f"cat > {E}/a.md <<'EOF'\nx'\nEOF\necho y > src/x.py\ncat > {E}/b.md <<'EOF'\n'\nEOF"),  # B19
    ("Bash", "echo \"<<EOF\"\necho y > src/x.py\nEOF"),                  # B20
    ("Bash", "bash -c \"echo x > src/x.py\""),                           # B21
    ("Bash", "sh -c 'echo x > src/x.py'"),                               # B22
    ("Bash", "cmd /c \"echo x > src\\x.py\""),                           # B23
    ("Bash", "powershell -NoProfile -Command \"Set-Content src/x.py x\""),  # B24
    ("Bash", "pwsh -EncodedCommand ZQBjAGgAbwA="),                       # B25
    ("Bash", "eval \"echo x > src/x.py\""),                              # B26
    ("Bash", "echo x > >(cat > src/x.py)"),                              # B27
    ("Bash", "echo 'x > src/x.py"),                                      # B28
    ("Bash", f"find {E} -name '*.tmp' | xargs rm"),                      # B29
    ("Bash", "find src -name '*.pyc' -delete"),                          # B30
    ("Bash", f"ln -s \"{CWD}/src\" {E}/l"),                              # B31
    ("Bash", "echo x > \"$HOME/x\""),                                    # B33
    ("Bash", "echo x > ~/x"),                                            # B33
    ("Bash", "{ echo x; } > src/x.py"),                                  # B34
    ("Bash", "echo x > /tmp/x"),                                         # B35 (falso positivo documentado)
    ("Bash", f"(cd src && echo x > a.py); echo y > {E}/a.txt"),
    ("Bash", f"echo $(echo x > src/x.py) > {E}/a.txt"),
    ("PowerShell", "Set-Content src/x.py x"),                            # B36
    ("PowerShell", "Set-Content -Value x src/x.py"),                     # B37
    ("PowerShell", "Set-Content -Path:src/x.py -Value x"),               # B38
    ("PowerShell", "'x' | Out-File -FilePath src\\x.py"),                # B39
    ("PowerShell", "Add-Content -LiteralPath src/x.py x"),               # B40
    ("PowerShell", "Set-Content -Force src/x.py x"),                     # B40
    ("PowerShell", "New-Item -Path src -Name x.py -ItemType File"),      # B41
    ("PowerShell", f"Copy-Item {E}/a src/x.py"),                         # B42
    ("PowerShell", f"Move-Item src/x.py {E}/"),                          # B43
    ("PowerShell", f"Remove-Item {E}/a,src/x.py"),                       # B44
    ("PowerShell", "Rename-Item src/x.py y.py"),                         # B45
    ("PowerShell", "ni src/x.py"), ("PowerShell", "del src/x.py"), ("PowerShell", "sc src/x.py x"),     # B46
    ("PowerShell", "ac src/x.py x"), ("PowerShell", "cpi a src/x.py"), ("PowerShell", "mi src/x.py b"),
    ("PowerShell", "ri src/x.py"), ("PowerShell", "'x' | tee src/x.py"), ("PowerShell", "rni src/x.py y"),
    ("PowerShell", "clc src/x.py"),
    ("PowerShell", "[IO.File]::WriteAllText('src/x.py','x')"),           # B47
    ("PowerShell", "echo x > src\\x.py"),                                # B48
    ("PowerShell", "Set-Content docs/entregas/t\\..\\..\\..\\src\\x.py x"),  # B49
    ("PowerShell", "Write-Output a\\\nSet-Content src/x.py x"),          # B50
    ("PowerShell", f"$p = '{E}'; $P = 'src'; Set-Content \"$p/x.py\" x"),  # B51
    ("PowerShell", "Set-Alias w Set-Content; w src/x.py x"),             # B52
    ("PowerShell", f"@\"\n$(Set-Content src/x.py x)\n\"@ | Out-File {E}/a.txt"),  # B54
    ("PowerShell", f"Get-ChildItem {E} | Remove-Item"),                  # B55 (falso positivo por desenho)
    ("PowerShell", "Start-Process python -RedirectStandardOutput src/x.txt"),  # B56
    ("PowerShell", "<# x\n#> Set-Content src/x.py x"),
    ("PowerShell", "Set-Content HKCU:\\Software\\x x"),
    ("PowerShell", f"$a = @(1); Set-Content @a"),
    # Segmento e cd condicional.
    ("Bash", f"false && cd docs/entregas; echo x > t/a"),                # cd pulado: o destino real é <raiz>/t/a
    ("Bash", f"X=$(false) && Y={E}; echo x > $Y/a"),                     # atribuição com $( ) pode falhar
    ("Bash", f"mkdir -p {E} && O={E}; echo x > $O/a"),                   # condicional usada em outro segmento
    ("Bash", f"O={E}; for O in src; do echo x > $O/a; done"),            # palavra-chave e for O
    ("Bash", f"O={E}; read O; echo x > $O/a"),                           # palavra solta
    ("Bash", f"if true; then O={E}; fi; echo x > $O/a"),
    ("Bash", f"O=src; if c; then\nO={E}\nfi\necho x > $O/a"),           # palavra-chave encerra as atribuições
    ("PowerShell", f"$o = '{E}'; foreach ($o in @('src')) {{ Set-Content \"$o/x.py\" x }}"),
    ("Bash", "pwsh -Command \"Set-Content src/x.py x\""),
    ("Bash", "bash -c \"$X\""),
    # Conferência do passo 5 (conferencia.md, D1 a D16) e R1.
    ("Bash", "if :; then cp evil ../../fora.txt; fi"),                   # D1
    ("Bash", "for f in a; do rm -rf ../../x; done"),                     # D1
    ("Bash", "! touch ../../fora.txt"),                                  # D1
    ("PowerShell", "$x = Set-Content ../../fora.txt evil"),              # D2
    ("PowerShell", "$x = & sc ../../fora.txt y"),                        # D2
    ("PowerShell", ". Set-Content ../../fora.txt evil"),                 # D4
    ("Bash", "echo x > $\"docs/entregas/t/conferencia.md\""),            # D5
    ("Bash", "echo x >&1/../../../fora.txt"),                            # D6
    ("Bash", "cd docs & echo x > entregas/t/conferencia_a.md"),                     # D7: cd em segundo plano não muda o cwd
    ("Bash", "cd docs | cat; echo x > entregas/t/conferencia_a.md"),                # D7
    ("Bash", "cd docs; if :; then cd ..; fi; echo x > entregas/t/conferencia_a.md"),  # D9
    ("Bash", "cmd //c \"echo x > ../../fora.txt\""),                     # D10
    ("Bash", "cmd /c powershell -c Set-Content ../../fora.txt x"),       # D11
    ("PowerShell", "Set-Content docs/entregas/t/x,../conferencia.md -Value evil"),  # D12
    ("PowerShell", "Out-File -wv docs/entregas/t/conferencia.md ../../fora.txt -InputObject x"),  # D13
    ("PowerShell", "Set-Content -Bogus docs/entregas/t/conferencia.md ../../fora.txt -Value x"),  # P8: parâmetro desconhecido
    ("PowerShell", "Invoke-Command ([scriptblock]::Create(\"sc ../../fora.txt x\"))"),  # D14
    ("Bash", "exec -a z touch ../../fora.txt"),                          # D15
    ("Bash", "time -p touch ../../fora.txt"),                            # D15
    ("Bash", "sudo -u x touch ../../fora.txt"),                          # D15
    ("Bash", "robocopy evil ../../x /E"),                                # R1
    ("PowerShell", "xcopy evil ..\\..\\x\\ /E"),                         # R1
    ("Bash", "robocopy evil"),                                           # R1: sem destino reconhecível
    # Reconferência do passo 5b (conferencia_5b.md): os E plausíveis por acidente (decisão de 2026-11-23).
    ("Bash", "cd docs && true & echo x > entregas/t/conferencia_z.md"),  # E2: lista em segundo plano
    ("Bash", "echo 'touch ../../fora.txt' | bash"),                      # E5
    ("Bash", "bash <<< 'touch ../../fora.txt'"),                         # E5
    ("PowerShell", "'Set-Content ../../fora.txt x' | pwsh -c -"),        # E5
    ("Bash", "echo 'Set-Content ../../fora.txt x' | pwsh -NoProfile"),  # E5: pwsh sem -Command lê a entrada
    ("Bash", "pwsh -ExecutionPolicy Bypass -Command \"Set-Content ../../fora.txt x\""),  # E6
    ("Bash", "bash -o pipefail -c \"touch ../../fora.txt\""),            # E6
    ("PowerShell", "Set-Content -D ../../fora.txt docs/entregas/t/conferencia_a.md"),  # E10
    ("PowerShell", "Set-Content docs/entregas/t/conferencia_a.md ,../../fora.txt -Value x"),  # E11
    ("Bash", "timeout -k 1 5 touch ../../fora.txt"),                     # E12
    ("Bash", "stdbuf -o L touch ../../fora.txt"),                        # E12
    ("Bash", "nice --adjustment 5 touch ../../fora.txt"),                # E12
    ("Bash", f"robocopy //E {E} ../../x"),                               # E13
    ("PowerShell", f"robocopy src {E} /LOG:..\\..\\fora.txt"),           # E13
    ("PowerShell", f"robocopy ../../x {E} /MOVE"),                       # E13: /MOVE remove a origem
    ("Bash", f"robocopy /E ../../x {E}"),                                # N29f: o Git Bash converte /E em E:/
    # Era liberado no 819311b; o experimento do N29f mostrou que, no Git Bash, o /E vira E:/ e desloca origem e
    # destino. Expectativa alterada com justificativa (a forma certa, //E, está em SHELL_LIBERADOS).
    ("Bash", f"robocopy src {E} /E"),
    # Conferência do passo 5c (conferencia_5c.md, F2 e F3).
    ("Bash", "cd docs && sleep 1 &\necho x > entregas/t/conferencia_z.md"),     # F2: & seguido de newline
    ("Bash", "cd docs &&\nsleep 1 &\necho x > entregas/t/conferencia_z.md"),    # F2
    ("PowerShell", f"robocopy src {E} /E /LOG:$PWD\\robo.log"),                  # F3: log com variável
    ("Bash", f"robocopy //E src {E} //LOG:$HOME/robo.log"),                       # F3
    ("Bash", "echo 'touch ../../fora.txt' | bash -es x"),                         # F1: -s agrupado lê a entrada
]


@pytest.mark.parametrize("perfil", ("verificador", "seguranca"))
@pytest.mark.parametrize("ferramenta, comando", SHELL_R4)
def test_shell_r4_bloqueado(perfil, ferramenta, comando):
    bloqueia, motivo = _sh(perfil, comando, ferramenta)
    assert bloqueia and "(R4," in motivo and "PARE" in motivo


def test_shell_r4_seguranca_so_grava_decisao_e_conferencia():  # B57
    bloqueia, motivo = _sh("seguranca", f"echo x > {E}/notas.md")
    assert bloqueia and "(R4," in motivo
    assert _sh("verificador", f"echo x > {E}/notas.md") == (False, "")


def test_shell_r4_temp_que_se_sobrepoe_a_raiz_nao_vale():  # B58
    assert _sh("verificador", "echo x > src/x.py", temp=CWD)[0]
    assert _sh("verificador", f"echo x > \"{CWD}/src/x.py\"", temp=str(_RAIZ.parent))[0]


SHELL_R5 = [
    ("Bash", "echo x > .claude/settings.local.json"),                    # F14
    ("Bash", "sed -i s/a/b/ .claude/agents/mecanico.md"),                # F15
    ("Bash", "cp \"$S/g.py\" tools/guarda_agentes.py"),                  # F16
    ("Bash", "cp \"$S/guarda_agentes.py\" tools/"),                      # F17
    ("Bash", f"mv .claude/settings.local.json \"{T}/x\""),               # F18
    ("Bash", "rm -rf .claude"),                                          # F19
    ("Bash", "rm -rf tools"),                                            # F20
    ("Bash", "rm -rf ."), ("Bash", f"rm -rf \"{CWD}\""),                 # F21
    ("Bash", f"cp -r \"{T}/evil/.\" ."),                                 # F22
    ("Bash", "echo x > \"$X/.claude/settings.json\""),                   # F23
    ("Bash", f"ln tools/guarda_agentes.py \"{T}/g.py\""),                # F24
    ("PowerShell", f"New-Item -ItemType HardLink -Path \"{T}\\g.py\" -Target tools\\guarda_agentes.py"),  # F25
    ("PowerShell", "Set-Content ‘tools/guarda_agentes.py’ x"),  # F26
    ("PowerShell", f"Set-Content \"{CWD}\\tools\\guarda_agentes.py\" x"),  # F27 (\ não é escape no PowerShell)
    ("Bash", "bash -c \"echo x > .claude/settings.json\""),              # F28
    ("Bash", "cmd /c \"copy x .claude\\settings.json\""),                # F29
    ("Bash", "cd .claude && echo {} > settings.local.json"),             # F30
    ("Bash", "cd tools; echo x > guarda_agentes.py"),                    # F31
    ("Bash", "echo x > ~/.claude/settings.json"),                        # F32
    ("Bash", f"tar -xf \"{T}/a.tar\""),                                  # F33
    ("PowerShell", f"Expand-Archive \"{T}\\a.zip\" -DestinationPath ."),  # F34
    ("Bash", "rm tools/*.py"),                                           # F35
    ("Bash", "rm .cl*/agents/x.md"),                                     # F36
    ("Bash", "echo x > \"$(echo .claude)/settings.json\""),              # F37
    ("Bash", f"echo x > \"{_PREFIXO_PY}/Lib/site-packages/x.pth\""),     # N8
    ("PowerShell", f"Copy-Item \"{T}\\s.py\" \"{_PREFIXO_PY}\\Lib\\site-packages\\sitecustomize.py\""),  # N8
    ("PowerShell", "Copy-Item \"$S\\guarda_agentes.py\" tools\\"),     # dest/basename(fonte) no Copy-Item
    # Conferência do passo 5 (conferencia.md, D1 a D15; experimento_shell.md) e R1.
    ("Bash", "if true; then cp evil .claude/settings.json; fi"),        # D1
    ("Bash", "! cp evil tools/guarda_agentes.py"),                       # D1
    ("PowerShell", "$x = Set-Content .claude/settings.json evil"),       # D2
    ("PowerShell", "$null = Set-Content .claude/settings.json evil"),    # D3
    ("PowerShell", ". Set-Content .claude/settings.json evil"),          # D4
    ("PowerShell", "return Set-Content .claude/settings.json evil"),  # D4
    ("Bash", "echo x > $\".claude/settings.json\""),                     # D5
    ("Bash", "echo x >&1/../.claude/settings.json"),                     # D6
    ("Bash", "CDPATH=.claude; cd agents && echo x > mecanico.md"),       # D8
    ("Bash", "if :; then cd .claude; fi; echo x > settings.json"),       # D9
    ("Bash", "cmd //c \"echo x > .claude/settings.json\""),              # D10
    ("Bash", "cmd /c \"powershell -c Set-Content .claude/settings.json x\""),  # D11
    ("PowerShell", "Set-Content x.txt,.claude/settings.json -Value evil"),  # D12
    ("PowerShell", "Set-Content -PipelineVariable pv .claude/settings.json -Value evil"),  # D13
    ("PowerShell", "Invoke-Command -ScriptBlock ([scriptblock]::Create(\"Set-Content .claude/settings.json x\"))"),  # D14
    ("Bash", "command -p cp evil .claude/settings.json"),                # D15
    ("Bash", "robocopy evil .claude /E"),                                # R1
    ("PowerShell", "xcopy evil .claude\\ /E"),                           # R1
    # Reconferência do passo 5b: E plausíveis por acidente.
    ("Bash", "echo 'cp evil .claude/settings.json' | bash"),             # E5
    ("PowerShell", "Set-Content -N .claude/settings.json evil"),         # E10
    ("PowerShell", "Set-Content x.txt ,.claude/settings.json -Value evil"),  # E11
    ("Bash", "timeout -s KILL 5 cp evil .claude/settings.json"),         # E12
    ("Bash", "robocopy //E evil .claude"),                               # E13
    ("PowerShell", "robocopy .claude bak /MOVE"),                        # E13
    ("PowerShell", "robocopy a b /LOG:.claude/settings.json"),           # E13
    # Conferência do passo 5c (F1): opção curta terminada em o consome valor; -s lê a entrada.
    ("Bash", "bash -euo pipefail <<'EOF'\ncp evil .claude/settings.json\nEOF"),
    ("Bash", "echo 'cp evil .claude/settings.json' | bash -eo pipefail"),
]


@pytest.mark.parametrize("perfil", gs.PERFIS)
@pytest.mark.parametrize("ferramenta, comando", SHELL_R5)
def test_shell_r5_bloqueado(perfil, ferramenta, comando):
    bloqueia, motivo = _sh(perfil, comando, ferramenta)
    assert bloqueia and "(R5," in motivo and "PARE" in motivo


@pytest.mark.parametrize("ferramenta, comando", [
    ("Bash", "printf a\\\ngit status"),
    ("PowerShell", "$x = 'a'\n# comentário com 'aspas'\nSet-Content src/x.py x"),
])
def test_shell_r4_comentario_e_continuacao_nao_escondem_comando(ferramenta, comando):
    bloqueia, motivo = _sh("verificador", comando, ferramenta)
    assert ("(R4," in motivo) is ("Set-Content" in comando)


def test_analisar_gravacao_resolve_variavel_e_cd():
    destinos, falha = gs.analisar_gravacao(f"O={E}/o.txt; cd src && echo x > $O", "bash", CWD)
    assert not falha
    assert [sorted(d["valores"]) for d in destinos] == [[gs._abs(f"src/{E}/o.txt", CWD)]]
    # cd que pode falhar (pasta inexistente) seguido de ;: o destino vale nos dois diretórios.
    destinos, _ = gs.analisar_gravacao("cd nao_existe; echo x > a", "bash", CWD)
    assert sorted(destinos[0]["valores"]) == sorted({gs._abs("a", CWD), gs._abs("nao_existe/a", CWD)})
    # cd para pasta que existe, no prefixo: não falha e não encerra o prefixo de atribuições.
    destinos, falha = gs.analisar_gravacao(f"cd \"{CWD}\" && O={E}/o.txt\ngit status > $O", "bash", CWD)
    assert not falha and sorted(destinos[0]["valores"]) == [gs._abs(f"{E}/o.txt", CWD)]
