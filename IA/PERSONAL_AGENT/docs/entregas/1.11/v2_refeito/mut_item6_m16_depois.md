# Controle de mutação `mut_item6_m16_depois`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `src/main.py`, `app.py`, `tests/fakes_oracle.py`, `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 126 passed, 6 skipped, 13 warnings in 18.61s | OK |
| m16_fallback_v1_no_divergente |         if status_banco == "ALVO_DIVERGENTE":\n ->         if status… | 1 substituição | 1 failed, 125 passed, 6 skipped, 13 warnings in 17.07s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
