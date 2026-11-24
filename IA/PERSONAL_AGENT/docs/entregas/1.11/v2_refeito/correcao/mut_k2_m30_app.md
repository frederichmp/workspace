# Controle de mutação `mut_k2_m30_app`

Alvo `app.py`; testes `tests/test_oracle_kill.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`, `tests/test_item1_intencao.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `src/main.py`, `app.py`, `tests/test_oracle_kill.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`, `tests/test_item1_intencao.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 185 passed, 6 skipped, 13 warnings in 49.51s | OK |
| m29m30_ramo_desconhecido_revertido |     elif desfecho.get("resultado_desconhecido"):\n ->     elif False… | 1 substituição | 2 failed, 183 passed, 6 skipped, 13 warnings in 48.62s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
