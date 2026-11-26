# Controle de mutação `mut_c6_m1_m16`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 237 passed, 6 skipped, 13 warnings in 48.75s | OK |
| m1_assinatura_v1_4_binds |                     p_username_esperado   => :p_username_esperado,\n… | 1 substituição | 25 failed, 212 passed, 6 skipped, 13 warnings in 48.89s \| caíram: te… | DETECTADA |
| m2_ordem_trocada_bloco_e_binds |                     p_username_esperado   => :p_username_esperado,\n… | 1 substituição | 15 failed, 222 passed, 6 skipped, 13 warnings in 48.54s \| caíram: te… | DETECTADA |
| m3_ordem_trocada_so_binds |                     p_username_esperado   => :p_username_esperado,\n… | 1 substituição | 15 failed, 222 passed, 6 skipped, 13 warnings in 48.74s \| caíram: te… | DETECTADA |
| m4_ref_aleatorio |             p_ref_aprovacao=ref_aprovacao, ->             p_ref_aprov… | 1 substituição | 4 failed, 233 passed, 6 skipped, 13 warnings in 47.81s \| caíram: tes… | DETECTADA |
| m5_logon_cru_sem_var_date |             p_logon_time_esperado=logon_var, ->             p_logon_t… | 1 substituição | 4 failed, 233 passed, 6 skipped, 13 warnings in 47.85s \| caíram: tes… | DETECTADA |
| m6_ref_com_default_none |     identidade_esperada: Dict[str, Any],\n    ref_aprovacao: str,\n… | 1 substituição | 1 failed, 236 passed, 6 skipped, 13 warnings in 48.23s \| caíram: tes… | DETECTADA |
| m7_sem_validacao_local |     invalidos = campos_invalidos_identidade_e_ref(identidade_esperada… | 1 substituição | 29 failed, 208 passed, 6 skipped, 13 warnings in 48.35s \| caíram: te… | DETECTADA |
| m8_strip_no_username |             p_username_esperado=identidade_esperada["username"], ->  … | 1 substituição | 2 failed, 235 passed, 6 skipped, 13 warnings in 47.79s \| caíram: tes… | DETECTADA |
| m9_logon_fora_do_hash | CAMPOS_IDENTIDADE_ALVO: Tuple[str, ...] = ("inst_id", "sid", "serial#… | 1 substituição | 2 failed, 235 passed, 6 skipped, 13 warnings in 48.40s \| caíram: tes… | DETECTADA |
| m10_divergente_como_executado | RESULTADOS_KILL_EXECUTADO: Tuple[str, ...] = ("ENCERRADA", "MARCADA_P… | 1 substituição | 3 failed, 234 passed, 6 skipped, 13 warnings in 48.33s \| caíram: tes… | DETECTADA |
| m11_retentativa_v1_no_except_adaptada |     except oracledb.Error as db_err:\n        # A3: o texto do erro … | 1 substituição | 4 failed, 233 passed, 6 skipped, 13 warnings in 47.69s \| caíram: tes… | DETECTADA |
| m12_ecoa_ref_no_resultado_adaptada |                 "resultado_desconhecido": desconhecido,\n           … | 1 substituição | 2 failed, 235 passed, 6 skipped, 13 warnings in 47.74s \| caíram: tes… | DETECTADA |
| m13_logon_fora_do_select |                    type,\n                   logon_time\n          … | 1 substituição | 106 failed, 131 passed, 6 skipped, 13 warnings in 37.06s \| caíram:  … | DETECTADA |
| m14_isoformat_com_T |         return valor.isoformat(sep=" ") ->         return valor.isofo… | 1 substituição | 1 failed, 236 passed, 6 skipped, 13 warnings in 49.26s \| caíram: tes… | DETECTADA |
| m15_d8_sem_resultado_desconhecido |                 "motivo": type(exc).__name__,\n                "resu… | 1 substituição | 3 failed, 234 passed, 6 skipped, 13 warnings in 48.29s \| caíram: tes… | DETECTADA |
| m16_fallback_v1_no_divergente_adaptada |         elif status_banco == "ALVO_DIVERGENTE":\n ->         elif st… | 1 substituição | 2 failed, 235 passed, 6 skipped, 13 warnings in 47.76s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
