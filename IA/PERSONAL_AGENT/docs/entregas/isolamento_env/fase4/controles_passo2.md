# Controles do Passo 2 (fase 4)

Rodados pela sessão principal (claude-opus-5-5) com scratchpad/passo2_ctrl/controles.sh: cópias de HEAD 216a6fd (produção = b0ce169) fora do repositório, .env só de sentinela, sem ORACLE_SANDBOX, `-k 'f4 or descartada or b3_nomes'` em tests/test_carga_env_entrada.py. Cada mutação conferida com 1 substituição por arquivo (bytes).

```
== ctrl_b0ce169: 17 failed, 1 passed, 17 deselected, 13 warnings in 97.07s (0:01:37)
   FAILED tests/test_carga_env_entrada.py::test_oracle_sandbox_do_env_descartada[cli]
   FAILED tests/test_carga_env_entrada.py::test_oracle_sandbox_do_env_descartada[web]
   FAILED tests/test_carga_env_entrada.py::test_b3_nomes_sombreados_sem_valores[cli]
   FAILED tests/test_carga_env_entrada.py::test_b3_nomes_sombreados_sem_valores[web]
   FAILED tests/test_carga_env_entrada.py::test_f4a_oserror_antes_da_escrita_permite_nova_tentativa[cli]
   FAILED tests/test_carga_env_entrada.py::test_f4a_oserror_antes_da_escrita_permite_nova_tentativa[web]
   FAILED tests/test_carga_env_entrada.py::test_f4b_uma_unica_leitura_do_env[cli]
   FAILED tests/test_carga_env_entrada.py::test_f4b_uma_unica_leitura_do_env[web]
   FAILED tests/test_carga_env_entrada.py::test_f4c_env_diretorio_fail_closed[cli]
   FAILED tests/test_carga_env_entrada.py::test_f4c_env_diretorio_fail_closed[web]
   FAILED tests/test_carga_env_entrada.py::test_f4c2_env_ausente_nova_tentativa
   FAILED tests/test_carga_env_entrada.py::test_f4d_linhas_malformadas_so_contagem[cli]
   FAILED tests/test_carga_env_entrada.py::test_f4d_linhas_malformadas_so_contagem[web]
   FAILED tests/test_carga_env_entrada.py::test_f4e_escrita_parcial_fail_closed[cli]
   FAILED tests/test_carga_env_entrada.py::test_f4e_escrita_parcial_fail_closed[web]
   FAILED tests/test_carga_env_entrada.py::test_f4g_ok_so_depois_do_descarte[cli]
   FAILED tests/test_carga_env_entrada.py::test_f4g_ok_so_depois_do_descarte[web]
== nova: 18 passed, 17 deselected, 13 warnings in 82.12s (0:01:22)
passo2_ctrl/m1/IA/PERSONAL_AGENT/app.py M1 1 troca
passo2_ctrl/m1/IA/PERSONAL_AGENT/src/main.py M1 1 troca
== m1_oserror_sempre_none: 2 failed, 16 passed, 17 deselected, 13 warnings in 85.09s (0:01:25)
   FAILED tests/test_carga_env_entrada.py::test_f4e_escrita_parcial_fail_closed[cli]
   FAILED tests/test_carga_env_entrada.py::test_f4e_escrita_parcial_fail_closed[web]
passo2_ctrl/m2/IA/PERSONAL_AGENT/app.py M2 1 troca
passo2_ctrl/m2/IA/PERSONAL_AGENT/src/main.py M2 1 troca
== m2_baseexception_none: 1 failed, 17 passed, 17 deselected, 13 warnings in 78.83s (0:01:18)
   FAILED tests/test_carga_env_entrada.py::test_f4h_interrupcao_fica_fail_closed
passo2_ctrl/m3/IA/PERSONAL_AGENT/app.py M3 1 troca
passo2_ctrl/m3/IA/PERSONAL_AGENT/src/main.py M3 1 troca
== m3_sem_pop: 6 failed, 12 passed, 17 deselected, 13 warnings in 80.89s (0:01:20)
   FAILED tests/test_carga_env_entrada.py::test_oracle_sandbox_do_env_descartada[cli]
   FAILED tests/test_carga_env_entrada.py::test_oracle_sandbox_do_env_descartada[web]
   FAILED tests/test_carga_env_entrada.py::test_f4a_oserror_antes_da_escrita_permite_nova_tentativa[cli]
   FAILED tests/test_carga_env_entrada.py::test_f4a_oserror_antes_da_escrita_permite_nova_tentativa[web]
   FAILED tests/test_carga_env_entrada.py::test_f4g_ok_so_depois_do_descarte[cli]
   FAILED tests/test_carga_env_entrada.py::test_f4g_ok_so_depois_do_descarte[web]
```

## Leitura
- Todos os testes novos falham contra b0ce169, menos (h), que passa por construção (L14) e é detectado pela M2.
- (e) também falha direto em b0ce169, só pela contagem de leituras ([2,0]); a parte fail-closed do (e) é provada pela M1. A decisão previa que (e) passaria em b0ce169.
- D3: os dois testes com expectativa alterada falham em b0ce169 (stream ausente), como esperado.
- M3 (sem o pop do finally) é pega por (a), (g) e pelo teste de descarte.
