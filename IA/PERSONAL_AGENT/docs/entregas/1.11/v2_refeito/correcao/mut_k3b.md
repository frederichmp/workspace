# Controle de mutação `mut_k3b`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`; cópia `git archive HEAD` + `tests/test_oracle_kill.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 124 passed, 6 skipped, 13 warnings in 2.76s | OK |
| M_EXEC_INICIADO_ANTES_VAR |         status_var = cursor.var(oracledb.DB_TYPE_VARCHAR, size=128)\… | 1 substituição | 4 failed, 120 passed, 6 skipped, 13 warnings in 2.98s \| caíram: test… | DETECTADA |
| M_RHS_SWAP_PROG_MACH |                     p_program_esperado    => :p_program_esperado,\n … | 1 substituição | 2 failed, 122 passed, 6 skipped, 13 warnings in 2.98s \| caíram: test… | DETECTADA |
| M_RHS_SWAP_SID_SERIAL |                     p_sid                 => :p_sid,\n              … | 1 substituição | 2 failed, 122 passed, 6 skipped, 13 warnings in 3.01s \| caíram: test… | DETECTADA |

Resultado: todas DETECTADAS.
