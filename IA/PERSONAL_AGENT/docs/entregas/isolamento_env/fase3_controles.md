
## Passo 1

Modelo: Sonnet 5.5 (claude-sonnet-5-5), subagente `mecanico`. Arquivo escrito: `tests/test_carga_env_entrada.py`.
Cópia: `git archive --format=tar d05577e IA/PERSONAL_AGENT` extraída com `tar --force-local` em pasta nova de %TEMP% (sem `.env`; `app.py` e `src/main.py` iguais aos de d05577e, conferidos com `diff --strip-trailing-cr`). O teste da cópia foi sobrescrito pela versão do working tree (diff contra a versão de d05577e: 226 linhas, não vazio, L3). Comando: `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider tests/test_carga_env_entrada.py -k ...`. Pasta removida depois.

### Controle negativo: testes novos (esperado FAILED com AssertionError na asserção principal)

Resultado: 6 failed (b4 web, c1 cli, c1 web, c2a web, c2a cli, r_f2_1), todos na asserção principal, nenhum erro de harness (returncode 0, `excecoes_harness == []`).

```text
FFFFFF                                                                   [100%]
================================== FAILURES ===================================
________________ test_b4_web_chave_nova_entre_reruns_nao_entra ________________

tmp_path = WindowsPath('C:/Users/Frederich/AppData/Local/Temp/pytest-of-Frederich/pytest-109/test_b4_web_chave_nova_entre_r0')

>       assert dados["sentinela_tardia"] == "AUSENTE", resumo
E       AssertionError: por_run=[{'sandbox': 'AUSENTE', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': []}, {'sandbox': 'AUSENTE', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': '1', 'excecoes': []}], chamadas=[{'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}]
E       assert '1' == 'AUSENTE'
E         
E         - AUSENTE
E         + 1

tests\test_carga_env_entrada.py:218: AssertionError
__________________ test_c1_nul_nao_deixa_oracle_sandbox[cli] __________________

entrada = 'cli'
tmp_path = WindowsPath('C:/Users/Frederich/AppData/Local/Temp/pytest-of-Frederich/pytest-109/test_c1_nul_nao_deixa_oracle_s0')

>       assert [r["sandbox"] for r in dados["por_run"]] == ["AUSENTE", "AUSENTE"], resumo
E       AssertionError: por_run=[{'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['ValueError: embedded null character']}, {'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['ValueError: embedded null character']}], chamadas=[{'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}]
E       assert ['1', '1'] == ['AUSENTE', 'AUSENTE']
E         
E         At index 0 diff: '1' != 'AUSENTE'
E         Use -v to get more diff

tests\test_carga_env_entrada.py:232: AssertionError
__________________ test_c1_nul_nao_deixa_oracle_sandbox[web] __________________

entrada = 'web'
tmp_path = WindowsPath('C:/Users/Frederich/AppData/Local/Temp/pytest-of-Frederich/pytest-109/test_c1_nul_nao_deixa_oracle_s1')

>       assert [r["sandbox"] for r in dados["por_run"]] == ["AUSENTE", "AUSENTE"], resumo
E       AssertionError: por_run=[{'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['Exception: embedded null character']}, {'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['Exception: embedded null character']}], chamadas=[{'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}]
E       assert ['1', '1'] == ['AUSENTE', 'AUSENTE']
E         
E         At index 0 diff: '1' != 'AUSENTE'
E         Use -v to get more diff

tests\test_carga_env_entrada.py:232: AssertionError
_____________ test_c2a_rerun_apos_falha_nao_promove_a_shell[web] ______________

entrada = 'web'
tmp_path = WindowsPath('C:/Users/Frederich/AppData/Local/Temp/pytest-of-Frederich/pytest-109/test_c2a_rerun_apos_falha_nao_0')

>       assert dados["por_run"][1]["sandbox"] == "AUSENTE", resumo
E       AssertionError: por_run=[{'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['Exception: embedded null character']}, {'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': []}], chamadas=[{'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}]
E       assert '1' == 'AUSENTE'
E         
E         - AUSENTE
E         + 1

tests\test_carga_env_entrada.py:247: AssertionError
_____________ test_c2a_rerun_apos_falha_nao_promove_a_shell[cli] ______________

entrada = 'cli'
tmp_path = WindowsPath('C:/Users/Frederich/AppData/Local/Temp/pytest-of-Frederich/pytest-109/test_c2a_rerun_apos_falha_nao_1')

>       assert dados["por_run"][1]["sandbox"] == "AUSENTE", resumo
E       AssertionError: por_run=[{'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['ValueError: embedded null character']}, {'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': []}], chamadas=[{'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}]
E       assert '1' == 'AUSENTE'
E         
E         - AUSENTE
E         + 1

tests\test_carga_env_entrada.py:247: AssertionError
_____________________ test_r_f2_1_duas_sessoes_uma_carga ______________________

tmp_path = WindowsPath('C:/Users/Frederich/AppData/Local/Temp/pytest-of-Frederich/pytest-109/test_r_f2_1_duas_sessoes_uma_c0')

>       assert len(dados["chamadas"]) == 1, resumo
E       AssertionError: sandbox=AUSENTE, chamadas=[{'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}], por_run=[{'sandbox': 'AUSENTE', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': []}]
E       assert 2 == 1
E        +  where 2 = len([{'caminho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override'...ho': 'C:\\Users\\Frederich\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}])

tests\test_carga_env_entrada.py:261: AssertionError
============================== warnings summary ===============================
..\..\..\..\..\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: 13 warnings

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
6 failed, 4 deselected, 13 warnings in 23.09s
```

### Testes existentes em d05577e (esperado: passam)

```text
....                                                                     [100%]
============================== warnings summary ===============================
..\..\..\..\..\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: 13 warnings

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
4 passed, 6 deselected, 13 warnings in 15.12s
```
