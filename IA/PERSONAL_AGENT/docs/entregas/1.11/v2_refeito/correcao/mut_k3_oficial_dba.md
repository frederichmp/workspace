# Controle de mutação `mut_k3_oficial_dba`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/fakes_oracle.py`, `docs/entregas/1.11/item6/ops_kill.sql`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 190 passed, 6 skipped, 13 warnings in 10.57s | OK |
| M_RHS_SWAP_PROG_MACH |                     p_program_esperado    => :p_program_esperado,\n … | 1 substituição | 15 failed, 175 passed, 6 skipped, 13 warnings in 10.77s \| caíram: te… | DETECTADA |
| M_RHS_SWAP_SID_SERIAL |                     p_sid                 => :p_sid,\n              … | 1 substituição | 15 failed, 175 passed, 6 skipped, 13 warnings in 10.90s \| caíram: te… | DETECTADA |
| M_STATUS_VAR_SIZE_8 | cursor.var(oracledb.DB_TYPE_VARCHAR, size=128) -> cursor.var(oracledb… | 1 substituição | 43 failed, 147 passed, 6 skipped, 13 warnings in 11.05s \| caíram: te… | DETECTADA |
| M_LOGON_COMENTARIO_NO_SELECT |                    type,\n                   logon_time\n          … | 1 substituição | 47 failed, 143 passed, 6 skipped, 13 warnings in 10.80s \| caíram: te… | DETECTADA |
| M_EXEC_INICIADO_ANTES_VAR |         status_var = cursor.var(oracledb.DB_TYPE_VARCHAR, size=128)\… | 1 substituição | 4 failed, 186 passed, 6 skipped, 13 warnings in 10.41s \| caíram: tes… | DETECTADA |
| M_EXEC_KILL_GET_DEFAULT | {c: alvo_reconsulta[c] for c in CAMPOS_IDENTIDADE_ESPERADA if c in al… | 1 substituição | 3 failed, 187 passed, 6 skipped, 13 warnings in 10.27s \| caíram: tes… | DETECTADA |
| M_FALLBACK_V1_NO_NAO_ENCONTRADO |         status_banco = str(status_var.getvalue() or "").strip()\n ->… | 1 substituição | 2 failed, 188 passed, 6 skipped, 13 warnings in 10.07s \| caíram: tes… | DETECTADA |
| M_LIMITE_GE_128 | len(valor) > LIMITE_TEXTO_IDENTIDADE -> len(valor) >= LIMITE_TEXTO_ID… | 1 substituição | 6 failed, 184 passed, 6 skipped, 13 warnings in 10.09s \| caíram: tes… | DETECTADA |
| X_REGEX_ID_0_9A_Z | _REGEX_ID_INTERVENCAO = re.compile(r"[0-9a-f]{32}") -> _REGEX_ID_INTE… | 1 substituição | 1 failed, 189 passed, 6 skipped, 13 warnings in 10.01s \| caíram: tes… | DETECTADA |
| X_SERIAL_FORA_ROW2 | dados_alvo["serial#"] = row[2] -> dados_alvo["serial#"] = row[1] | 1 substituição | 2 failed, 188 passed, 6 skipped, 13 warnings in 9.98s \| caíram: test… | DETECTADA |
| X_SELECT_SID_SERIAL_TROCADOS |         query = """\n            SELECT inst_id,\n                 … | 1 substituição | 2 failed, 188 passed, 6 skipped, 13 warnings in 9.92s \| caíram: test… | DETECTADA |
| m27_limite_local_em_bytes_utf8 | len(valor) > LIMITE_TEXTO_IDENTIDADE -> len(valor.encode("utf-8")) > … | 1 substituição | 3 failed, 187 passed, 6 skipped, 13 warnings in 10.12s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
