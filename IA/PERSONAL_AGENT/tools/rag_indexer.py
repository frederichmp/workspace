"""Atalho de execução direta para src/tools/rag_indexer.py."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    alvo = Path(__file__).resolve().parent.parent / "src" / "tools" / "rag_indexer.py"
    runpy.run_path(str(alvo), run_name="__main__")
