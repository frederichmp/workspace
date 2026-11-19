"""Testes de tools/verificacao_padrao.py (docs/PROCESSO.md §5).

Sem git, sem subprocesso e sem pytest aninhado: as funções puras decidem o que é OK, e o
fluxo do main roda com _git, _ler_perfil e _rodar_pytest trocados por fakes em tmp_path.
"""
import importlib.util
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("verificacao_padrao", _RAIZ / "tools" / "verificacao_padrao.py")
vp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vp)

PROCESSO = (_RAIZ / "docs" / "PROCESSO.md").read_text(encoding="utf-8")
RESUMO_OK = "272 passed, 16 skipped, 16 warnings in 271.07s (0:04:31)"


def _saida(resumo, skips=((16, vp.MOTIVO_SKIP),)):
    linhas = ["........s....  [100%]", "=========================== short test summary info ==========================="]
    linhas += [f"SKIPPED [{n}] tests\\conftest.py:188: {motivo}" for n, motivo in skips]
    linhas.append(resumo)
    return "\n".join(linhas) + "\n"


# ---------- pytest ----------

def test_pytest_ok():
    st, _, cont = vp.analisar_pytest(_saida(RESUMO_OK), 0, 272, 16)
    assert st == vp.OK
    assert cont["passed"] == 272 and cont["skipped"] == 16


def test_pytest_skipped_abaixo_do_esperado_para():
    saida = _saida("280 passed, 8 skipped in 300.00s", skips=((8, vp.MOTIVO_SKIP),))
    st, motivo, _ = vp.analisar_pytest(saida, 0, 280, 16)
    assert st == vp.PARE
    assert "SANDBOX" in motivo


def test_pytest_skip_com_outro_motivo_falha():
    saida = _saida(RESUMO_OK, skips=((15, vp.MOTIVO_SKIP), (1, "dependência ausente")))
    st, motivo, _ = vp.analisar_pytest(saida, 0, 272, 16)
    assert st == vp.FALHA
    assert "outro motivo" in motivo


def test_pytest_falha_de_governanca_para_mesmo_com_contagem_certa():
    saida = _saida(RESUMO_OK) + "\nFALHA DE GOVERNANCA: data/logs/kill_approval.log real foi alterado\n"
    st, _, _ = vp.analisar_pytest(saida, 1, 272, 16)
    assert st == vp.PARE


def test_pytest_exit_de_governanca_para():
    saida = "! _pytest.outcomes.Exit: FALHA DE GOVERNANCA: ORACLE_SANDBOX alterado. Nenhum teste executado. !\r\n"
    st, _, _ = vp.analisar_pytest(saida, 3, 272, 16)
    assert st == vp.PARE


def test_pytest_texto_de_governanca_citado_por_teste_que_falhou_e_falha():
    saida = ('        (0, "FALHA DE GOVERNANCA: x", vp.PARE),\n'
             "E   assert 'FALHA DE GOVERNANCA: x' == 'y'\n"
             + _saida("1 failed, 271 passed, 16 skipped in 270.00s"))
    st, _, _ = vp.analisar_pytest(saida, 1, 272, 16)
    assert st == vp.FALHA


def test_pytest_erro_de_import_do_oracledb_nao_verificado():
    saida = ("ImportError while loading conftest\n"
             "  File \"site-packages/oracledb/__init__.py\", line 40\n"
             "ImportError: DLL load failed while importing base_impl: bloqueado\n")
    st, motivo, _ = vp.analisar_pytest(saida, 4, 272, 16)
    assert st == vp.NAO_VERIFICADO
    assert "oracledb" in motivo


def test_pytest_sem_linha_de_contagem_nao_verificado():
    st, _, _ = vp.analisar_pytest("saída cortada\n", 0, 272, 16)
    assert st == vp.NAO_VERIFICADO


def test_pytest_tempo_esgotado_nao_verificado():
    st, _, _ = vp.analisar_pytest(_saida(RESUMO_OK), None, 272, 16)
    assert st == vp.NAO_VERIFICADO


def test_pytest_failed_falha():
    st, _, _ = vp.analisar_pytest(_saida("1 failed, 271 passed, 16 skipped in 270.00s"), 1, 272, 16)
    assert st == vp.FALHA


def test_pytest_passed_diferente_do_esperado_falha():
    st, motivo, _ = vp.analisar_pytest(_saida("270 passed, 16 skipped in 270.00s"), 0, 272, 16)
    assert st == vp.FALHA
    assert "passed" in motivo


# ---------- greps ----------

@pytest.mark.parametrize("codigo, linhas, esperado", [
    (1, [], vp.OK),
    (0, ["src/x.py:3:linha achada"], vp.FALHA),
    (2, [], vp.ERRO),
    (128, [], vp.ERRO),
])
def test_classificar_grep(codigo, linhas, esperado):
    assert vp.classificar_grep(codigo, linhas)[0] == esperado


LINHAS_LOAD_DOTENV = ["app.py:39:    load_dotenv(_ENV, override=False)",
                      "src/main.py:24:    load_dotenv(_ENV, override=False)"]


def test_load_dotenv_ok():
    assert vp.classificar_load_dotenv(0, LINHAS_LOAD_DOTENV)[0] == vp.OK


def test_load_dotenv_com_override_true_falha():
    linhas = [LINHAS_LOAD_DOTENV[0], "src/main.py:24:    load_dotenv(_ENV, override=True)"]
    assert vp.classificar_load_dotenv(0, linhas)[0] == vp.FALHA


def test_load_dotenv_com_tres_linhas_falha():
    linhas = LINHAS_LOAD_DOTENV + ["src/outro.py:5:    load_dotenv(override=False)"]
    assert vp.classificar_load_dotenv(0, linhas)[0] == vp.FALHA


def test_registry_vazio_ok():
    assert vp.classificar_registry("", False, [], "")[0] == vp.OK


def test_registry_alterado_sem_flag_falha():
    assert vp.classificar_registry(" registry/x.yaml | 2 +-", False, [], "")[0] == vp.FALHA


def test_registry_com_flag_exige_tudo_commitado_e_marcado():
    stat = " registry/x.yaml | 2 +-"
    assert vp.classificar_registry(stat, True, [], "")[0] == vp.OK
    assert vp.classificar_registry(stat, True, ["abc1234"], "")[0] == vp.FALHA
    assert vp.classificar_registry(stat, True, [], " registry/x.yaml | 1 +")[0] == vp.FALHA


def test_marca_pendente_com_e_sem_acento():
    assert vp.tem_marca_pendente("chore: hash novo (PENDENTE APROVAÇÃO)")
    assert vp.tem_marca_pendente("chore: hash novo PENDENTE APROVACAO")
    assert not vp.tem_marca_pendente("chore: hash novo")


def test_env_versionado():
    assert vp.env_versionado([".env", "docs/.env", ".env.example", "a/b.env"]) == [".env", "docs/.env"]


# ---------- igualdade com o §5 (L23) ----------

def _em_bash(texto, padrao):
    if padrao:
        return '"' + texto.replace('"', '\\"') + '"' if "'" in texto else "'" + texto + "'"
    return "'" + texto + "'" if "*" in texto else texto


def _linha_bash(args):
    i = args.index("--")
    flags, padrao, caminhos = args[:i - 1], args[i - 1], args[i + 1:]
    return " ".join(["git grep", *flags, _em_bash(padrao, True), "--", *(_em_bash(c, False) for c in caminhos)])


@pytest.mark.parametrize("args", [g[2] for g in vp.GREPS] + [vp.GREP_LOAD_DOTENV],
                         ids=[g[0] for g in vp.GREPS] + ["3.4"])
def test_greps_iguais_aos_do_processo(args):
    linhas = [l.split("#")[0].rstrip() for l in PROCESSO.splitlines()]
    assert _linha_bash(args) in linhas


def test_perfil_pytest_e_motivo_iguais_aos_do_processo_e_do_conftest():
    assert vp.CMD_PERFIL_NUCLEO in PROCESSO
    assert f"'{vp.PREFIXOS_PROIBIDOS.pattern}'" in PROCESSO
    assert "python " + " ".join(vp.ARGS_PYTEST) in PROCESSO
    assert f"'{vp.RE_ENV}'" in PROCESSO
    assert "git diff --stat <base> -- registry/ db/" in PROCESSO
    assert vp.MOTIVO_SKIP in (_RAIZ / "tests" / "conftest.py").read_text(encoding="utf-8")


# ---------- git status ----------

def test_ler_status_z_com_renomeacao_e_prefixo():
    saida = ("R  IA/PERSONAL_AGENT/docs/novo.md\0IA/PERSONAL_AGENT/docs/velho.md\0"
             "?? IA/PERSONAL_AGENT/tests/x.py\0")
    assert vp.ler_status_z(saida, "IA/PERSONAL_AGENT/") == [
        ("R ", "docs/novo.md"), ("R ", "docs/velho.md"), ("??", "tests/x.py")]


def test_renomeacao_que_sai_de_tests_manda_parar():
    itens = vp.ler_status_z("R  docs/novo.py\0tests/velho.py\0", "")
    fora, parar = vp.classificar_status(itens, ["docs/*"], "t1")
    assert parar == [("R ", "tests/velho.py")]


def test_status_previsto_e_saida_da_tarefa_passam():
    itens = [("??", "docs/entregas/t1/a.txt"), ("??", "docs/entregas/1.11/item1/abc/x.md"), (" M", "docs/PROCESSO.md")]
    fora, parar = vp.classificar_status(itens, ["docs/entregas/1.11/item1/*", "docs/PROCESSO.md"], "t1")
    assert fora == [] and parar == []


def test_status_fora_do_previsto_em_tests_ou_na_raiz_manda_parar():
    itens = [("??", "tests/test_intruso.py"), ("??", "docs/nota.md"), ("??", "intruso.py")]
    fora, parar = vp.classificar_status(itens, [], "t1")
    assert [c for _, c in fora] == ["tests/test_intruso.py", "docs/nota.md", "intruso.py"]
    assert [c for _, c in parar] == ["tests/test_intruso.py", "intruso.py"]


# ---------- argumentos e perfil ----------

@pytest.mark.parametrize("tarefa", ["../fora", "a/../b", "a b", "/abs", ".", "a\\b", ""])
def test_validar_tarefa_recusa(tarefa):
    with pytest.raises(ValueError):
        vp.validar_tarefa(tarefa)


@pytest.mark.parametrize("tarefa", ["revisao-subagentes-v2", "1.11/item1"])
def test_validar_tarefa_aceita(tarefa):
    assert vp.validar_tarefa(tarefa) == tarefa


@pytest.mark.parametrize("base", ["--output=x", "-p", "", "a b", "x;y", "HEAD@{1}"])
def test_validar_base_recusa(base):
    with pytest.raises(ValueError):
        vp.validar_base(base)


@pytest.mark.parametrize("base", ["486dd9b", "HEAD~1", "main", "3f2db49^"])
def test_validar_base_aceita(base):
    assert vp.validar_base(base) == base


@pytest.mark.parametrize("padrao", ["*", "*.md", "?", "docs*", "tests/*", "src/tools/*.py", "registry/*", "db/*.sql"])
def test_validar_previsto_recusa_curinga_amplo(padrao):
    with pytest.raises(ValueError):
        vp.validar_previsto(padrao)


@pytest.mark.parametrize("padrao", ["docs/entregas/1.11/item1/*", ".claude/agents/*.md", "tests/test_x.py",
                                    "CLAUDE.md", "registry/scripts.yaml"])
def test_validar_previsto_aceita(padrao):
    assert vp.validar_previsto(padrao) == padrao


@pytest.mark.parametrize("codigo, stdout, stderr, esperado", [
    (0, "Path\r\nTEMP\r\n", "", ["Path", "TEMP"]),
    (0, "Path\r\n", "Get-Item : não existe", None),
    (0, "", "", None),
    (1, "Path\r\n", "", None),
])
def test_interpretar_perfil(codigo, stdout, stderr, esperado):
    assert vp.interpretar_perfil(codigo, stdout, stderr) == esperado


def test_filtrar_perfil_so_prefixos_proibidos_sem_diferenciar_maiusculas():
    nomes = ["Path", "TEMP", "oracle_dsn_teste", "EMAIL_X", "OneDrive", "scripts_dir", "MY_ORACLE_X"]
    assert vp.filtrar_perfil(nomes) == ["EMAIL_X", "oracle_dsn_teste", "scripts_dir"]


def test_codigo_de_saida():
    assert vp.codigo_de_saida([vp.OK, vp.OK]) == 0
    assert vp.codigo_de_saida([vp.OK, vp.FALHA]) == 1
    assert vp.codigo_de_saida([vp.FALHA, vp.ERRO]) == 2
    assert vp.codigo_de_saida([vp.OK, vp.NAO_VERIFICADO]) == 2


# ---------- fluxo do main, com fakes ----------

class _Fakes:
    def __init__(self, status="", perfil=("Path", "TEMP"), pytest_resultado=(0, _saida(RESUMO_OK)), base_ok=True):
        self.status, self.perfil, self.pytest_resultado, self.base_ok = status, perfil, pytest_resultado, base_ok
        self.git_chamadas, self.pytest_chamado = [], False

    def git(self, *args, timeout=120):
        self.git_chamadas.append(args)
        if args[:2] == ("rev-parse", "--verify"):
            return (0, "a" * 40 + "\n") if self.base_ok else (1, "")
        respostas = {"--short": "abc1234\n", "--show-prefix": "IA/PERSONAL_AGENT/\n"}
        if args[0] == "rev-parse":
            return 0, respostas[args[1]]
        if args[0] == "branch":
            return 0, "main\n"
        if args[0] == "status":
            return 0, self.status
        if args[0] == "grep":
            return (0, "\n".join(LINHAS_LOAD_DOTENV) + "\n") if "load_dotenv\\(" in args else (1, "")
        if args[0] in ("diff", "log"):
            return 0, ""
        if args[0] == "ls-files":
            return 0, "app.py\n.env.example\n"
        raise AssertionError(f"git inesperado: {args}")

    def rodar_pytest(self):
        self.pytest_chamado = True
        return self.pytest_resultado


ARGS_MAIN = ["--tarefa", "t1", "--base", "3f2db49", "--esperado", "272/16"]


@pytest.fixture
def fakes(monkeypatch, tmp_path):
    def instalar(**kw):
        f = _Fakes(**kw)
        monkeypatch.setattr(vp, "RAIZ", tmp_path)
        monkeypatch.setattr(vp, "_git", f.git)
        monkeypatch.setattr(vp, "_ler_perfil", lambda: list(f.perfil) if f.perfil is not None else None)
        monkeypatch.setattr(vp, "_rodar_pytest", f.rodar_pytest)
        return f
    return instalar


def test_main_tudo_ok_grava_so_na_pasta_da_tarefa(fakes, tmp_path):
    f = fakes()
    assert vp.main(ARGS_MAIN) == 0
    assert f.pytest_chamado
    gravados = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert gravados and all(g.startswith("docs/entregas/t1/padrao") for g in gravados)


def test_main_perfil_proibido_nao_roda_pytest(fakes):
    f = fakes(perfil=("Path", "ORACLE_X"))
    assert vp.main(ARGS_MAIN) == 2
    assert not f.pytest_chamado


def test_main_perfil_que_nao_le_nao_roda_pytest(fakes):
    f = fakes(perfil=None)
    assert vp.main(ARGS_MAIN) == 2
    assert not f.pytest_chamado


def test_main_tests_fora_do_previsto_nao_roda_pytest(fakes):
    f = fakes(status="?? IA/PERSONAL_AGENT/tests/test_intruso.py\0")
    assert vp.main(ARGS_MAIN) == 2
    assert not f.pytest_chamado


def test_main_pytest_com_falha_nao_roda_greps(fakes):
    f = fakes(pytest_resultado=(1, _saida("1 failed, 271 passed, 16 skipped in 1.00s")))
    assert vp.main(ARGS_MAIN) == 1
    assert not [a for a in f.git_chamadas if a[0] == "grep"]


def test_main_base_que_parece_opcao_sai_2_sem_git(fakes):
    f = fakes()
    assert vp.main(["--tarefa", "t1", "--base=--output=x", "--esperado", "272/16"]) == 2
    assert f.git_chamadas == []


def test_main_base_que_nao_e_commit_sai_2(fakes):
    f = fakes(base_ok=False)
    assert vp.main(ARGS_MAIN) == 2
    assert not f.pytest_chamado


def test_main_nao_sobrescreve_saida(fakes, tmp_path):
    f = fakes()
    (tmp_path / "docs" / "entregas" / "t1").mkdir(parents=True)
    (tmp_path / "docs" / "entregas" / "t1" / "padrao.md").write_text("anterior", encoding="utf-8")
    assert vp.main(ARGS_MAIN) == 2
    assert not f.pytest_chamado
    assert (tmp_path / "docs" / "entregas" / "t1" / "padrao.md").read_text(encoding="utf-8") == "anterior"


class _PopenQueEstoura:
    pid = 4242
    returncode = None

    def __init__(self, *args, **kwargs):
        self.chamadas = 0

    def communicate(self, timeout=None):
        self.chamadas += 1
        if self.chamadas == 1:
            raise vp.subprocess.TimeoutExpired("cmd", timeout)
        return b"parcial", None

    def kill(self):
        pass


def test_estouro_de_tempo_mata_a_arvore_de_processos(monkeypatch):
    mortos = []
    monkeypatch.setattr(vp, "_matar_arvore", mortos.append)
    codigo, saida = vp._executar(["x"], ".", {}, 1, popen=_PopenQueEstoura)
    assert (codigo, saida, mortos) == (None, "parcial", [4242])


def test_matar_arvore_usa_taskkill_com_a_arvore():
    chamadas = []
    vp._matar_arvore(4242, run=lambda argv, **kw: chamadas.append(argv), windows=True)
    assert chamadas == [["taskkill", "/F", "/T", "/PID", "4242"]]


def test_gravar_nao_sobrescreve(tmp_path):
    alvo = tmp_path / "saida.md"
    alvo.write_text("anterior", encoding="utf-8")
    with pytest.raises(FileExistsError):
        vp._gravar(alvo, "novo")
    assert alvo.read_text(encoding="utf-8") == "anterior"


def test_main_erro_inesperado_sai_2(fakes, monkeypatch):
    fakes()

    def quebra():
        raise OSError("disco")
    monkeypatch.setattr(vp, "_rodar_pytest", quebra)
    assert vp.main(ARGS_MAIN) == 2
