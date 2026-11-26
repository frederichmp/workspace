# Controle de mutação `mut_c5b_main`

Alvo `src/main.py`; testes `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `tests/test_oracle_kill.py`, `tests/test_fluxo_cli.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 40 passed, 13 warnings in 58.53s | OK |
| M_R1_CLI_SEM_TRAVA_NO_LAUDO_FINAL | \n    if not local and historico_tem_dado_do_banco(messages):\n -> … | 1 substituição | 1 failed, 39 passed, 13 warnings in 58.58s \| caíram: tests/test_flux… | DETECTADA |

Resultado: todas DETECTADAS.
