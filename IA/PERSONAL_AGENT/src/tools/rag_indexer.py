"""
Módulo de Indexação RAG Local (Retrieval-Augmented Generation) para Scripts Oracle DBA.
Lê todos os arquivos .sql e .txt do repositório de scripts homologados (./MeusScripts e SCRIPT STARTUP GIT/oracle),
quebra em chunks de 1000 caracteres (overlap 200), gera embeddings locais (all-MiniLM-L6-v2)
e persiste no banco vetorial ChromaDB (./chroma_db).
"""
import shutil
import warnings
from pathlib import Path
from typing import List

warnings.filterwarnings("ignore")

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Caminhos base do projeto e do repositório de scripts Oracle do Workspace
SRC_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SRC_DIR.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent.parent

MEUS_SCRIPTS_DIR = PROJECT_ROOT / "MeusScripts"
ORACLE_WORKSPACE_SCRIPTS_DIR = WORKSPACE_ROOT / "SCRIPT STARTUP GIT" / "oracle"
CHROMA_DB_DIR = PROJECT_ROOT / "chroma_db"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def sincronizar_scripts_oracle() -> Path:
    """
    Garante que a pasta ./MeusScripts exista e sincroniza os scripts .sql e .txt
    do diretório 'SCRIPT STARTUP GIT/oracle' do Workspace para dentro de ./MeusScripts.
    """
    MEUS_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    if ORACLE_WORKSPACE_SCRIPTS_DIR.exists():
        contador = 0
        for ext in ("*.sql", "*.txt", "*.md"):
            for arquivo in ORACLE_WORKSPACE_SCRIPTS_DIR.rglob(ext):
                rel_path = arquivo.relative_to(ORACLE_WORKSPACE_SCRIPTS_DIR)
                destino = MEUS_SCRIPTS_DIR / rel_path
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(arquivo, destino)
                contador += 1
        print(
            f"[RAG Indexer]: {contador} arquivos sincronizados de "
            f"'{ORACLE_WORKSPACE_SCRIPTS_DIR}' para '{MEUS_SCRIPTS_DIR}'."
        )
    return MEUS_SCRIPTS_DIR


def indexar_base_conhecimento(
    pasta_scripts: str | Path = MEUS_SCRIPTS_DIR,
    pasta_chroma: str | Path = CHROMA_DB_DIR,
) -> int:
    """
    Lê todos os arquivos .sql e .txt de ./MeusScripts usando DirectoryLoader + TextLoader,
    divide em chunks de 1000 caracteres (overlap 200) e persiste os vetores no ChromaDB local.
    Retorna o total de chunks indexados.
    """
    pasta_alvo = Path(pasta_scripts)
    if not pasta_alvo.exists() or not any(pasta_alvo.rglob("*.*")):
        sincronizar_scripts_oracle()

    documentos = []
    # Carrega arquivos .sql e .txt com detecção automática de encoding (UTF-8 / Latin-1)
    for padrao in ("**/*.sql", "**/*.txt"):
        loader = DirectoryLoader(
            str(pasta_alvo),
            glob=padrao,
            loader_cls=TextLoader,
            loader_kwargs={"autodetect_encoding": True},
            show_progress=False,
            use_multithreading=True,
        )
        documentos.extend(loader.load())

    if not documentos:
        print(f"[RAG Indexer]: Nenhum arquivo .sql ou .txt encontrado em '{pasta_alvo}'.")
        return 0

    print(f"[RAG Indexer]: {len(documentos)} arquivos carregados. Gerando chunks...")

    # Quebra os arquivos em chunks de 1000 caracteres com 200 de overlap
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n-- ====", "\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(documentos)

    print(
        f"[RAG Indexer]: Inicializando modelo de embeddings '{EMBEDDING_MODEL_NAME}'..."
    )
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

    # Limpa índice anterior caso exista para evitar duplicação ao reindexar
    caminho_chroma = Path(pasta_chroma)
    if caminho_chroma.exists():
        shutil.rmtree(caminho_chroma)

    print(f"[RAG Indexer]: Gravando {len(chunks)} chunks em '{caminho_chroma}'...")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(caminho_chroma),
    )

    return len(chunks)


if __name__ == "__main__":
    print("=== Iniciando Indexação da Base de Conhecimento DBA (RAG Local) ===")
    sincronizar_scripts_oracle()
    total_chunks = indexar_base_conhecimento()
    print(f"\n[Concluído]: {total_chunks} chunks salvos com sucesso em '{CHROMA_DB_DIR}'!")
