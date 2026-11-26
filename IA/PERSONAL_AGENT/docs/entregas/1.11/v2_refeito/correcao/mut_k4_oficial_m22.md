# Controle de mutação `mut_k4_oficial_m22`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `src/tools/__init__.py`, `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/fakes_oracle.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 225 passed, 6 skipped, 13 warnings in 47.79s | OK |
| m22_dsn_de_volta_no_d8 |                 # A5 (só este ramo, D8): sem "instancia": dsn; os dem… | 1 substituição | 1 failed, 224 passed, 6 skipped, 13 warnings in 47.99s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
