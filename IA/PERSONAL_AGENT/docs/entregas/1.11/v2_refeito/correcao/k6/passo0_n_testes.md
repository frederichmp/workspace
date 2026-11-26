# Controle de mutação `passo0_n_testes`

Alvo `tests/test_oracle_kill.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 237 passed, 6 skipped, 13 warnings in 54.13s | OK |
| N4_GATE_SANDBOX_DESLIGADO |     if os.getenv("OPS_KILL_PKG_VERSAO") != "2":\n        pytest.skip… | 1 substituição | 237 passed, 6 skipped, 13 warnings in 53.12s | PASSOU |
| N8_SANDBOX_PASSA_NONE |             identidade_esperada=identidade, ref_aprovacao=uuid.uuid4(… | 1 substituição | 237 passed, 6 skipped, 13 warnings in 53.51s | PASSOU |

Resultado: alguma PASSOU (teste cego ou controle mal desenhado: L14, L18).
