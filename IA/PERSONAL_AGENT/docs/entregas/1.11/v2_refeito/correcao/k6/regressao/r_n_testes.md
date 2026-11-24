# Controle de mutação `r_n_testes`

Alvo `tests/test_oracle_kill.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 293 passed, 6 skipped, 13 warnings in 48.67s | OK |
| N4_GATE_SANDBOX_DESLIGADO |     if os.getenv("OPS_KILL_PKG_VERSAO") != "2":\n        pytest.skip… | 1 substituição | 5 failed, 288 passed, 6 skipped, 13 warnings in 49.96s \| caíram: tes… | DETECTADA |
| N8_SANDBOX_PASSA_NONE |             identidade_esperada=identidade, ref_aprovacao=uuid.uuid4(… | 1 substituição | 1 failed, 292 passed, 6 skipped, 13 warnings in 49.70s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
