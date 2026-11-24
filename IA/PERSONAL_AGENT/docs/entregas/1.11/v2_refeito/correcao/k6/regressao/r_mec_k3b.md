# Controle de mutação `r_mec_k3b`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 293 passed, 6 skipped, 13 warnings in 48.59s | OK |
| M_EXEC_INICIADO_ANTES_VAR |         status_var = cursor.var(oracledb.DB_TYPE_VARCHAR, size=128)\… | 1 substituição | 4 failed, 289 passed, 6 skipped, 13 warnings in 48.38s \| caíram: tes… | DETECTADA |
| M_RHS_SWAP_PROG_MACH |                     p_program_esperado    => :p_program_esperado,\n … | 1 substituição | 15 failed, 278 passed, 6 skipped, 13 warnings in 49.23s \| caíram: te… | DETECTADA |
| M_RHS_SWAP_SID_SERIAL |                     p_sid                 => :p_sid,\n              … | 1 substituição | 15 failed, 278 passed, 6 skipped, 13 warnings in 51.07s \| caíram: te… | DETECTADA |

Resultado: todas DETECTADAS.
