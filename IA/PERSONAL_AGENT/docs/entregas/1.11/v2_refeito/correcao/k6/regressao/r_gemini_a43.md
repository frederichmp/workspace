# Controle de mutação `r_gemini_a43`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 293 passed, 6 skipped, 13 warnings in 49.02s | OK |
| M_RHS_SWAP_PROG_MACH |                     p_program_esperado    => :p_program_esperado,\n … | 1 substituição | 15 failed, 278 passed, 6 skipped, 13 warnings in 48.40s \| caíram: te… | DETECTADA |
| M_RHS_SWAP_SID_SERIAL |                     p_sid                 => :p_sid,\n              … | 1 substituição | 15 failed, 278 passed, 6 skipped, 13 warnings in 48.59s \| caíram: te… | DETECTADA |
| M_STATUS_VAR_SIZE_8 | cursor.var(oracledb.DB_TYPE_VARCHAR, size=128) -> cursor.var(oracledb… | 1 substituição | 53 failed, 240 passed, 6 skipped, 13 warnings in 49.59s \| caíram: te… | DETECTADA |
| M_LOGON_COMENTARIO_NO_SELECT |                    type,\n                   logon_time\n          … | 1 substituição | 118 failed, 175 passed, 6 skipped, 13 warnings in 37.90s \| caíram:  … | DETECTADA |
| M_EXEC_INICIADO_ANTES_VAR |         status_var = cursor.var(oracledb.DB_TYPE_VARCHAR, size=128)\… | 1 substituição | 4 failed, 289 passed, 6 skipped, 13 warnings in 48.37s \| caíram: tes… | DETECTADA |
| M_EXEC_KILL_GET_DEFAULT | {c: alvo_reconsulta[c] for c in CAMPOS_IDENTIDADE_ESPERADA if c in al… | 1 substituição | 3 failed, 290 passed, 6 skipped, 13 warnings in 48.40s \| caíram: tes… | DETECTADA |
| M_FALLBACK_V1_NO_NAO_ENCONTRADO |         status_banco = str(status_var.getvalue() or "").strip()\n ->… | 1 substituição | 2 failed, 291 passed, 6 skipped, 13 warnings in 48.90s \| caíram: tes… | DETECTADA |
| M_LIMITE_GE_128 | len(valor) > LIMITE_TEXTO_IDENTIDADE -> len(valor) >= LIMITE_TEXTO_ID… | 1 substituição | 6 failed, 287 passed, 6 skipped, 13 warnings in 48.54s \| caíram: tes… | DETECTADA |
| X_REGEX_ID_0_9A_Z | _REGEX_ID_INTERVENCAO = re.compile(r"[0-9a-f]{32}") -> _REGEX_ID_INTE… | 1 substituição | 1 failed, 292 passed, 6 skipped, 13 warnings in 49.00s \| caíram: tes… | DETECTADA |
| X_SERIAL_FORA_ROW2 | dados_alvo["serial#"] = row[2] -> dados_alvo["serial#"] = row[1] | 1 substituição | 2 failed, 291 passed, 6 skipped, 13 warnings in 48.35s \| caíram: tes… | DETECTADA |
| X_SELECT_SID_SERIAL_TROCADOS |         query = """\n            SELECT inst_id,\n                 … | 1 substituição | 2 failed, 291 passed, 6 skipped, 13 warnings in 48.75s \| caíram: tes… | DETECTADA |
| m27_limite_local_em_bytes_utf8 | len(valor) > LIMITE_TEXTO_IDENTIDADE -> len(valor.encode("utf-8")) > … | 1 substituição | 3 failed, 290 passed, 6 skipped, 13 warnings in 48.14s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
