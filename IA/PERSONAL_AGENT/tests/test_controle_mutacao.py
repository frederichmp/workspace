"""Testes de tools/controle_mutacao.py (docs/PROCESSO.md §5).

Funções puras e o fluxo do main com fakes no lugar da cópia e do pytest: sem git e sem pytest aninhado.
"""
import importlib.util
import json
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("controle_mutacao", _RAIZ / "tools" / "controle_mutacao.py")
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)


# ---------- troca ----------

def test_troca_com_uma_ocorrencia():
    novo, crlf, lf_so = cm.aplicar_troca(b"a = 1\nb = 2\n", "b = 2", "b = 3")
    assert novo == b"a = 1\nb = 3\n"
    assert (crlf, lf_so) == (0, 2)


@pytest.mark.parametrize("texto, de", [(b"x\nx\n", "x"), (b"abc\n", "zzz")])
def test_troca_exige_exatamente_uma_ocorrencia(texto, de):
    with pytest.raises(ValueError):
        cm.aplicar_troca(texto, de, "y")


def test_troca_em_crlf_com_de_em_lf_falha_e_diz_o_fim_de_linha():
    with pytest.raises(ValueError, match="2 CRLF"):
        cm.aplicar_troca(b"a\r\nb\r\n", "a\nb", "c")


def test_troca_em_utf8():
    novo, _, _ = cm.aplicar_troca("ação = 1\n".encode("utf-8"), "ação", "acao")
    assert novo == b"acao = 1\n"


# ---------- classificação ----------

@pytest.mark.parametrize("codigo, saida, esperado", [
    (0, "....\n5 passed in 1.00s\n", cm.PASSOU),
    (0, "5 passed, 2 skipped, 13 warnings in 1.00s\n", cm.PASSOU),
    (1, "FAILED tests/x.py::test_a - assert\n1 failed, 4 passed in 1.00s\n", cm.DETECTADA),
    # KM2 (plano 9.10.2; expectativa alterada pela regra pedida): só "error" deixa de ser mutante morto.
    (1, "ERROR tests/x.py::test_b - erro\n1 error, 4 passed in 1.00s\n", cm.INVALIDA),
    (1, "FAILED tests/x.py::test_a - x\nERROR tests/x.py::test_b - e\n1 failed, 1 error in 1.00s\n", cm.DETECTADA),
    (2, "FAILED tests/x.py::test_a - x\n1 failed in 1.00s\n", cm.INVALIDA),
    (3, "1 failed in 1.00s\n", cm.INVALIDA),
    (4, "ERROR: file or directory not found: tests/x.py\n\nno tests ran in 0.01s\n", cm.INVALIDA),
    (5, "1 failed in 1.00s\n", cm.INVALIDA),
    (1, "5 passed in 1.00s\n", cm.INVALIDA),
    (2, "Interrupted: 1 error during collection\n1 error in 0.50s\n", cm.INVALIDA),
    (5, "no tests ran in 0.01s\n", cm.INVALIDA),
    (None, "", cm.INVALIDA),
    (1, "saída cortada\n", cm.INVALIDA),
    (0, "saída cortada\n", cm.INVALIDA),
    (0, "FALHA DE GOVERNANCA: x\n5 passed in 1.00s\n", cm.INVALIDA),
    (3, "! _pytest.outcomes.Exit: FALHA DE GOVERNANCA: alterado !\r\n", cm.INVALIDA),
    (1, "        (0, \"FALHA DE GOVERNANCA: x\", cm.INVALIDA),\nFAILED tests/x.py::test_g - assert\n"
        "1 failed in 1.00s\n", cm.DETECTADA),
    (1, "E   assert 'FALHA DE GOVERNANCA: x' == 'y'\nFAILED tests/x.py::test_g - assert\n1 failed in 1.00s\n",
     cm.DETECTADA),
])
def test_classificar(codigo, saida, esperado):
    assert cm.classificar(codigo, saida)[0] == esperado


def test_testes_que_cairam():
    saida = "FAILED tests/x.py::test_a - AssertionError\nERROR tests/y.py::test_b - erro\nSKIPPED [1] x\n"
    assert cm.testes_que_cairam(saida) == ["tests/x.py::test_a", "tests/y.py::test_b"]


@pytest.mark.parametrize("m0, outras, esperado", [
    (cm.PASSOU, [cm.DETECTADA, cm.DETECTADA], 0),
    (cm.PASSOU, [cm.DETECTADA, cm.PASSOU], 1),
    (cm.PASSOU, [cm.DETECTADA, cm.INVALIDA], 2),
    (cm.PASSOU, [cm.PASSOU, cm.ERRO], 2),
    (cm.INVALIDA, [cm.DETECTADA], 2),
    (None, [], 2),
])
def test_codigo_de_saida(m0, outras, esperado):
    assert cm.codigo_de_saida(m0, outras) == esperado


# ---------- validações ----------

@pytest.mark.parametrize("caminho", ["../fora.py", "/abs.py", "C:/x.py", ".env", "docs/.ENV", "a/.env.local",
                                     "a//b.py", "./x.py", "", "--noconftest", "tests/-p.py", "@args.txt",
                                     "tests/a b.py"])
def test_validar_caminho_recusa(caminho):
    with pytest.raises(ValueError):
        cm.validar_caminho(caminho)


@pytest.mark.parametrize("caminho, esperado", [
    ("tools/x.py", "tools/x.py"),
    ("tests\\test_x.py", "tests/test_x.py"),
    ("tests/test_x.py::test_y[a-b]", "tests/test_x.py::test_y[a-b]"),
    (".env.example", ".env.example"),
])
def test_validar_caminho_aceita(caminho, esperado):
    assert cm.validar_caminho(caminho) == esperado


@pytest.mark.parametrize("mutacoes", [
    [],
    [("m0", "a", "b")],
    [("m1", "a", "b"), ("m1", "c", "d")],
    [("m 1", "a", "b")],
    [("m1", "a", "a")],
    [("m1", "", "b")],
])
def test_validar_mutacoes_recusa(mutacoes):
    with pytest.raises(ValueError):
        cm.validar_mutacoes(mutacoes)


@pytest.mark.parametrize("real, esperado", [
    ("C:\\proj\\tools\\x.py", True),
    ("C:\\proj\\.env", False),
    ("C:\\fora\\x.py", False),
    ("C:\\projeto_vizinho\\x.py", False),
])
def test_incluir_seguro(real, esperado):
    assert cm.incluir_seguro(real, "C:\\proj") is esperado


class _PopenQueEstoura:
    pid = 4242
    returncode = None

    def __init__(self, *args, **kwargs):
        self.chamadas = 0

    def communicate(self, timeout=None):
        self.chamadas += 1
        if self.chamadas == 1:
            raise cm.subprocess.TimeoutExpired("cmd", timeout)
        return b"parcial", None

    def kill(self):
        pass


def test_estouro_de_tempo_mata_a_arvore_de_processos(monkeypatch):
    mortos = []
    monkeypatch.setattr(cm, "_matar_arvore", mortos.append)
    codigo, saida = cm._executar(["x"], ".", {}, 1, popen=_PopenQueEstoura)
    assert (codigo, saida, mortos) == (None, "parcial", [4242])


def test_matar_arvore_usa_taskkill_com_a_arvore():
    chamadas = []
    cm._matar_arvore(4242, run=lambda argv, **kw: chamadas.append(argv), windows=True)
    assert chamadas == [["taskkill", "/F", "/T", "/PID", "4242"]]


def test_km_ambiente_do_filho_tira_credenciais_gate_proxy_e_ollama():
    """KM (plano 9.9; mata M_KM_*): o filho não recebe ORACLE_*, EMAIL_*, GEMINI_*, OPS_KILL_*, OLLAMA_* nem *_PROXY,
    em qualquer caixa; o resto passa (positivo), e o bytecode fica desligado. Dict puro: o ambiente do pytest não muda."""
    fora = {
        "ORACLE_SANDBOX": "1", "oracle_user_diag": "x", "ORACLE_DSN": "x", "Email_Senha_App": "x",
        "PYTEST_ADDOPTS": "-k inexistente", "pytest_plugins": "x",  # KM2
        "GEMINI_API_KEY": "x", "OPS_KILL_PKG_VERSAO": "2", "ops_kill_outra": "x", "OLLAMA_HOST": "x",
        "ollama_base_url": "x", "HTTP_PROXY": "x", "https_proxy": "x", "ALL_PROXY": "x", "No_Proxy": "x",
    }
    fica = {"PATH": "p", "SYSTEMROOT": "s", "AGENTDBA_LOG_DIR": "l", "ORACLEHOME": "o", "PROXYCHAINS": "c",
            "PYTEST_XDIST_WORKER": "w", "PYTEST_ADDOPTS_OUTRO": "o"}  # KM2: só os nomes exatos saem
    env = cm.ambiente_do_filho({**fora, **fica})
    assert env == {**fica, "PYTHONDONTWRITEBYTECODE": "1"}


def test_km_rodar_testes_entrega_ao_filho_o_ambiente_filtrado(monkeypatch):
    """KM (mata M_KM_RODAR_SEM_FILTRO): _rodar_testes passa ao filho o ambiente_do_filho(os.environ). Só chaves
    fictícias são definidas aqui; o ORACLE_SANDBOX do processo não é tocado (CLAUDE.md)."""
    monkeypatch.setenv("GEMINI_API_KEY", "chave-ficticia-km")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy-sentinela.invalid:3128")
    monkeypatch.setenv("OPS_KILL_PKG_VERSAO", "2")
    monkeypatch.setenv("SENTINELA_KM_FICA", "1")
    capturado = {}

    def _executar(cmd, cwd, env, timeout):
        capturado["env"] = env
        return 0, ""

    monkeypatch.setattr(cm, "_executar", _executar)
    cm._rodar_testes(".", ["tests/x.py"])
    env = capturado["env"]
    assert env == cm.ambiente_do_filho(dict(cm.os.environ))
    assert "GEMINI_API_KEY" not in env and "HTTP_PROXY" not in env and "OPS_KILL_PKG_VERSAO" not in env
    assert env["SENTINELA_KM_FICA"] == "1" and env["PYTHONDONTWRITEBYTECODE"] == "1"


def test_gravar_nao_sobrescreve(tmp_path):
    alvo = tmp_path / "saida.txt"
    alvo.write_text("anterior", encoding="utf-8")
    with pytest.raises(FileExistsError):
        cm._gravar(alvo, "novo")
    assert alvo.read_text(encoding="utf-8") == "anterior"


# ---------- fluxo do main, com fakes ----------

ALVO = "tools/alvo.py"
ORIGINAL = b"def f():\n    return 1\n"
ARGS = ["--tarefa", "t1", "--rotulo", "c", "--alvo", ALVO, "--teste", "tests/test_alvo.py",
        "--mutacao", "m1", "return 1", "return 2"]


class _Fakes:
    def __init__(self, tmp_path, detecta=True, m0_passa=True, env_na_copia=False, quebra=False,
                 coleta_projeto=(3, 0), coleta_copia=(3, 0), m0_saida=None):
        self.coleta = {"projeto": coleta_projeto, "copia": coleta_copia}
        self.m0_saida = m0_saida
        self.coletas = []
        self.copia = tmp_path / "copia_fake"
        self.detecta, self.m0_passa, self.env_na_copia, self.quebra = detecta, m0_passa, env_na_copia, quebra
        self.vistos = []

    def criar_copia(self, tmp):
        (self.copia / "tools").mkdir(parents=True, exist_ok=True)
        (self.copia / ALVO).write_bytes(ORIGINAL)
        if self.env_na_copia:
            (self.copia / ".env").write_text("SENTINELA_FICTICIA=1\n", encoding="utf-8")
        return self.copia

    def rodar_testes(self, copia, testes):
        if self.quebra:
            raise OSError("disco")
        texto = (copia / ALVO).read_bytes()
        self.vistos.append(texto)
        if texto == ORIGINAL:
            if self.m0_passa:
                return 0, self.m0_saida or "3 passed in 0.10s\n"
            return 1, "FAILED tests/test_alvo.py::test_f - x\n1 failed, 2 passed in 0.10s\n"
        if self.detecta:
            return 1, "FAILED tests/test_alvo.py::test_f - assert\n1 failed, 2 passed in 0.10s\n"
        return 0, "3 passed in 0.10s\n"

    def coletar(self, pasta, testes):
        qual = "copia" if Path(pasta) == self.copia else "projeto"
        self.coletas.append(qual)
        return self.coleta[qual]


@pytest.fixture
def fakes(monkeypatch, tmp_path):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    tmp_copia = tmp_path / "tmp_controle"

    def criar_tmp():
        tmp_copia.mkdir()
        return tmp_copia

    def instalar(**kw):
        f = _Fakes(tmp_path, **kw)
        f.raiz, f.tmp = raiz, tmp_copia
        monkeypatch.setattr(cm, "RAIZ", raiz)
        monkeypatch.setattr(cm, "_criar_tmp", criar_tmp)
        monkeypatch.setattr(cm, "_criar_copia", f.criar_copia)
        monkeypatch.setattr(cm, "_rodar_testes", f.rodar_testes)
        monkeypatch.setattr(cm, "_coletar_testes", f.coletar)
        return f
    return instalar


def test_main_todas_detectadas_grava_saidas_e_apaga_a_copia(fakes):
    f = fakes()
    assert cm.main(ARGS) == 0
    pasta = f.raiz / "docs" / "entregas" / "t1"
    assert sorted(p.name for p in pasta.iterdir()) == ["c.md", "c_m0.txt", "c_m1.txt"]
    assert (f.copia / ALVO).read_bytes() == ORIGINAL
    assert not f.tmp.exists()


def test_main_mutacao_que_passa_sai_1(fakes):
    fakes(detecta=False)
    assert cm.main(ARGS) == 1


def test_main_m0_que_falha_nao_roda_mutacoes(fakes):
    f = fakes(m0_passa=False)
    assert cm.main(ARGS) == 2
    assert len(f.vistos) == 1


def test_main_troca_ambigua_e_erro_sem_rodar(fakes):
    f = fakes()
    args = ARGS[:-3] + ["m1", "r", "R"]
    assert cm.main(args) == 2
    assert len(f.vistos) == 1


def test_main_restaura_o_alvo_entre_mutacoes(fakes):
    f = fakes()
    assert cm.main(ARGS + ["--mutacao", "m2", "def f", "def g"]) == 0
    assert b"return 2" in f.vistos[1] and b"def f" in f.vistos[1]
    assert b"def g" in f.vistos[2] and b"return 1" in f.vistos[2]


def test_main_recusa_incluir_env_sem_rodar(fakes):
    f = fakes()
    assert cm.main(ARGS + ["--incluir", ".env"]) == 2
    assert f.vistos == []


def test_main_copia_com_env_aborta(fakes):
    f = fakes(env_na_copia=True)
    assert cm.main(ARGS) == 2
    assert f.vistos == []
    assert not f.tmp.exists()


def test_main_nao_sobrescreve_saida(fakes):
    f = fakes()
    (f.raiz / "docs" / "entregas" / "t1").mkdir(parents=True)
    (f.raiz / "docs" / "entregas" / "t1" / "c.md").write_text("anterior", encoding="utf-8")
    assert cm.main(ARGS) == 2
    assert f.vistos == []


def test_main_mutacoes_em_json(fakes):
    f = fakes()
    pasta = f.raiz / "docs" / "entregas" / "t1"
    pasta.mkdir(parents=True)
    (pasta / "mutacoes.json").write_text(json.dumps([{"nome": "m1", "de": "return 1", "para": "return 2"}]),
                                        encoding="utf-8")
    args = ARGS[:-4] + ["--mutacoes-json", "docs/entregas/t1/mutacoes.json"]
    assert cm.main(args) == 0
    assert len(f.vistos) == 2


def test_main_erro_inesperado_sai_2_e_apaga_a_copia(fakes):
    f = fakes(quebra=True)
    assert cm.main(ARGS) == 2
    assert not f.tmp.exists()


# ---------- KM2 (docs/plans/1.11-R1-ampliada.md 9.10): coleta, execução e validade da rodada ----------

@pytest.mark.parametrize("saida, esperado", [
    ("565 tests collected in 1.68s\n", (565, 0)),
    ("1 test collected in 0.01s\n", (1, 0)),
    ("3/565 tests collected (562 deselected) in 0.50s\n", (3, 562)),
    ("no tests collected in 0.01s\n", None),
    ("", None),
])
def test_km2_coletados(saida, esperado):
    assert cm.coletados(saida) == esperado


@pytest.mark.parametrize("saida, esperado", [
    ("5 passed, 2 skipped, 13 warnings in 1.00s\n", (7, 0)),
    ("1 failed, 4 passed, 1 error in 1.00s\n", (6, 0)),
    ("3 passed, 562 deselected in 0.50s\n", (3, 562)),
    ("1 xfailed, 2 passed in 0.10s\n", (3, 0)),
    ("saída cortada\n", (0, 0)),
])
def test_km2_executados(saida, esperado):
    assert cm.executados(saida) == esperado


@pytest.mark.parametrize("projeto, copia, esperado, valida", [
    ((5, 0), (5, 0), None, True),
    ((5, 0), (5, 0), 5, True),
    ((5, 0), (5, 0), 6, False),
    ((5, 0), (4, 0), None, False),
    ((3, 2), (3, 2), None, False),
    (None, (5, 0), None, False),
    ((5, 0), None, None, False),
    ((0, 0), (0, 0), None, False),
])
def test_km2_validar_coleta(projeto, copia, esperado, valida):
    assert (cm.validar_coleta(projeto, copia, esperado) is None) is valida


def test_km2_coletar_testes_usa_collect_only_e_o_ambiente_do_filho(monkeypatch):
    """KM2: a coleta roda --collect-only com o ambiente do filho (sem o PYTEST_ADDOPTS do pai)."""
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k inexistente")
    capturado = {}

    def _executar(cmd, cwd, env, timeout):
        capturado.update(cmd=cmd, env=env)
        return 0, "7 tests collected in 0.10s\n"

    monkeypatch.setattr(cm, "_executar", _executar)
    assert cm._coletar_testes(".", ["tests/x.py"]) == (7, 0)
    assert "--collect-only" in capturado["cmd"] and "tests/x.py" in capturado["cmd"]
    assert "PYTEST_ADDOPTS" not in capturado["env"]


def test_km2_rodar_testes_sem_pytest_addopts_do_pai(monkeypatch):
    """KM2 (item 4, parte com falsos): com PYTEST_ADDOPTS="-k inexistente" no pai, o filho não o recebe."""
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k inexistente")
    monkeypatch.setenv("PYTEST_PLUGINS", "plugin_inexistente")
    capturado = {}
    monkeypatch.setattr(cm, "_executar", lambda cmd, cwd, env, timeout: capturado.update(env=env) or (0, ""))
    cm._rodar_testes(".", ["tests/x.py"])
    assert "PYTEST_ADDOPTS" not in capturado["env"] and "PYTEST_PLUGINS" not in capturado["env"]


def test_km2_main_coleta_divergente_invalida_sem_rodar(fakes):
    """KM2: projeto e cópia coletam números diferentes: rodada INVÁLIDA, sem m0 e sem mutações."""
    f = fakes(coleta_copia=(2, 0))
    assert cm.main(ARGS) == 2
    assert f.vistos == []
    md = (f.raiz / "docs" / "entregas" / "t1" / "c.md").read_text(encoding="utf-8")
    assert "coleta diverge: projeto 3, cópia 2" in md and "Coletados (selecionados, deselecionados): projeto (3, 0)" in md


def test_km2_main_coleta_com_deselecionados_invalida(fakes):
    f = fakes(coleta_projeto=(1, 2), coleta_copia=(1, 2))
    assert cm.main(ARGS) == 2
    assert f.vistos == []


def test_km2_main_esperado_diferente_invalida(fakes):
    f = fakes()
    assert cm.main(ARGS + ["--esperado-coletados", "4"]) == 2
    assert f.vistos == []


def test_km2_main_m0_executa_menos_que_o_coletado_invalida(fakes):
    """KM2: o m0 passa, mas executa 2 dos 3 coletados: rodada INVÁLIDA, nenhuma mutação roda."""
    f = fakes(m0_saida="2 passed in 0.10s\n")
    assert cm.main(ARGS) == 2
    assert len(f.vistos) == 1


def test_km2_main_m0_com_deselected_invalida(fakes):
    f = fakes(m0_saida="3 passed, 1 deselected in 0.10s\n")
    assert cm.main(ARGS) == 2
    assert len(f.vistos) == 1


def test_km2_main_valida_registra_a_coleta_e_a_contagem(fakes):
    f = fakes()
    assert cm.main(ARGS + ["--esperado-coletados", "3"]) == 0
    assert f.coletas == ["projeto", "copia"]
    md = (f.raiz / "docs" / "entregas" / "t1" / "c.md").read_text(encoding="utf-8")
    assert "projeto (3, 0), cópia (3, 0), esperado 3." in md
    assert "Mutações: DETECTADAS 1, PASSOU 0, INVÁLIDAS 0, ERRO 0" in md


def test_km2_main_mutante_so_com_error_e_invalido_e_nao_morto(fakes, monkeypatch):
    """KM2 (item 2): um mutante que só produz "error" é INVÁLIDO (rc 2 na rodada), nunca contado como morto."""
    f = fakes()
    original = f.rodar_testes

    def rodar(copia, testes):
        codigo, saida = original(copia, testes)
        if (copia / ALVO).read_bytes() != ORIGINAL:
            return 1, "ERROR tests/test_alvo.py::test_f - setup\n1 error, 2 passed in 0.10s\n"
        return codigo, saida

    monkeypatch.setattr(cm, "_rodar_testes", rodar)
    assert cm.main(ARGS) == 2
    md = (f.raiz / "docs" / "entregas" / "t1" / "c.md").read_text(encoding="utf-8")
    assert "Mutações: DETECTADAS 0, PASSOU 0, INVÁLIDAS 1, ERRO 0" in md
