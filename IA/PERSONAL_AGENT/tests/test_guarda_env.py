"""Testes do guarda de leitura do .env (tests/_guarda_env.py; isolamento-env, fase 4, passo 1).

Só arquivos de tmp_path fazem o papel de ".env real": o .env do repositório nunca é aberto aqui.
Nenhum teste imprime conteúdo de arquivo nem valor de variável.
"""
import builtins
import io
import os

import dotenv.main
import pytest

from tests import _guarda_env
from tests._guarda_env import LeituraEnvRealBloqueada, instalar, mesmo_arquivo, open_original

CONTEUDO_REAL = "CHAVE_REAL_FICTICIA=1234567890\n"
CONTEUDO_FICTICIO = "F=1\n"


@pytest.fixture
def arquivos(tmp_path):
    real = tmp_path / "arquivo_real_com_nome_longo.env"
    real.write_bytes(CONTEUDO_REAL.encode("utf-8"))
    ficticio = tmp_path / "ficticio.env"
    ficticio.write_bytes(CONTEUDO_FICTICIO.encode("utf-8"))
    outro = tmp_path / "outro_arquivo_qualquer.env"
    outro.write_bytes("O=2\n".encode("utf-8"))
    return real, ficticio, outro


# ---------------------------------------------------------------------------
# mesmo_arquivo
# ---------------------------------------------------------------------------

def test_mesmo_arquivo_str_path_e_bytes(arquivos):
    real, _, outro = arquivos
    assert mesmo_arquivo(str(real), real)
    assert mesmo_arquivo(real, str(real))
    assert mesmo_arquivo(os.fsencode(real), real)
    assert mesmo_arquivo(real, os.fsencode(real))
    assert not mesmo_arquivo(outro, real)


def test_mesmo_arquivo_ignora_fd_e_none(arquivos):
    real, _, _ = arquivos
    assert mesmo_arquivo(None, real) is False
    assert mesmo_arquivo(3, real) is False
    assert mesmo_arquivo(real, None) is False
    assert mesmo_arquivo("", real) is False


def test_mesmo_arquivo_prefixo_estendido(arquivos):
    real, _, outro = arquivos
    assert mesmo_arquivo("\\\\?\\" + str(real), real)
    assert mesmo_arquivo(os.fsencode("\\\\?\\" + str(real)), real)
    assert not mesmo_arquivo("\\\\?\\" + str(outro), real)


def test_mesmo_arquivo_caixa_diferente(arquivos):
    real, _, _ = arquivos
    if os.name == "nt":  # no Windows a caixa não distingue arquivos (normcase/samestat)
        assert mesmo_arquivo(str(real).upper(), real)
        assert mesmo_arquivo(str(real).lower(), real)


def test_mesmo_arquivo_nome_curto_8_3(arquivos):
    real, _, outro = arquivos
    try:
        import ctypes

        obter_curto = ctypes.windll.kernel32.GetShortPathNameW
    except (AttributeError, ImportError, OSError):
        pytest.skip("GetShortPathNameW indisponível (sistema sem Windows)")
    obter_curto.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    obter_curto.restype = ctypes.c_uint
    buf = ctypes.create_unicode_buffer(1024)
    n = obter_curto(str(real), buf, len(buf))
    curto = buf.value if 0 < n < len(buf) else ""
    if not curto or curto.lower() == str(real).lower():
        pytest.skip("o sistema não gerou nome curto 8.3 para o arquivo de teste")
    assert mesmo_arquivo(curto, real)
    assert mesmo_arquivo(os.fsencode(curto), real)
    assert mesmo_arquivo("\\\\?\\" + curto, real)
    assert not mesmo_arquivo(curto, outro)


def test_mesmo_arquivo_caminho_relativo(arquivos, monkeypatch):
    real, _, outro = arquivos
    monkeypatch.chdir(real.parent)
    assert mesmo_arquivo(real.name, real)
    assert mesmo_arquivo(os.path.join(".", real.name), real)
    assert not mesmo_arquivo(outro.name, real)


def test_mesmo_arquivo_inexistentes_comparam_por_caminho(tmp_path):
    real = tmp_path / "nao_existe_real.env"
    outro = tmp_path / "nao_existe_outro.env"
    assert not real.exists() and not outro.exists()
    assert mesmo_arquivo(str(real), real)
    assert mesmo_arquivo("\\\\?\\" + str(real), real)
    assert mesmo_arquivo(os.fsencode(real), real)
    assert not mesmo_arquivo(outro, real)


def test_mesmo_arquivo_erro_de_stat_compara_por_caminho(arquivos, monkeypatch):
    """Stat do real com PermissionError (ex.: .env travado pelo OneDrive): o guarda não pode abrir mão."""
    real, ficticio, outro = arquivos
    stat_verdadeiro = _guarda_env._STAT_ORIGINAL

    def _stat_travado(caminho, *a, **k):
        if os.path.basename(os.fsdecode(os.fspath(caminho))) == real.name:
            raise PermissionError(13, "travado (simulado)")
        return stat_verdadeiro(caminho, *a, **k)

    monkeypatch.setattr(_guarda_env, "_STAT_ORIGINAL", _stat_travado)
    assert mesmo_arquivo(str(real), real)
    assert mesmo_arquivo("\\\\?\\" + str(real), real)
    assert not mesmo_arquivo(outro, real)

    registro = instalar(monkeypatch.setattr, real, ficticio)
    with open(real, encoding="utf-8") as f:
        assert f.read() == CONTEUDO_FICTICIO
    assert [a["tipo"] for a in registro.aberturas_redirecionadas] == ["open"]


# ---------------------------------------------------------------------------
# open / io.open / os.stat
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tipo", ["open", "io.open"])
def test_open_do_real_com_ficticio_le_o_ficticio(arquivos, monkeypatch, tipo):
    real, ficticio, _ = arquivos
    registro = instalar(monkeypatch.setattr, real, ficticio)
    aberta = io.open if tipo == "io.open" else builtins.open  # lidos DEPOIS de instalar (são os wrappers)
    with aberta(real, encoding="utf-8") as f:
        assert f.read() == CONTEUDO_FICTICIO
    assert registro.aberturas_redirecionadas == [{"caminho": str(real), "tipo": tipo}]
    assert registro.leituras_env_reais == []


def test_open_do_real_com_ficticio_aceita_bytes_e_8_3_e_modo_binario(arquivos, monkeypatch):
    real, ficticio, outro = arquivos
    registro = instalar(monkeypatch.setattr, real, ficticio)
    with open(os.fsencode(real), "rb") as f:
        assert f.read() == CONTEUDO_FICTICIO.encode("utf-8")
    with open("\\\\?\\" + str(real), encoding="utf-8") as f:
        assert f.read() == CONTEUDO_FICTICIO
    assert len(registro.aberturas_redirecionadas) == 2
    # outro arquivo: abre o próprio, sem registro novo
    with open(outro, encoding="utf-8") as f:
        assert f.read() == "O=2\n"
    assert len(registro.aberturas_redirecionadas) == 2


@pytest.mark.parametrize("tipo", ["open", "io.open"])
def test_open_do_real_sem_ficticio_bloqueia_e_nao_e_engolido(arquivos, monkeypatch, tipo):
    real, _, outro = arquivos
    registro = instalar(monkeypatch.setattr, real)
    aberta = io.open if tipo == "io.open" else builtins.open  # lidos DEPOIS de instalar (são os wrappers)
    with pytest.raises(LeituraEnvRealBloqueada):
        try:
            aberta(real, encoding="utf-8")
        except Exception:  # o except da carga de produção não pode engolir o bloqueio
            pytest.fail("LeituraEnvRealBloqueada foi capturada por 'except Exception'")
    assert registro.leituras_env_reais == [{"caminho": str(real), "tipo": tipo}]
    assert registro.aberturas_redirecionadas == []
    with aberta(outro, encoding="utf-8") as f:  # outro arquivo segue funcionando
        assert f.read() == "O=2\n"
    assert len(registro.leituras_env_reais) == 1


def test_open_com_fd_inteiro_passa_intacto(arquivos, monkeypatch):
    real, _, outro = arquivos
    registro = instalar(monkeypatch.setattr, real)
    fd = os.open(outro, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        with open(fd, "rb", closefd=False) as f:
            assert f.read() == b"O=2\n"
    finally:
        os.close(fd)
    assert registro.leituras_env_reais == [] and registro.aberturas_redirecionadas == []


def test_stat_do_real_com_ficticio_devolve_o_stat_do_ficticio(arquivos, monkeypatch):
    real, ficticio, outro = arquivos
    assert len(CONTEUDO_REAL) != len(CONTEUDO_FICTICIO)
    registro = instalar(monkeypatch.setattr, real, ficticio)
    assert os.stat(real).st_size == len(CONTEUDO_FICTICIO)
    assert os.stat(os.fsencode(real)).st_size == len(CONTEUDO_FICTICIO)
    assert os.stat(real, follow_symlinks=False).st_size == len(CONTEUDO_FICTICIO)
    assert os.path.samestat(os.stat(real), os.stat(ficticio))
    assert [e["tipo"] for e in registro.aberturas_redirecionadas] == ["stat"] * 4
    assert os.stat(outro).st_size == len("O=2\n")  # outro arquivo: stat verdadeiro
    assert len(registro.aberturas_redirecionadas) == 4
    fd = os.open(outro, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        assert os.stat(fd).st_size == len("O=2\n")  # fd inteiro passa intacto
    finally:
        os.close(fd)
    assert registro.leituras_env_reais == []


def test_stat_do_real_sem_ficticio_delega(arquivos, monkeypatch):
    real, _, _ = arquivos
    registro = instalar(monkeypatch.setattr, real)
    assert os.stat(real).st_size == len(CONTEUDO_REAL)  # stat não lê conteúdo
    assert registro.leituras_env_reais == [] and registro.aberturas_redirecionadas == []


# ---------------------------------------------------------------------------
# dotenv.main.DotEnv.__init__
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("forma", ["str", "bytes", "prefixo_estendido", "path", "kw"])
def test_dotenv_com_caminho_do_real_e_bloqueado(arquivos, monkeypatch, forma):
    real, ficticio, _ = arquivos
    registro = instalar(monkeypatch.setattr, real, ficticio)
    argumento = {
        "str": lambda: str(real),
        "bytes": lambda: os.fsencode(real),
        "prefixo_estendido": lambda: "\\\\?\\" + str(real),
        "path": lambda: real,
        "kw": lambda: real,
    }[forma]()
    with pytest.raises(LeituraEnvRealBloqueada):
        if forma == "kw":
            dotenv.main.DotEnv(dotenv_path=argumento)
        else:
            dotenv.main.DotEnv(argumento)
    assert len(registro.leituras_env_reais) == 1
    assert registro.leituras_env_reais[0]["tipo"] == "DotEnv"


def test_dotenv_com_stream_nomeado_do_real_e_bloqueado(arquivos, monkeypatch):
    real, ficticio, _ = arquivos
    registro = instalar(monkeypatch.setattr, real, ficticio)
    stream = open_original(real, encoding="utf-8")  # abertura original, fora do guarda (arquivo de tmp_path)
    try:
        with pytest.raises(LeituraEnvRealBloqueada):
            dotenv.main.DotEnv(None, stream=stream)
        with pytest.raises(LeituraEnvRealBloqueada):
            dotenv.main.DotEnv(dotenv_path=None, stream=stream)
    finally:
        stream.close()
    assert [e["tipo"] for e in registro.leituras_env_reais] == ["DotEnv(stream)", "DotEnv(stream)"]


def test_dotenv_com_stream_sem_nome_ou_de_outro_arquivo_passa(arquivos, monkeypatch):
    real, ficticio, _ = arquivos
    registro = instalar(monkeypatch.setattr, real, ficticio)
    assert dotenv.main.DotEnv(None, stream=io.StringIO("A=1")).dict() == {"A": "1"}
    with open_original(ficticio, encoding="utf-8") as stream:
        assert dotenv.main.DotEnv(None, stream=stream).dict() == {"F": "1"}
    # o caminho do fictício também passa
    assert dotenv.main.DotEnv(str(ficticio)).dict() == {"F": "1"}
    assert registro.leituras_env_reais == []


def test_dotenv_stream_aberto_pelo_open_guardado_le_o_ficticio(arquivos, monkeypatch):
    """Caminho da produção do passo 2: open(real) redireciona e DotEnv(stream=...) lê o fictício, sem bloqueio."""
    real, ficticio, _ = arquivos
    registro = instalar(monkeypatch.setattr, real, ficticio)
    with open(real, encoding="utf-8") as stream:
        assert dotenv.main.DotEnv(None, stream=stream).dict() == {"F": "1"}
    assert registro.leituras_env_reais == []
    assert [e["tipo"] for e in registro.aberturas_redirecionadas] == ["open"]


# ---------------------------------------------------------------------------
# A exceção não é Exception
# ---------------------------------------------------------------------------

def test_leitura_bloqueada_nao_e_subclasse_de_exception():
    assert issubclass(LeituraEnvRealBloqueada, Exception) is False
    assert issubclass(LeituraEnvRealBloqueada, BaseException)
    capturada = False
    with pytest.raises(LeituraEnvRealBloqueada):
        try:
            raise LeituraEnvRealBloqueada("x")
        except Exception:
            capturada = True
    assert capturada is False


def test_originais_capturados_no_import_nao_sao_os_wrappers(arquivos, monkeypatch):
    real, ficticio, _ = arquivos
    antes = (builtins.open, io.open, os.stat, dotenv.main.DotEnv.__init__)
    instalar(monkeypatch.setattr, real, ficticio)
    depois = (builtins.open, io.open, os.stat, dotenv.main.DotEnv.__init__)
    assert all(a is not d for a, d in zip(antes, depois))
    assert _guarda_env.open_original is not builtins.open
    assert _guarda_env.stat_original is not os.stat
    monkeypatch.undo()
    assert (builtins.open, io.open, os.stat, dotenv.main.DotEnv.__init__) == antes
