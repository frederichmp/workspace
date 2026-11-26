# Controle de mutação `r_k5`

Alvo `tests/test_oracle_kill.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 293 passed, 6 skipped, 13 warnings in 48.37s | OK |
| m28a_sandbox_sem_identidade_e_ref |         sid=-1, serial=1, inst_id=1,\n        identidade_esperada=id… | 1 substituição | 2 failed, 291 passed, 6 skipped, 13 warnings in 48.81s \| caíram: tes… | DETECTADA |
| m28b_sandbox_sem_gate |     """Reproduz caso validado no MODELO: encerramento de sessão de ST… | 1 substituição | 1 failed, 292 passed, 6 skipped, 13 warnings in 48.36s \| caíram: tes… | DETECTADA |
| m28c_sandbox_connect_sem_try_finally |     conn = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn… | 1 substituição | 1 failed, 292 passed, 6 skipped, 13 warnings in 48.43s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
