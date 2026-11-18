"""Isolamento do .env, fase 4, Achado 4: o Chroma de rag_search não lê cwd/.env fora da carga-env.

Roda com o diretório corrente num tmp_path que tem um .env fictício (só sentinela), importa o chromadb
ali (as 7 leituras do import, residual I3, caem no fictício) e conta os DotEnv construídos com caminho
durante `_obter_vectorstore()`. Embeddings e cliente do Chroma são falsos: sem modelo, sem banco, sem rede.
O guarda de tests/_guarda_env.py recusa qualquer leitura do .env real.
"""
from pathlib import Path

import dotenv.main
import pytest

from src.tools import rag_search
from tests._guarda_env import instalar

RAIZ = Path(__file__).resolve().parent.parent


class _ClienteFalso:
    def __init__(self, settings):
        self.settings = settings

    def get_or_create_collection(self, **kwargs):
        return object()


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("SENTINELA_RAG_FASE4=1\n", encoding="utf-8")
    registro = instalar(monkeypatch.setattr, RAIZ / ".env")  # sem fictício: leitura do real é recusada
    import chromadb
    import chromadb.config  # noqa: F401  (import aqui, com cwd no tmp_path)

    clientes = []

    def _cliente(settings):
        cliente = _ClienteFalso(settings)
        clientes.append(cliente)
        return cliente

    monkeypatch.setattr(chromadb, "Client", _cliente)
    monkeypatch.setattr(rag_search, "HuggingFaceEmbeddings", lambda **k: object())
    monkeypatch.setattr(rag_search, "CHROMA_DB_DIR", tmp_path / "chroma_db")
    monkeypatch.setattr(rag_search, "_EMBEDDINGS_INSTANCE", None)
    monkeypatch.setattr(rag_search, "_VECTORSTORE_INSTANCE", None)

    leituras = []
    init_vigente = dotenv.main.DotEnv.__init__

    def _contar(self, *args, **kwargs):
        caminho = kwargs["dotenv_path"] if "dotenv_path" in kwargs else (args[0] if args else None)
        if caminho is not None:
            leituras.append(str(caminho))
        return init_vigente(self, *args, **kwargs)

    monkeypatch.setattr(dotenv.main.DotEnv, "__init__", _contar)
    yield leituras, clientes
    assert registro.leituras_env_reais == []


def test_contador_ve_o_env_do_diretorio_corrente(ambiente):
    """Controle do próprio teste: um Settings() comum lê o .env do diretório corrente e o contador registra."""
    import chromadb.config

    leituras, _ = ambiente
    chromadb.config.Settings()
    assert leituras, "o contador não registrou a leitura de cwd/.env por um Settings() comum"


def test_obter_vectorstore_nao_le_env(ambiente):
    """Achado 4: `_obter_vectorstore()` constrói o Chroma sem ler .env (Settings com `_env_file=None`)."""
    leituras, clientes = ambiente
    rag_search._obter_vectorstore()
    assert len(clientes) == 1, "o cliente do Chroma deveria ter sido criado uma vez"
    assert Path(clientes[0].settings.persist_directory) == rag_search.CHROMA_DB_DIR
    assert leituras == [], f"DotEnv construído com caminho durante _obter_vectorstore: {leituras}"
