# Controle de mutação `mut_k4_oficial_init`

Alvo `src/tools/__init__.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `src/tools/__init__.py`, `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/fakes_oracle.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 225 passed, 6 skipped, 13 warnings in 47.87s | OK |
| m23a_volta_ao_all | "oracle_tools_schema", -> "oracle_tools_schema", "matar_sessao_oracle… | 1 substituição | 1 failed, 224 passed, 6 skipped, 13 warnings in 47.50s \| caíram: tes… | DETECTADA |
| m23b_volta_o_import_sem_all |     oracle_tools_schema, ->     oracle_tools_schema,\n    matar_sessa… | 1 substituição | 1 failed, 224 passed, 6 skipped, 13 warnings in 47.92s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
