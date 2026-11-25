# Controle de mutação `mut_c4_dba_b`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`, `tests/test_r1_saida_llm.py::test_r1_ast_a2_excecao_so_em_tipo_codigo_registro_ou_log`, `tests/test_r1_saida_llm.py::test_r1_ast_a4_coordenador_sem_analisar_log_complexo`, `tests/test_r1_saida_llm.py::test_r1_system_prompt_sem_regra_de_ouro`, `tests/test_r1_saida_llm.py::test_r1_nomes_ferramentas_oracle_iguais_ao_schema`; cópia `git archive HEAD` + `app.py`, `src/main.py`, `src/tools/oracle_dba.py`, `tests/test_fluxo_web.py`, `tests/test_fluxo_cli.py`, `tests/test_r1_saida_llm.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 48 passed, 13 warnings in 64.75s (0:01:04) | OK |
| M_R1_NOMES_ORACLE_SEM_O_KILL | NOMES_FERRAMENTAS_ORACLE = frozenset(f["function"]["name"] for f in o… | 1 substituição | 4 failed, 44 passed, 13 warnings in 65.75s (0:01:05) \| caíram: tests… | DETECTADA |

Resultado: todas DETECTADAS.
