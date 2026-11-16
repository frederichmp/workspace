"""
Teste Parametrizado do Corpus Adversarial (A1 a A31).
Verifica a conformidade do tokenizador e validador sintático SEM conexão com o banco.
Inclui teste L3 de integração com executar_script() e simulação de catálogo.
"""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from src.tools.executor import executar_script, tokenizar_e_validar_sql
from src.tools.registry import ScriptRegistryEntry

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


# =============================================================================
# L3: Testes de regras do executor via executar_script() sem conexão
# =============================================================================
@pytest.mark.parametrize(
    "script_id,filename,tipo_declarado,expected_motivo",
    [
        ("a14_spool_inicio", "a14_spool_inicio.sql", "SELECT", "DIRETIVA_SQLPLUS"),
        ("a16_tipo_select_com_update", "a16_tipo_select_com_update.sql", "SELECT", "TIPO_DIVERGENTE"),
        ("a17_tipo_dml_com_create", "a17_tipo_dml_com_create.sql", "DML", "TIPO_DIVERGENTE"),
        ("a18_tipo_plsql_com_select", "a18_tipo_plsql_com_select.sql", "PLSQL", "TIPO_DIVERGENTE"),
        ("a20_syntax_error", "a20_syntax_error.sql", "SELECT", "TIPO_NAO_RECONHECIDO"),
    ],
    ids=[
        "A14_DIRETIVA_SQLPLUS",
        "A16_TIPO_DIVERGENTE",
        "A17_TIPO_DIVERGENTE",
        "A18_TIPO_DIVERGENTE",
        "A20_TIPO_NAO_RECONHECIDO",
    ],
)
def test_l3_executar_script_adversarial_sem_conexao(
    script_id, filename, tipo_declarado, expected_motivo, monkeypatch
):
    """
    L3: Valida a execução completa via executar_script (não apenas tokenizador)
    com registro de teste e arquivo real para regras do executor, garantindo
    que nenhuma conexão com o Oracle seja aberta (mock_connect.assert_not_called()).
    """
    file_path = CORPUS_DIR / filename
    raw_bytes = file_path.read_bytes()
    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

    entry = ScriptRegistryEntry(
        script_id=script_id,
        arquivo=filename,
        sha256=sha256_hash,
        tipo=tipo_declarado,
        risco="baixo",
        status="homologado",
        binds=[],
    )

    monkeypatch.setenv("SCRIPTS_DIR_PATH", str(CORPUS_DIR))
    with patch("src.tools.executor.obter_script", return_value=entry), \
         patch("oracledb.connect") as mock_conn:
        saida_str = executar_script(script_id, {})
        resultado = json.loads(saida_str)

        assert resultado["status"] == "recusado", f"Esperado status=recusado, obtido: {resultado}"
        assert resultado["motivo"] == expected_motivo, (
            f"Caso {script_id}: esperado motivo={expected_motivo}, obtido={resultado.get('motivo')} (msg: {resultado.get('mensagem')})"
        )
        mock_conn.assert_not_called()
