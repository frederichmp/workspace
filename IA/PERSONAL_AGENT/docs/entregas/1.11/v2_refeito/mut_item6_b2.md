# Controle de mutação `mut_item6_b2`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `src/main.py`, `app.py`, `tests/fakes_oracle.py`, `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 123 passed, 6 skipped, 13 warnings in 20.22s | OK |
| m9_logon_fora_do_hash | CAMPOS_IDENTIDADE_ALVO: Tuple[str, ...] = ("inst_id", "sid", "serial#… | 1 substituição | 2 failed, 121 passed, 6 skipped, 13 warnings in 20.74s \| caíram: tes… | DETECTADA |
| m10_divergente_como_executado | RESULTADOS_KILL_EXECUTADO: Tuple[str, ...] = ("ENCERRADA", "MARCADA_P… | 1 substituição | 1 failed, 122 passed, 6 skipped, 13 warnings in 20.82s \| caíram: tes… | DETECTADA |
| m11_retentativa_v1_no_except |     except oracledb.Error as db_err:\n        if execute_iniciado:\… | 1 substituição | 2 failed, 121 passed, 6 skipped, 13 warnings in 20.76s \| caíram: tes… | DETECTADA |
| m12_ecoa_ref_no_resultado |                     "mensagem": MENSAGEM_ALVO_DIVERGENTE,\n ->      … | 1 substituição | 1 failed, 122 passed, 6 skipped, 13 warnings in 20.53s \| caíram: tes… | DETECTADA |
| m13_logon_fora_do_select |                    type,\n                   logon_time\n          … | 1 substituição | 1 failed, 122 passed, 6 skipped, 13 warnings in 19.48s \| caíram: tes… | DETECTADA |
| m14_isoformat_com_T |         return valor.isoformat(sep=" ") ->         return valor.isofo… | 1 substituição | 1 failed, 122 passed, 6 skipped, 13 warnings in 20.56s \| caíram: tes… | DETECTADA |
| m15_d8_sem_resultado_desconhecido |                 "motivo": type(exc).__name__,\n                "resu… | 1 substituição | 1 failed, 122 passed, 6 skipped, 13 warnings in 21.05s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
