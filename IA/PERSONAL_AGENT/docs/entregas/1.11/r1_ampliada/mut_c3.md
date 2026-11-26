# Controle de mutação `mut_c3`

Alvo `src/tools/executor.py`; testes `tests/test_r1_saida_llm.py::test_r1_varredura_executor[select]`, `tests/test_r1_saida_llm.py::test_r1_varredura_executor[dml]`, `tests/test_r1_saida_llm.py::test_r1_varredura_executor[erro_oracle]`, `tests/test_r1_saida_llm.py::test_r1_varredura_executor[excecao]`, `tests/test_r1_saida_llm.py::test_r1_executor_path_invalido_sem_o_diretorio_de_scripts`, `tests/test_r1_saida_llm.py::test_r1_ast_a1_json_dumps_sem_chaves_proibidas`, `tests/test_r1_saida_llm.py::test_r1_ast_a2_excecao_so_em_tipo_codigo_registro_ou_log`; cópia `git archive HEAD` + `src/tools/executor.py`, `tests/test_r1_saida_llm.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 9 passed, 13 warnings in 1.39s | OK |
| M_R1_EXEC_V1_INSTANCIA_NO_SELECT |                     "sha256_verificado": sha256_calculado,\n        … | 1 substituição | 2 failed, 7 passed, 13 warnings in 2.13s \| caíram: tests/test_r1_sai… | DETECTADA |
| M_R1_EXEC_V3_TEXTO_DO_ORACLE |                 "mensagem": f"Erro do Oracle {_codigo_erro(db_err)}."… | 1 substituição | 2 failed, 7 passed, 13 warnings in 1.96s \| caíram: tests/test_r1_sai… | DETECTADA |
| M_R1_EXEC_V3_TEXTO_DA_EXCECAO |                 "mensagem": f"Erro inesperado durante execução: {_cod… | 1 substituição | 2 failed, 7 passed, 13 warnings in 1.58s \| caíram: tests/test_r1_sai… | DETECTADA |
| M_R1_EXEC_CAMINHO_DO_DIRETORIO |                         "ao diretório de scripts."\n ->             … | 1 substituição | 1 failed, 8 passed, 13 warnings in 1.76s \| caíram: tests/test_r1_sai… | DETECTADA |
| M_R1_EXEC_PATH_COM_TEXTO |                 "mensagem": f"Falha na validação do caminho do arquiv… | 1 substituição | 1 failed, 8 passed, 13 warnings in 1.71s \| caíram: tests/test_r1_sai… | DETECTADA |
| M_R1_EXEC_LOB_COM_TEXTO |             return f"<Erro ao ler LOB: {type(e).__name__}>"\n ->    … | 1 substituição | 1 failed, 8 passed, 13 warnings in 1.58s \| caíram: tests/test_r1_sai… | DETECTADA |

Resultado: todas DETECTADAS.
