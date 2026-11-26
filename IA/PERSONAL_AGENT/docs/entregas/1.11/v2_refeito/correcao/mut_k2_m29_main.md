# Controle de mutação `mut_k2_m29_main`

Alvo `src/main.py`; testes `tests/test_oracle_kill.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`, `tests/test_item1_intencao.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `src/main.py`, `app.py`, `tests/test_oracle_kill.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`, `tests/test_item1_intencao.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 185 passed, 6 skipped, 13 warnings in 50.16s | OK |
| m29m30_ramo_desconhecido_revertido |     elif desfecho.get("resultado_desconhecido"):\n ->     elif False… | 1 substituição | 1 failed, 184 passed, 6 skipped, 13 warnings in 50.52s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
