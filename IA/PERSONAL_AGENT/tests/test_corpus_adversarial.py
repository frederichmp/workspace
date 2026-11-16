"""
Teste Parametrizado do Corpus Adversarial (A1 a A31).
Verifica a conformidade do tokenizador e validador sintático SEM conexão com o banco.
"""

import json
from pathlib import Path
import pytest

from src.tools.executor import tokenizar_e_validar_sql

CORPUS_DIR = Path(__file__).resolve().parent / "corpus_adversarial"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"

with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
    corpus_manifest = json.load(f)

corpus_params = [
    (
        data["id"],
        fname,
        data["tipo_declarado"],
        data["expected_status"],
        data["expected_tipo"],
    )
    for fname, data in corpus_manifest.items()
]


@pytest.mark.parametrize(
    "case_id,filename,tipo_declarado,expected_status,expected_tipo",
    corpus_params,
    ids=[f"{c[0]}_{c[1]}" for c in corpus_params],
)
def test_corpus_adversarial_tokenizacao(
    case_id, filename, tipo_declarado, expected_status, expected_tipo
):
    """Valida cada caso do corpus adversarial sem conexão."""
    file_path = CORPUS_DIR / filename
    sql_content = file_path.read_text(encoding="utf-8")

    valido, cod_motivo, msg_erro, sql_exec, tipo_detectado = tokenizar_e_validar_sql(sql_content)

    if not valido:
        status_obtido = cod_motivo
        tipo_obtido = None
    elif tipo_declarado != tipo_detectado:
        status_obtido = "TIPO_DIVERGENTE"
        tipo_obtido = None
    else:
        status_obtido = "VALID"
        tipo_obtido = tipo_detectado

    assert status_obtido == expected_status, (
        f"Falha no caso {case_id} ({filename}): "
        f"esperado status={expected_status}, obtido status={status_obtido} (msg: {msg_erro})"
    )
    if expected_status == "VALID":
        assert tipo_obtido == expected_tipo, (
            f"Falha no caso {case_id} ({filename}): "
            f"esperado tipo={expected_tipo}, obtido tipo={tipo_obtido}"
        )
