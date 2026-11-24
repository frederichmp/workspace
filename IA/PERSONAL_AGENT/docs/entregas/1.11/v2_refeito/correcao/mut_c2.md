# Controle de mutação `mut_c2`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`; cópia `git archive HEAD` + `tests/fakes_oracle.py`, `src/tools/oracle_dba.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 126 passed, 6 skipped, 13 warnings in 17.81s | OK |
| M_STATUS_VAR_SIZE_8 | cursor.var(oracledb.DB_TYPE_VARCHAR, size=128) -> cursor.var(oracledb… | 1 substituição | 15 failed, 111 passed, 6 skipped, 13 warnings in 21.71s \| caíram: te… | DETECTADA |
| M_LOGON_COMENTARIO_NO_SELECT |                    type,\n                   logon_time\n          … | 1 substituição | 24 failed, 102 passed, 6 skipped, 13 warnings in 24.52s \| caíram: te… | DETECTADA |
| X_SELECT_SID_SERIAL_TROCADOS |         query = """\n            SELECT inst_id,\n                 … | 1 substituição | 2 failed, 124 passed, 6 skipped, 13 warnings in 26.16s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
