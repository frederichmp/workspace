# Controle de mutação `mut_k5_oficial`

Alvo `tests/test_oracle_kill.py`; testes `tests/test_oracle_kill.py`; cópia `git archive HEAD` + `tests/test_oracle_kill.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 146 passed, 6 skipped, 13 warnings in 2.99s | OK |
| m28a_sandbox_sem_identidade_e_ref |         sid=-1, serial=1, inst_id=1,\n        identidade_esperada=id… | 1 substituição | 1 failed, 145 passed, 6 skipped, 13 warnings in 3.50s \| caíram: test… | DETECTADA |
| m28b_sandbox_sem_gate |     """Reproduz caso validado no MODELO: encerramento de sessão de ST… | 1 substituição | 1 failed, 145 passed, 6 skipped, 13 warnings in 3.26s \| caíram: test… | DETECTADA |
| m28c_sandbox_connect_sem_try_finally |     conn = oracledb.connect(user=user_mut, password=pass_mut, dsn=dsn… | 1 substituição | 1 failed, 145 passed, 6 skipped, 13 warnings in 3.22s \| caíram: test… | DETECTADA |

Resultado: todas DETECTADAS.
