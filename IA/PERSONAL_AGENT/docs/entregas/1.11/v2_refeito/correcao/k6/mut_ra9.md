# Controle de mutação `mut_ra9`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_item1_intencao.py::test_ra_toda_chamada_de_producao_passa_resultado_desconhecido`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `tests/test_item1_intencao.py`, `tests/test_oracle_kill.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 1 passed, 13 warnings in 1.75s | OK |
| R-a9_interrompido_sem_o_argumento_so_ast |                 id_intervencao=id_intervencao,\n                resu… | 1 substituição | 1 failed, 13 warnings in 1.76s \| caíram: tests/test_item1_intencao.p… | DETECTADA |

Resultado: todas DETECTADAS.
