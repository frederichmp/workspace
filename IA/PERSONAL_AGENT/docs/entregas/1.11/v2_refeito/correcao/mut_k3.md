# Controle de mutação `mut_k3`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`; cópia `git archive HEAD` + `tests/test_oracle_kill.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 124 passed, 6 skipped, 13 warnings in 3.04s | OK |
| M_LIMITE_GE_128 | len(valor) > LIMITE_TEXTO_IDENTIDADE -> len(valor) >= LIMITE_TEXTO_ID… | 1 substituição | 6 failed, 118 passed, 6 skipped, 13 warnings in 2.93s \| caíram: test… | DETECTADA |
| M_EXEC_INICIADO_ANTES_VAR |         status_var = cursor.var(oracledb.DB_TYPE_VARCHAR, size=128)\n… | 'de' aparece 0 vez(es); precisa de 1 (alvo com 2122 CRLF e 0 LF só) | - | ERRO |
| M_EXEC_KILL_GET_DEFAULT | {c: alvo_reconsulta[c] for c in CAMPOS_IDENTIDADE_ESPERADA if c in al… | 1 substituição | 3 failed, 121 passed, 6 skipped, 13 warnings in 2.99s \| caíram: test… | DETECTADA |
| X_REGEX_ID_0_9A_Z | _REGEX_ID_INTERVENCAO = re.compile(r"[0-9a-f]{32}") -> _REGEX_ID_INTE… | 1 substituição | 1 failed, 123 passed, 6 skipped, 13 warnings in 2.91s \| caíram: test… | DETECTADA |
| M_RHS_SWAP_PROG_MACH |                     p_program_esperado    => :p_program_esperado,\n  … | 'de' aparece 0 vez(es); precisa de 1 (alvo com 2122 CRLF e 0 LF só) | - | ERRO |
| M_RHS_SWAP_SID_SERIAL |                     p_sid                 => :p_sid,\n               … | 'de' aparece 0 vez(es); precisa de 1 (alvo com 2122 CRLF e 0 LF só) | - | ERRO |
| m27_limite_em_bytes_utf8 | len(valor) > LIMITE_TEXTO_IDENTIDADE -> len(valor.encode("utf-8")) > … | 1 substituição | 3 failed, 121 passed, 6 skipped, 13 warnings in 3.05s \| caíram: test… | DETECTADA |

Resultado: controle INVÁLIDO ou ERRO.
