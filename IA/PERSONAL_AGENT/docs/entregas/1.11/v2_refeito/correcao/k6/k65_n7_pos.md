# Controle de mutação `k65_n7_pos`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD` + `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 294 passed, 6 skipped, 13 warnings in 49.79s | OK |
| N7_BLOCO_COMENTARIO_PLSQL_V1 |                     p_username_esperado   => :p_username_esperado,\n… | 1 substituição | 62 failed, 232 passed, 6 skipped, 13 warnings in 50.45s \| caíram: te… | DETECTADA |

Resultado: todas DETECTADAS.
