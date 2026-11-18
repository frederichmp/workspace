"""Guarda de leitura do .env real para os testes (isolamento-env, fase 4, passo 1; Achados 2 e 5).

Não é coletado pelo pytest (nome com "_" inicial, sem "test_"). Usado pelas fixtures de fluxo (CLI e Web)
e pelo script do harness de `test_carga_env_entrada.py`, que roda em subprocesso.

Contrato de `instalar(setattr_fn, real, ficticio=None)`:
- `builtins.open` e `io.open`: abertura do `real` com `ficticio` -> abre o `ficticio` e registra em
  `aberturas_redirecionadas`; sem `ficticio` -> registra em `leituras_env_reais` e levanta
  `LeituraEnvRealBloqueada`.
- `os.stat`: caminho `real` com `ficticio` -> stat do `ficticio` (registrado como "stat"); sem `ficticio`
  delega (stat não lê conteúdo).
- `dotenv.main.DotEnv.__init__`: bloqueia o caminho `real` e o `stream` cujo `.name` seja o `real`.

Nada aqui lê ou imprime conteúdo de arquivo nem valor de variável: os registros guardam só caminho e tipo.
"""
import builtins
import io
import os
import threading

import dotenv.main

# Originais capturados no import. Toda comparação usa estes (o wrapper de os.stat entraria em recursão).
_OPEN_ORIGINAL = builtins.open
_IO_OPEN_ORIGINAL = io.open
_STAT_ORIGINAL = os.stat
_DOTENV_INIT_ORIGINAL = dotenv.main.DotEnv.__init__

_estado_thread = threading.local()  # evita recursão: realpath/stat chamados de dentro da comparação


class LeituraEnvRealBloqueada(BaseException):
    """BaseException de propósito: o `except Exception` da carga em app.py/src/main.py não a engole."""


class Registro:
    """Listas de eventos; cada item é um dict com só `caminho` (como recebido, em texto) e `tipo`."""

    def __init__(self):
        self.leituras_env_reais = []
        self.aberturas_redirecionadas = []
        self.cargas = []  # chamadas a load_dotenv registradas pelos stubs das fixtures
        self.valores = []  # chamadas a dotenv_values registradas pelos stubs das fixtures


# Para o teste abrir/consultar um arquivo próprio sem passar pelo guarda.
open_original = _OPEN_ORIGINAL
stat_original = _STAT_ORIGINAL


def _como_texto(alvo):
    """str/bytes/PathLike -> str; int (fd), bool, None e vazio -> None."""
    if alvo is None or isinstance(alvo, int):
        return None
    try:
        texto = os.fsdecode(os.fspath(alvo))
    except TypeError:
        return None
    return texto or None


def _sem_prefixo_estendido(texto):
    if texto[:8].upper() == "\\\\?\\UNC\\":
        return "\\\\" + texto[8:]
    if texto[:4] in ("\\\\?\\", "\\\\.\\"):
        return texto[4:]
    return texto


_NAO_EXISTE = object()
_ERRO = object()


def _stat_ou_marca(caminho):
    try:
        return _STAT_ORIGINAL(caminho)
    except LeituraEnvRealBloqueada:
        raise
    except (FileNotFoundError, NotADirectoryError):
        return _NAO_EXISTE
    except (OSError, ValueError):
        return _ERRO


def _chave_de_caminho(texto):
    return os.path.normcase(os.path.realpath(_sem_prefixo_estendido(texto)))


def mesmo_arquivo(alvo, real):
    """True se `alvo` (str, bytes, PathLike) designa o mesmo arquivo que `real`; fd int e None -> False."""
    texto_alvo = _como_texto(alvo)
    texto_real = _como_texto(real)
    if texto_alvo is None or texto_real is None:
        return False
    anterior = getattr(_estado_thread, "dentro", False)
    _estado_thread.dentro = True
    try:
        st_alvo = _stat_ou_marca(_sem_prefixo_estendido(texto_alvo))
        st_real = _stat_ou_marca(_sem_prefixo_estendido(texto_real))
        if st_alvo not in (_NAO_EXISTE, _ERRO) and st_real not in (_NAO_EXISTE, _ERRO):
            return os.path.samestat(st_alvo, st_real)
        # Sem stat dos dois lados (inexistente ou erro, ex.: PermissionError com o .env travado pelo OneDrive):
        # compara por caminho. Erro de stat nunca vira "não é o mesmo" direto, senão o open do real passaria.
        try:
            return _chave_de_caminho(texto_alvo) == _chave_de_caminho(texto_real)
        except (OSError, ValueError):
            return False
    finally:
        _estado_thread.dentro = anterior


def _e_o_real(alvo, real):
    if getattr(_estado_thread, "dentro", False):
        return False
    return mesmo_arquivo(alvo, real)


def instalar(setattr_fn, real, ficticio=None):
    """Instala os wrappers via `setattr_fn(obj, nome, valor)` e devolve o `Registro`."""
    registro = Registro()
    real = os.fspath(real)
    ficticio = None if ficticio is None else os.fspath(ficticio)
    open_anterior = builtins.open
    io_open_anterior = io.open
    stat_anterior = os.stat
    init_anterior = dotenv.main.DotEnv.__init__

    def _evento(alvo, tipo):
        return {"caminho": _como_texto(alvo), "tipo": tipo}

    def _fazer_open(anterior, tipo):
        def _open(file, *args, **kwargs):
            if _e_o_real(file, real):
                if ficticio is None:
                    registro.leituras_env_reais.append(_evento(file, tipo))
                    raise LeituraEnvRealBloqueada(f"{tipo} do .env real bloqueado pelo guarda do teste")
                registro.aberturas_redirecionadas.append(_evento(file, tipo))
                return anterior(ficticio, *args, **kwargs)
            return anterior(file, *args, **kwargs)

        return _open

    def _stat(path, *args, **kwargs):
        if ficticio is not None and kwargs.get("dir_fd") is None and _e_o_real(path, real):
            registro.aberturas_redirecionadas.append(_evento(path, "stat"))
            return stat_anterior(ficticio, *args, **kwargs)
        return stat_anterior(path, *args, **kwargs)

    def _init(self, *args, **kwargs):
        caminho = kwargs["dotenv_path"] if "dotenv_path" in kwargs else (args[0] if args else None)
        stream = kwargs["stream"] if "stream" in kwargs else (args[1] if len(args) > 1 else None)
        if _e_o_real(caminho, real):
            registro.leituras_env_reais.append(_evento(caminho, "DotEnv"))
            raise LeituraEnvRealBloqueada("DotEnv do .env real bloqueado pelo guarda do teste")
        nome_stream = getattr(stream, "name", None)
        if _e_o_real(nome_stream, real):
            registro.leituras_env_reais.append(_evento(nome_stream, "DotEnv(stream)"))
            raise LeituraEnvRealBloqueada("DotEnv(stream) do .env real bloqueado pelo guarda do teste")
        return init_anterior(self, *args, **kwargs)

    setattr_fn(builtins, "open", _fazer_open(open_anterior, "open"))
    setattr_fn(io, "open", _fazer_open(io_open_anterior, "io.open"))
    setattr_fn(os, "stat", _stat)
    setattr_fn(dotenv.main.DotEnv, "__init__", _init)
    return registro
