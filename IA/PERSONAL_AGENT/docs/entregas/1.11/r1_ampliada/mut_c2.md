# Controle de mutação `mut_c2`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_r1_saida_llm.py`, `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `tests/test_r1_saida_llm.py`, `tests/test_oracle_kill.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 364 passed, 6 skipped, 13 warnings in 56.50s | OK |
| M_R1_V1_INSTANCIA_SUCESSO_SESSOES |                 "status": "sucesso",\n                "host_acessive… | 1 substituição | 2 failed, 362 passed, 6 skipped, 13 warnings in 55.98s \| caíram: tes… | DETECTADA |
| M_R1_V1_INSTANCIA_ERRO_CONFIG_KILL |                 "resultado_desconhecido": False,\n                "m… | 1 substituição | 2 failed, 362 passed, 6 skipped, 13 warnings in 54.87s \| caíram: tes… | DETECTADA |
| M_R1_V2_HOST_NA_PRE_CONSULTA |             "mensagem": TEXTO_HOST_INACESSIVEL,\n ->             "me… | 1 substituição | 3 failed, 361 passed, 6 skipped, 13 warnings in 56.05s \| caíram: tes… | DETECTADA |
| M_R1_V2_DETALHE_REDE_NO_KILL |                 "resultado_desconhecido": False,\n                "h… | 1 substituição | 2 failed, 362 passed, 6 skipped, 13 warnings in 57.07s \| caíram: tes… | DETECTADA |
| M_R1_V2_ERRO_REDE_COM_TEXTO |             "erro_rede": f"{type(net_err).__name__} errno={getattr(ne… | 1 substituição | 1 failed, 363 passed, 6 skipped, 13 warnings in 56.20s \| caíram: tes… | DETECTADA |
| M_R1_V3_STR_NA_PRE_CONSULTA | \n            "mensagem": f"Erro do Oracle {_codigo_erro(db_err)}.",… | 1 substituição | 3 failed, 361 passed, 6 skipped, 13 warnings in 57.03s \| caíram: tes… | DETECTADA |
| M_R1_V3_CODIGO_ERRO_DEVOLVE_TEXTO |                 return achado.group(0)\n ->                 return _… | 1 substituição | 13 failed, 351 passed, 6 skipped, 13 warnings in 56.67s \| caíram: te… | DETECTADA |
| M_R1_V3_KILL_DEPOIS_COM_TEXTO |                 f"{_codigo_erro(db_err)}"\n ->                 f"{_d… | 1 substituição | 5 failed, 359 passed, 6 skipped, 13 warnings in 58.14s \| caíram: tes… | DETECTADA |
| M_R1_V4_USERNAME_NA_RECUSA |                     "pertence a usuário protegido. Encerramento não p… | 1 substituição | 2 failed, 362 passed, 6 skipped, 13 warnings in 56.68s \| caíram: tes… | DETECTADA |
| M_R1_V5_APROVADOR_NA_MENSAGEM |                 f"Intervenção não aprovada ({decisao}/{motivo}). "\n… | 1 substituição | 1 failed, 363 passed, 6 skipped, 13 warnings in 54.84s \| caíram: tes… | DETECTADA |
| M_R1_V6_PKG_NO_EXECUTADO |                 f"Encerramento executado para "\n ->                … | 1 substituição | 3 failed, 361 passed, 6 skipped, 13 warnings in 55.99s \| caíram: tes… | DETECTADA |
| M_R1_V6_PKG_NO_SCHEMA |                 "de encerramento. Requer aprovação humana prévia (HIT… | 1 substituição | 1 failed, 363 passed, 6 skipped, 13 warnings in 56.23s \| caíram: tes… | DETECTADA |
| M_R1_V7_HASH_ATUAL_DE_VOLTA |                 # R1 ampliada V7 (R2; decisao_c1.md §2.7): os hashes … | 1 substituição | 3 failed, 361 passed, 6 skipped, 13 warnings in 55.70s \| caíram: tes… | DETECTADA |
| M_R1_V8E_COORDENADOR_POR_SUBSTRING |         return host in _HOSTS_COORDENADOR_LOCAL\n ->         return … | 1 substituição | 3 failed, 361 passed, 6 skipped, 13 warnings in 57.13s \| caíram: tes… | DETECTADA |
| M_R1_HISTORICO_POR_LISTA_NEGADA |             if mensagem.get("name") not in NOMES_FERRAMENTAS_SEM_DADO… | 1 substituição | 4 failed, 360 passed, 6 skipped, 13 warnings in 56.95s \| caíram: tes… | DETECTADA |
| M_R1_REGISTRO_LOCAL_MUDO |         logger.warning(" \| ".join(partes))\n ->         pass\n | 1 substituição | 1 failed, 363 passed, 6 skipped, 13 warnings in 56.96s \| caíram: tes… | DETECTADA |

Resultado: todas DETECTADAS.
