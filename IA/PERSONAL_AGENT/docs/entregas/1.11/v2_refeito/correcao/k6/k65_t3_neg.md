# Controle de mutação `k65_t3_neg`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py::test_t3_nove_binds_valores_exatos`; cópia `git archive HEAD`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 2 passed, 13 warnings in 1.39s | OK |
| M_T3_COMENTARIO_COM_FORMAL |                     p_status              => :p_status\n ->         … | 1 substituição | 2 passed, 13 warnings in 1.31s | PASSOU |

Resultado: alguma PASSOU (teste cego ou controle mal desenhado: L14, L18).
