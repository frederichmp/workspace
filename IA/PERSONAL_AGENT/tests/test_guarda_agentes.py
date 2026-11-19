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
