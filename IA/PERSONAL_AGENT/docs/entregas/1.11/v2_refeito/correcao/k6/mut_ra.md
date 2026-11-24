# Controle de mutação `mut_ra`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `tests/test_item1_intencao.py`, `tests/test_oracle_kill.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 271 passed, 6 skipped, 13 warnings in 55.06s | OK |
| R-a1_principal_sem_o_argumento |             id_intervencao=id_intervencao,\n            resultado_de… | 1 substituição | 51 failed, 220 passed, 6 skipped, 13 warnings in 54.17s \| caíram:   … | DETECTADA |
| R-a2_principal_false_fixo |             id_intervencao=id_intervencao,\n            resultado_de… | 1 substituição | 3 failed, 268 passed, 6 skipped, 13 warnings in 56.40s \| caíram: tes… | DETECTADA |
| R-a3_interrompido_false |                 id_intervencao=id_intervencao,\n                resu… | 1 substituição | 1 failed, 270 passed, 6 skipped, 13 warnings in 55.86s \| caíram: tes… | DETECTADA |
| R-a4_reconciliador_false |                     id_intervencao=id_reg,\n                    resu… | 1 substituição | 1 failed, 270 passed, 6 skipped, 13 warnings in 55.73s \| caíram: tes… | DETECTADA |
| R-a5_reconc_so_conta_com_o_campo |                     elif reg.get("fase") == "RESULTADO":\n ->       … | 1 substituição | 2 failed, 269 passed, 6 skipped, 13 warnings in 56.69s \| caíram: tes… | DETECTADA |
| R-a5b_reconciliador_so_conta_bool |                     elif reg.get("fase") == "RESULTADO":\n ->       … | 1 substituição | 5 failed, 266 passed, 6 skipped, 13 warnings in 57.65s \| caíram: tes… | DETECTADA |
| R-a6_sem_campo_vira_linha_invalida |                     elif reg.get("fase") == "RESULTADO":\n          … | 1 substituição | 2 failed, 269 passed, 6 skipped, 13 warnings in 55.56s \| caíram: tes… | DETECTADA |
| R-a7_recusa_humana_true |                 id_intervencao=id_intervencao,\n                resu… | 1 substituição | 2 failed, 269 passed, 6 skipped, 13 warnings in 56.30s \| caíram: tes… | DETECTADA |
| R-a8_sem_validacao_bool |         if not isinstance(resultado_desconhecido, bool):\n ->       … | 1 substituição | 5 failed, 266 passed, 6 skipped, 13 warnings in 56.38s \| caíram: tes… | DETECTADA |
| R-a10_critical_sem_o_campo |                     "resultado_desconhecido": resultado_desconhecido,… | 1 substituição | 2 failed, 269 passed, 6 skipped, 13 warnings in 55.93s \| caíram: tes… | DETECTADA |
| R-a10b_critical_false_fixo |                     "resultado_desconhecido": resultado_desconhecido,… | 1 substituição | 1 failed, 270 passed, 6 skipped, 13 warnings in 56.58s \| caíram: tes… | DETECTADA |
| R-a11_intencao_aceita_valor |     elif resultado_desconhecido is not None:\n ->     elif False:\n | 1 substituição | 3 failed, 268 passed, 6 skipped, 13 warnings in 56.64s \| caíram: tes… | DETECTADA |
| R-a12_chave_em_toda_fase |     if fase == "RESULTADO":\n        registro["resultado_desconhecid… | 1 substituição | 7 failed, 264 passed, 6 skipped, 13 warnings in 57.15s \| caíram: tes… | DETECTADA |
| R-a13_interrompido_recup_sem_campo |             "resultado_banco": "INTERROMPIDO",\n            "resulta… | 1 substituição | 1 failed, 270 passed, 6 skipped, 13 warnings in 55.61s \| caíram: tes… | DETECTADA |
| R-a14_recusa_recup_sem_campo |                         "resultado_banco": None,\n                  … | 1 substituição | 2 failed, 269 passed, 6 skipped, 13 warnings in 56.23s \| caíram:    … | DETECTADA |
| R-a15_default_true |     id_intervencao: str,\n    resultado_desconhecido: Optional[bool]… | 1 substituição | 2 failed, 269 passed, 6 skipped, 13 warnings in 55.79s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
