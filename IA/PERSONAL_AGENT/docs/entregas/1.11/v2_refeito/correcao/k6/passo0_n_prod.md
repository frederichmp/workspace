# Controle de mutação `passo0_n_prod`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 237 passed, 6 skipped, 13 warnings in 49.60s | OK |
| N1_D8_VAZA_STR_EXC | Erro a partir da chamada ao PKG: {type(exc).__name__}"\n -> Erro a p… | 1 substituição | 237 passed, 6 skipped, 13 warnings in 48.54s | PASSOU |
| N2_PREP_GET_DEFAULT |     identidade = {c: fonte[c] for c in CAMPOS_IDENTIDADE_ESPERADA if … | 1 substituição | 237 passed, 6 skipped, 13 warnings in 55.42s | PASSOU |
| N3_PRE_HITL_IGNORA_CAMINHO_EFETIVO |             _gravar_linha_jsonl_duravel(_caminho_log_efetivo(caminho_… | 1 substituição | 237 passed, 6 skipped, 13 warnings in 54.86s | PASSOU |
| N5_SEM_STATUS_PKG_VAZIO_EM_MATAR |             status_banco = status_banco or STATUS_PKG_VAZIO\n ->  | 1 substituição | 237 passed, 6 skipped, 13 warnings in 55.63s | PASSOU |
| N6_PARAM_INST_DESCONHECIDO_TRUE |     validados = validar_parametros_kill(inst_id, sid, serial)\n    i… | 1 substituição | 237 passed, 6 skipped, 13 warnings in 55.47s | PASSOU |
| N7_BLOCO_COMENTARIO_PLSQL_V1 |                     p_username_esperado   => :p_username_esperado,\n… | 1 substituição | 237 passed, 6 skipped, 13 warnings in 54.05s | PASSOU |

Resultado: alguma PASSOU (teste cego ou controle mal desenhado: L14, L18).
