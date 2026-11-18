"""
Módulo de Busca Semântica RAG Local (Retrieval-Augmented Generation) para o Agente Coordenador.
Consulta o banco vetorial local (./chroma_db) com embeddings HuggingFace (all-MiniLM-L6-v2)
para recuperar scripts SQL homologados e manuais do DBA.
"""
import json
import warnings
from pathlib import Path
from typing import Any, Dict, List

warnings.filterwarnings("ignore")

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

SRC_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SRC_DIR.parent
CHROMA_DB_DIR = PROJECT_ROOT / "chroma_db"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Cache em memória para evitar recarregar o modelo de embeddings a cada chamada do Agente
_EMBEDDINGS_INSTANCE = None
_VECTORSTORE_INSTANCE = None


def _obter_vectorstore() -> Chroma:
    """Inicializa e mantém em cache a conexão com o ChromaDB local e o modelo de embeddings."""
    global _EMBEDDINGS_INSTANCE, _VECTORSTORE_INSTANCE
    if _EMBEDDINGS_INSTANCE is None:
        _EMBEDDINGS_INSTANCE = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    if _VECTORSTORE_INSTANCE is None:
        # Isolamento do .env (fase 4, Achado 4): sem client_settings o Chroma cria Settings() que lê cwd/.env
        # fora da carga-env. O argumento do pydantic-settings é `_env_file` (com sublinhado); a forma sem sublinhado
        # seria ignorada em silêncio (model_config com extra="ignore"). Residual: o import do chromadb (na 1ª chamada)
        # ainda cria Settings() em argumentos-padrão do próprio pacote; por isso o import fica aqui, e não no topo
        # (no topo, essas leituras iriam para a subida das entradas e para a coleta dos testes).
        import chromadb.config

        _VECTORSTORE_INSTANCE = Chroma(
            persist_directory=str(CHROMA_DB_DIR),
            embedding_function=_EMBEDDINGS_INSTANCE,
            client_settings=chromadb.config.Settings(is_persistent=True, _env_file=None),
        )
    return _VECTORSTORE_INSTANCE


def buscar_script_interno(tema_ou_problema: str) -> str:
    """
    Realiza busca de similaridade semântica (Top 3) no ChromaDB local (./chroma_db)
    e retorna os trechos e caminhos dos scripts SQL homologados em formato JSON.
    """
    if not CHROMA_DB_DIR.exists():
        return json.dumps(
            {
                "status": "erro",
                "mensagem": (
                    f"Base vetorial não encontrada em '{CHROMA_DB_DIR}'. "
                    "Execute 'python src/tools/rag_indexer.py' primeiro."
                ),
            },
            ensure_ascii=False,
        )

    try:
        vectorstore = _obter_vectorstore()
        resultados = vectorstore.similarity_search_with_score(tema_ou_problema, k=3)

        scripts_encontrados = []
        arquivos_vistos = set()
        for doc, score in resultados:
            caminho_origem = doc.metadata.get("source", "desconhecido")
            try:
                nome_relativo = str(
                    Path(caminho_origem).relative_to(PROJECT_ROOT / "MeusScripts")
                )
            except ValueError:
                nome_relativo = Path(caminho_origem).name

            # Se o arquivo completo for compacto (<= 3000 caracteres), entrega o script SQL inteiro
            # para garantir que o Agente receba tanto o cabeçalho explicativo quanto a query SQL executável.
            conteudo_final = doc.page_content.strip()
            caminho_path = Path(caminho_origem)
            if caminho_path.exists() and nome_relativo not in arquivos_vistos:
                try:
                    texto_completo = caminho_path.read_text(encoding="utf-8", errors="replace").strip()
                    if len(texto_completo) <= 3000:
                        conteudo_final = texto_completo
                    else:
                        conteudo_final = texto_completo[:3000] + "\n-- ... [TRUNCADO] ..."
                except Exception:
                    pass
            arquivos_vistos.add(nome_relativo)

            scripts_encontrados.append(
                {
                    "arquivo": nome_relativo.replace("\\", "/"),
                    "score_distancia": round(float(score), 4),
                    "conteudo_sql": conteudo_final,
                }
            )

        return json.dumps(
            {
                "status": "sucesso",
                "consulta": tema_ou_problema,
                "total_encontrado": len(scripts_encontrados),
                "scripts_homologados": scripts_encontrados,
            },
            ensure_ascii=False,
        )

    except Exception as exc:
        return json.dumps(
            {
                "status": "erro",
                "consulta": tema_ou_problema,
                "mensagem": str(exc),
            },
            ensure_ascii=False,
        )


# Schema no padrão OpenAI Tool Calling para exportação ao Orquestrador
rag_tools_schema: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "buscar_script_interno",
            "description": (
                "Pesquisa na base de conhecimento local do DBA por scripts SQL homologados, "
                "manuais ou queries históricas. Use sempre que precisar de uma query complexa "
                "que você não sabe de cor."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tema_ou_problema": {
                        "type": "string",
                        "description": (
                            "O tema técnico, sintoma ou problema a ser pesquisado na base de scripts "
                            "(ex: 'bloqueio de linha lock', 'uso de tablespace', 'sessões inativas', 'rman backup')."
                        ),
                    }
                },
                "required": ["tema_ou_problema"],
            },
        },
    }
]


if __name__ == "__main__":
    print("=== Teste Isolado de Busca RAG Local (Top 3 Scripts DBA) ===")
    consulta_teste = "script para identificar bloqueios de linha e sessões bloqueadoras (locks)"
    print(f"\nPesquisando por: '{consulta_teste}'...")
    resultado_json = buscar_script_interno(consulta_teste)
    print("\n[Resultado do RAG]:")
    print(resultado_json)
