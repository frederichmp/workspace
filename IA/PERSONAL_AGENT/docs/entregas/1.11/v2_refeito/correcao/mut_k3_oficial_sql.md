# Controle de mutação `mut_k3_oficial_sql`

Alvo `docs/entregas/1.11/item6/ops_kill.sql`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/fakes_oracle.py`, `docs/entregas/1.11/item6/ops_kill.sql`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 190 passed, 6 skipped, 13 warnings in 10.32s | OK |
| m26_formal_trocado_na_spec |     p_program_esperado    IN  VARCHAR2,\n    p_machine_esperado    IN… | 1 substituição | 1 failed, 189 passed, 6 skipped, 13 warnings in 10.20s \| caíram: tes… | DETECTADA |
| m26b_logon_time_varchar_no_body |     p_logon_time_esperado IN  DATE,\n    p_ref_aprovacao       IN  VA… | 1 substituição | 1 failed, 189 passed, 6 skipped, 13 warnings in 10.41s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
