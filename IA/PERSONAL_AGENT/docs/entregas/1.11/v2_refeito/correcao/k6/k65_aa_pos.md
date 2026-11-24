# Controle de mutação `k65_aa_pos`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD` + `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 294 passed, 6 skipped, 13 warnings in 50.21s | OK |
| M_ALVO_ALTERADO_DESCONHECIDO_TRUE |                 "status_banco": "ALVO_ALTERADO",\n                "r… | 1 substituição | 4 failed, 290 passed, 6 skipped, 13 warnings in 49.77s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
