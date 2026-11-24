# Controle de mutação `mut_k2_dba`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`, `tests/test_item1_intencao.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `src/main.py`, `app.py`, `tests/test_oracle_kill.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`, `tests/test_item1_intencao.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 185 passed, 6 skipped, 13 warnings in 49.27s | OK |
| m17_erro_oracle_como_recusa |     "ALVO_DIVERGENTE", "NAO_USUARIO", "USUARIO_PROTEGIDO",\n) ->    … | 1 substituição | 2 failed, 183 passed, 6 skipped, 13 warnings in 48.98s \| caíram: tes… | DETECTADA |
| m18_status_vazio_como_recusa |         elif status_banco in RECUSAS_PKG_SEM_KILL:\n ->         elif… | 1 substituição | 5 failed, 180 passed, 6 skipped, 13 warnings in 49.40s \| caíram: tes… | DETECTADA |
| m19_erro_interno_nao_desconhecido |                 "status_banco": "ERRO_INTERNO",\n                "re… | 1 substituição | 1 failed, 184 passed, 6 skipped, 13 warnings in 52.62s \| caíram:    … | DETECTADA |
| m20_flag_por_bool_sem_parse_ok |     resultado_desconhecido = not (parse_ok and dados_exec.get("result… | 1 substituição | 3 failed, 182 passed, 6 skipped, 13 warnings in 51.23s \| caíram: tes… | DETECTADA |
| m21_str_db_err_sem_helper |                 f"{_descrever_erro(db_err)}"\n ->                 f"… | 1 substituição | 1 failed, 184 passed, 6 skipped, 13 warnings in 49.12s \| caíram: tes… | DETECTADA |
| m24_corpo_erro_do_oracle |             f"foi aprovado por {aprovador} ({canal}); {MENSAGEM_DESFE… | 1 substituição | 6 failed, 179 passed, 6 skipped, 13 warnings in 49.59s \| caíram: tes… | DETECTADA |
| m17b_executado_ignora_desconhecido |     executado = resultado_banco in RESULTADOS_KILL_EXECUTADO and not … | 1 substituição | 4 failed, 181 passed, 6 skipped, 13 warnings in 48.94s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
