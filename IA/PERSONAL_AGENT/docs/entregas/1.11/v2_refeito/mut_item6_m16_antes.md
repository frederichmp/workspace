# Controle de mutação `mut_item6_m16_antes`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `src/main.py`, `app.py`, `tests/fakes_oracle.py`, `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 123 passed, 6 skipped, 13 warnings in 18.60s | OK |
| m16_fallback_v1_no_divergente |         if status_banco == "ALVO_DIVERGENTE":\n ->         if status… | 1 substituição | 123 passed, 6 skipped, 13 warnings in 19.50s | PASSOU |

Resultado: alguma PASSOU (teste cego ou controle mal desenhado: L14, L18).
