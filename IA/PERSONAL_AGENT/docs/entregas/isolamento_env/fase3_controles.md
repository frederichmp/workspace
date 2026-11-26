
## Passo 1

Modelo: Sonnet 5.5 (claude-sonnet-5-5), subagente `mecanico`. Arquivo escrito: `tests/test_carga_env_entrada.py`.
Cópia: `git archive --format=tar d05577e IA/PERSONAL_AGENT` extraída com `tar --force-local` em pasta nova de %TEMP% (sem `.env`; `app.py` e `src/main.py` iguais aos de d05577e, conferidos com `diff --strip-trailing-cr`). O teste da cópia foi sobrescrito pela versão do working tree (diff contra a versão de d05577e: 226 linhas, não vazio, L3). Comando: `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider tests/test_carga_env_entrada.py -k ...`. Pasta removida depois.

### Controle negativo: testes novos (esperado FAILED com AssertionError na asserção principal)

Resultado: 6 failed (b4 web, c1 cli, c1 web, c2a web, c2a cli, r_f2_1), todos na asserção principal, nenhum erro de harness (returncode 0, `excecoes_harness == []`).

```text
FFFFFF                                                                   [100%]
================================== FAILURES ===================================
________________ test_b4_web_chave_nova_entre_reruns_nao_entra ________________

tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-109/test_b4_web_chave_nova_entre_r0')

>       assert dados["sentinela_tardia"] == "AUSENTE", resumo
E       AssertionError: por_run=[{'sandbox': 'AUSENTE', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': []}, {'sandbox': 'AUSENTE', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': '1', 'excecoes': []}], chamadas=[{'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}]
E       assert '1' == 'AUSENTE'
E         
E         - AUSENTE
E         + 1

tests\test_carga_env_entrada.py:218: AssertionError
__________________ test_c1_nul_nao_deixa_oracle_sandbox[cli] __________________

entrada = 'cli'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-109/test_c1_nul_nao_deixa_oracle_s0')

>       assert [r["sandbox"] for r in dados["por_run"]] == ["AUSENTE", "AUSENTE"], resumo
E       AssertionError: por_run=[{'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['ValueError: embedded null character']}, {'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['ValueError: embedded null character']}], chamadas=[{'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}]
E       assert ['1', '1'] == ['AUSENTE', 'AUSENTE']
E         
E         At index 0 diff: '1' != 'AUSENTE'
E         Use -v to get more diff

tests\test_carga_env_entrada.py:232: AssertionError
__________________ test_c1_nul_nao_deixa_oracle_sandbox[web] __________________

entrada = 'web'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-109/test_c1_nul_nao_deixa_oracle_s1')

>       assert [r["sandbox"] for r in dados["por_run"]] == ["AUSENTE", "AUSENTE"], resumo
E       AssertionError: por_run=[{'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['Exception: embedded null character']}, {'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['Exception: embedded null character']}], chamadas=[{'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}]
E       assert ['1', '1'] == ['AUSENTE', 'AUSENTE']
E         
E         At index 0 diff: '1' != 'AUSENTE'
E         Use -v to get more diff

tests\test_carga_env_entrada.py:232: AssertionError
_____________ test_c2a_rerun_apos_falha_nao_promove_a_shell[web] ______________

entrada = 'web'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-109/test_c2a_rerun_apos_falha_nao_0')

>       assert dados["por_run"][1]["sandbox"] == "AUSENTE", resumo
E       AssertionError: por_run=[{'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['Exception: embedded null character']}, {'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': []}], chamadas=[{'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}]
E       assert '1' == 'AUSENTE'
E         
E         - AUSENTE
E         + 1

tests\test_carga_env_entrada.py:247: AssertionError
_____________ test_c2a_rerun_apos_falha_nao_promove_a_shell[cli] ______________

entrada = 'cli'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-109/test_c2a_rerun_apos_falha_nao_1')

>       assert dados["por_run"][1]["sandbox"] == "AUSENTE", resumo
E       AssertionError: por_run=[{'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': ['ValueError: embedded null character']}, {'sandbox': '1', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': []}], chamadas=[{'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}]
E       assert '1' == 'AUSENTE'
E         
E         - AUSENTE
E         + 1

tests\test_carga_env_entrada.py:247: AssertionError
_____________________ test_r_f2_1_duas_sessoes_uma_carga ______________________

tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-109/test_r_f2_1_duas_sessoes_uma_c0')

>       assert len(dados["chamadas"]) == 1, resumo
E       AssertionError: sandbox=AUSENTE, chamadas=[{'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}, {'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}], por_run=[{'sandbox': 'AUSENTE', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'excecoes': []}]
E       assert 2 == 1
E        +  where 2 = len([{'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override'...ho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.UNyZGN3i8K\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False}])

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

## Passo 2

Modelo: Sonnet 5.5 (claude-sonnet-5-5), subagente `mecanico`. Arquivos: `tests/test_item1_intencao.py`, `tests/test_oracle_kill.py`, `tests/test_carga_env_entrada.py`. Produção (`src/tools/oracle_dba.py`) já editada pela sessão principal; não tocada.

### Working tree (sem ORACLE_SANDBOX)

`env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider tests/test_item1_intencao.py tests/test_oracle_kill.py tests/test_carga_env_entrada.py`

```text
98 passed, 6 skipped, 13 warnings in 49.22s
SKIPPED [6] tests\conftest.py:188: Teste ignorado: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)
```

### Controle negativo do teste A3 em d05577e

Cópia por `git archive --format=tar d05577e IA/PERSONAL_AGENT` + `tar --force-local` em pasta nova de %TEMP% (`src/tools/oracle_dba.py` da cópia igual ao de d05577e); teste da cópia sobrescrito pela versão do working tree (diff de 277 linhas, não vazio, L3). `C:\AgentDBA` existe antes: False; depois: False. Pasta removida depois.

```text
FF                                                                       [100%]
================================== FAILURES ===================================
____________ test_a3_src_tools_antes_da_entrada_mesmo_destino[cli] ____________

entrada = 'cli'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-115/test_a3_src_tools_antes_da_ent0')

>       assert destinos["src"] is not None and Path(destinos["src"]) == esperado, resumo
E       AssertionError: destino_log={'src': 'C:\\AgentDBA\\logs\\kill_approval.log', 'tools': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\pytest-of-<usuario>\\pytest-115\\test_a3_src_tools_antes_da_ent0\\dir_env\\kill_approval.log'}, esperado=C:\Users\<usuario>\AppData\Local\Temp\pytest-of-<usuario>\pytest-115\test_a3_src_tools_antes_da_ent0\dir_env\kill_approval.log, chamadas=[{'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.1joxfvmnKl\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False, 'src_oracle_dba_importado': True}]
E       assert ('C:\\AgentDBA\\logs\\kill_approval.log' is not None and WindowsPath('C:/AgentDBA/logs/kill_approval.log') == WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-115/test_a3_src_tools_antes_da_ent0/dir_env/kill_approval.log'))
E        +  where WindowsPath('C:/AgentDBA/logs/kill_approval.log') = Path('C:\\AgentDBA\\logs\\kill_approval.log')

tests\test_carga_env_entrada.py:304: AssertionError
____________ test_a3_src_tools_antes_da_entrada_mesmo_destino[web] ____________

entrada = 'web'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-115/test_a3_src_tools_antes_da_ent1')

>       assert destinos["src"] is not None and Path(destinos["src"]) == esperado, resumo
E       AssertionError: destino_log={'src': 'C:\\AgentDBA\\logs\\kill_approval.log', 'tools': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\pytest-of-<usuario>\\pytest-115\\test_a3_src_tools_antes_da_ent1\\dir_env\\kill_approval.log'}, esperado=C:\Users\<usuario>\AppData\Local\Temp\pytest-of-<usuario>\pytest-115\test_a3_src_tools_antes_da_ent1\dir_env\kill_approval.log, chamadas=[{'caminho': 'C:\\Users\\<usuario>\\AppData\\Local\\Temp\\tmp.1joxfvmnKl\\copia\\IA\\PERSONAL_AGENT\\.env', 'override': False, 'src_oracle_dba_importado': True}]
E       assert ('C:\\AgentDBA\\logs\\kill_approval.log' is not None and WindowsPath('C:/AgentDBA/logs/kill_approval.log') == WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-115/test_a3_src_tools_antes_da_ent1/dir_env/kill_approval.log'))
E        +  where WindowsPath('C:/AgentDBA/logs/kill_approval.log') = Path('C:\\AgentDBA\\logs\\kill_approval.log')

tests\test_carga_env_entrada.py:304: AssertionError
============================== warnings summary ===============================
..\..\..\..\..\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: 13 warnings

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2 failed, 10 deselected, 13 warnings in 8.64s
```

## Passo 3

Modelo: Sonnet 5.5 (claude-sonnet-5-5), subagente `mecanico`. Arquivos: `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`, `tests/test_carga_env_entrada.py`. Produção não tocada (ainda sem `dotenv_values`).

### Fixtures de fluxo (feitas primeiro, P3b), no working tree

`env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider tests/test_fluxo_cli.py tests/test_fluxo_web.py`

```text
23 passed, 13 warnings in 33.57s
```

### Testes novos do passo 3: NÃO rodados no working tree (produção ainda sem o passo 3)

### Controle negativo em d05577e

Cópia por `git archive --format=tar d05577e IA/PERSONAL_AGENT` + `tar --force-local` em pasta nova de %TEMP% (sem `.env`; `app.py`, `src/main.py` e `src/tools/oracle_dba.py` iguais a d05577e). Teste da cópia sobrescrito pela versão do working tree (diff de 368 linhas, não vazio, L3). Verificação extra na cópia: nenhum valor fictício `dsn_` aparece em tela, log, stdout nem stderr nas duas entradas em d05577e (o harness não vaza). Pasta removida depois.
Resultado: 5 failed, todos com AssertionError na asserção principal (sem erro de harness). Saída bruta, truncada a 700 colunas por linha:

```text
FFFFF                                                                    [100%]
================================== FAILURES ===================================
__________________ test_b3_nomes_sombreados_sem_valores[cli] __________________

entrada = 'cli'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-118/test_b3_nomes_sombreados_sem_v0')

>       assert len(sombreados) == 1, resumo
E       AssertionError: avisos=[], stderr='', por_run=[{'sandbox': 'AUSENTE', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'oracle_dsn_do_shell': True, 'excecoes': [], 'warning_tela': [], 'tela_texto': ''}]
E       assert 0 == 1
E        +  where 0 = len([])

tests\test_carga_env_entrada.py:350: AssertionError
__________________ test_b3_nomes_sombreados_sem_valores[web] __________________

entrada = 'web'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-118/test_b3_nomes_sombreados_sem_v1')

>       assert len(sombreados) == 1, resumo
E       AssertionError: avisos=[], stderr="2026-11-18 14:09:11.909 WARNING streamlit.runtime.scriptrunner_utils.script_run_context: Thread 'MainThread': missing ScriptRunContext! This warning can be ignored when running in bare mode.\n", por_run=[{'sandbox': 'AUSENTE', 'sentinela': 'AUSENTE', 'sentinela_fase3': '1', 'sentinela_tardia': 'AUSENTE', 'oracle_dsn_do_shell': True, 'excecoes': [], 'warning_tela': ['Conecte a VPN para visualizar o Top SQL da instância Oracle.', '**Ollama Local (11434):** Offline\n\n⚡ *Failover Ativo:* `gemini-3.1-flash-lite-preview`'], 'tela_texto': 'SpecialBlock(\n    type=\'main\',\n    children={\n        0: Markdown(),\n        1: Block(\n            type=\'f
E       assert 0 == 1
E        +  where 0 = len([])

tests\test_carga_env_entrada.py:350: AssertionError
_________________________ test_c3_cli_aviso_em_stderr _________________________

tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-118/test_c3_cli_aviso_em_stderr0')

>       assert dados["stderr"].count(_PREFIXO_CLI + _TEXTO_DESCARTE) == 1, resumo
E       AssertionError: stderr='', avisos=['ORACLE_SANDBOX encontrada no .env foi DESCARTADA: só vale quando definida pelo operador no shell.']
E       assert 0 == 1
E        +  where 0 = <built-in method count of str object at 0x00007FFF08EB5828>(('[Sistema]: AVISO: ' + 'ORACLE_SANDBOX encontrada no .env foi DESCARTADA: só vale quando definida pelo operador no shell. Remova a chave do .env.'))
E        +    where <built-in method count of str object at 0x00007FFF08EB5828> = ''.count

tests\test_carga_env_entrada.py:372: AssertionError
_____________________ test_c3_cli_aviso_com_raiz_em_error _____________________

tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-118/test_c3_cli_aviso_com_raiz_em_0')

>       assert _TEXTO_DESCARTE in dados["stderr"], resumo
E       AssertionError: stderr='', avisos=[]
E       assert 'ORACLE_SANDBOX encontrada no .env foi DESCARTADA: só vale quando definida pelo operador no shell. Remova a chave do .env.' in ''

tests\test_carga_env_entrada.py:381: AssertionError
____________________ test_c3_web_st_warning_em_todo_rerun _____________________

tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-118/test_c3_web_st_warning_em_todo0')

>           assert any(_TEXTO_DESCARTE in w for w in run["warning_tela"]), resumo
E           AssertionError: por_run=[['Conecte a VPN para visualizar o Top SQL da instância Oracle.', '**Ollama Local (11434):** Offline\n\n⚡ *Failover Ativo:* `gemini-3.1-flash-lite-preview`'], ['Conecte a VPN para visualizar o Top SQL da instância Oracle.', '**Ollama Local (11434):** Offline\n\n⚡ *Failover Ativo:* `gemini-3.1-flash-lite-preview`']]
E           assert False
E            +  where False = any(<generator object test_c3_web_st_warning_em_todo_rerun.<locals>.<genexpr> at 0x00000199433CEA40>)

tests\test_carga_env_entrada.py:392: AssertionError
============================== warnings summary ===============================
..\..\..\..\..\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: 13 warnings

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
5 failed, 12 deselected, 13 warnings in 19.23s
```

## Passo 4

Modelo: Sonnet 5.5 (claude-sonnet-5-5), subagente `mecanico`. Só testes: `tests/test_conftest_sandbox_env.py`, `test_env_em_execucao.py`, `test_carga_env_entrada.py`, `test_guard_sessao_sandbox.py`, `test_isolamento_env.py`, `test_oracle_kill.py`, `test_executor.py`. Produção e `tests/conftest.py` não editados no repositório (as mutações só existem nas cópias).

### Working tree (sem ORACLE_SANDBOX)

`env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider` (suíte completa, exit code 0):

```text
226 passed, 16 skipped, 13 warnings in 137.08s (0:02:17)
```

Só os 7 arquivos do passo: `104 passed, 14 skipped`. Baseline da suíte: 212 passed, 16 skipped; 14 testes novos (226 passed).
`C:\AgentDBA` não existe antes nem depois.

### Controle por item (mutação em cópia de d05577e)

Método: `git archive --format=tar d05577e IA/PERSONAL_AGENT` + `tar --force-local`, uma cópia nova em %TEMP% por item; os 7 arquivos de teste do working tree copiados para a cópia; `.env` fictício na raiz da cópia só com `ORACLE_DSN=dsn_ficticio_ctl`, `SENTINELA_CTL=1` e `GEMINI_API_KEY=chave_ficticia_ctl` (nunca ORACLE_SANDBOX; o `.env` real não existe nas cópias). Cada item roda primeiro SEM mutação (deve passar) e depois COM mutação (deve falhar na asserção principal). A mutação confere a contagem de substituições e que o arquivo mudou (L3), e preserva CRLF (as cópias têm CRLF). Cópias removidas. `C:\AgentDBA` existia antes: False; depois: False.
Observação: as cópias são de d05577e e não do HEAD; a estrutura das entradas em d05577e (carga e WARNING no topo de `app.py` e `src/main.py`) é a que as mutações do D6.3 alteram.

Saída bruta (linhas cortadas em 400 colunas; "mutação ...: N substituição(ões)" é o resultado do aplicador):

```text
C:/AgentDBA existe antes: False

######## D6.1a (d61a_remove_and_v) test_conftest_sandbox_env -k "valor_vazio"
--- SEM mutação
.                                                                        [100%]
============================== warnings summary ===============================
1 passed, 5 deselected, 13 warnings in 1.33s
--- COM mutação
mutação d61a_remove_and_v: 1 substituição(ões) em tests/conftest.py; CRLF=True; sha antes=ba3cc3d510 depois=6fa43ffef7
F                                                                        [100%]
================================== FAILURES ===================================
_________ test_credenciais_sandbox_valor_vazio_ou_sem_valor_nao_entra _________
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-127/test_credenciais_sandbox_valor0')
>       assert credenciais_sandbox_do_env(arq, "1", {}) == {"ORACLE_USER_KILL": "kill_ficticio"}
E       AssertionError: assert {'ORACLE_DSN'...ill_ficticio'} == {'ORACLE_USER...ill_ficticio'}
E         
E         Omitting 1 identical items, use -vv to show
E         Left contains 2 more items:
E         {'ORACLE_DSN': '', 'ORACLE_USER_DIAG': None}
E         Use -v to get more diff
tests\test_conftest_sandbox_env.py:57: AssertionError
============================== warnings summary ===============================
1 failed, 5 deselected, 13 warnings in 1.46s

######## D6.1b (d61b_load_dotenv_override) test_conftest_sandbox_env -k "ligacao_real"
--- SEM mutação
..                                                                       [100%]
============================== warnings summary ===============================
2 passed, 4 deselected, 13 warnings in 2.06s
--- COM mutação
mutação d61b_load_dotenv_override: 1 substituição(ões) em tests/conftest.py; CRLF=True; sha antes=ba3cc3d510 depois=4b44cfa0a7
FF                                                                       [100%]
================================== FAILURES ===================================
_____ test_ligacao_real_do_conftest_nao_carrega_env_sem_operador[ausente] _____
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-129/test_ligacao_real_do_conftest_0')
sandbox_shell = None
>       assert dados["presentes"] == [], f"chaves do .env fictício entraram em os.environ: {dados['presentes']}"
E       AssertionError: chaves do .env fictício entraram em os.environ: ['ORACLE_DSN', 'ORACLE_USER_READ', 'ORACLE_PASSWORD_READ', 'ORACLE_USER_MUT', 'ORACLE_PASSWORD_MUT', 'ORACLE_USER_DIAG', 'ORACLE_PASSWORD_DIAG', 'ORACLE_USER_KILL', 'ORACLE_PASSWORD_KILL', 'ORACLE_CALL_TIMEOUT_MS', 'ORACLE_SELECT_LIMIT', 'ORACLE_LOB_LIMIT', 'SENTINELA_D61_A', 'SENTINELA_D61_B']
E       assert ['ORACLE_DSN'...ER_DIAG', ...] == []
E         
E         Left contains 14 more items, first extra item: 'ORACLE_DSN'
E         Use -v to get more diff
tests\test_conftest_sandbox_env.py:99: AssertionError
______ test_ligacao_real_do_conftest_nao_carrega_env_sem_operador[zero] _______
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-129/test_ligacao_real_do_conftest_1')
sandbox_shell = '0'
>       assert dados["presentes"] == [], f"chaves do .env fictício entraram em os.environ: {dados['presentes']}"
E       AssertionError: chaves do .env fictício entraram em os.environ: ['ORACLE_DSN', 'ORACLE_USER_READ', 'ORACLE_PASSWORD_READ', 'ORACLE_USER_MUT', 'ORACLE_PASSWORD_MUT', 'ORACLE_USER_DIAG', 'ORACLE_PASSWORD_DIAG', 'ORACLE_USER_KILL', 'ORACLE_PASSWORD_KILL', 'ORACLE_CALL_TIMEOUT_MS', 'ORACLE_SELECT_LIMIT', 'ORACLE_LOB_LIMIT', 'SENTINELA_D61_A', 'SENTINELA_D61_B']
E       assert ['ORACLE_DSN'...ER_DIAG', ...] == []
E         
E         Left contains 14 more items, first extra item: 'ORACLE_DSN'
E         Use -v to get more diff
tests\test_conftest_sandbox_env.py:99: AssertionError
============================== warnings summary ===============================
2 failed, 4 deselected, 13 warnings in 2.69s

######## D6.2a (d62a_notificador_explicito) test_env_em_execucao -k "fluxo_nao_le"
--- SEM mutação
.                                                                        [100%]
============================== warnings summary ===============================
1 passed, 1 deselected, 13 warnings in 1.35s
--- COM mutação
mutação d62a_notificador_explicito: 2 substituição(ões) em src/tools/notificador.py; CRLF=True; sha antes=3766124c8b depois=1ed57eac07
F                                                                        [100%]
================================== FAILURES ===================================
___________________ test_fluxo_nao_le_nem_recarrega_dotenv ____________________
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000020DD2F0FE10>
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-131/test_fluxo_nao_le_nem_recarreg0')
>       assert leituras == []
E       AssertionError: assert ['DotEnv.__init__'] == []
E         
E         Left contains one more item: 'DotEnv.__init__'
E         Use -v to get more diff
tests\test_env_em_execucao.py:173: AssertionError
============================== warnings summary ===============================
1 failed, 1 deselected, 13 warnings in 1.55s

######## D6.2b (d62b_gemini_override) test_env_em_execucao -k "fluxo_nao_le"
--- SEM mutação
.                                                                        [100%]
============================== warnings summary ===============================
1 passed, 1 deselected, 13 warnings in 1.33s
--- COM mutação
mutação d62b_gemini_override: 2 substituição(ões) em src/tools/gemini_router.py; CRLF=True; sha antes=0f67f1ad29 depois=bd720ac93f
F                                                                        [100%]
================================== FAILURES ===================================
___________________ test_fluxo_nao_le_nem_recarrega_dotenv ____________________
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001FCBAC13E10>
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-133/test_fluxo_nao_le_nem_recarreg0')
>       assert leituras == []
E       AssertionError: assert ['DotEnv.__init__'] == []
E         
E         Left contains one more item: 'DotEnv.__init__'
E         Use -v to get more diff
tests\test_env_em_execucao.py:173: AssertionError
============================== warnings summary ===============================
1 failed, 1 deselected, 13 warnings in 1.64s

######## D6.3a (d63a_carga_depois_dos_imports) test_carga_env_entrada -k "d63_valor"
--- SEM mutação
..                                                                       [100%]
============================== warnings summary ===============================
2 passed, 19 deselected, 13 warnings in 10.61s
--- COM mutação
mutação d63a_carga_depois_dos_imports: 1 substituição(ões) em src/main.py; CRLF=True; sha antes=3f12b84178 depois=29791e4909
mutação d63a_carga_depois_dos_imports: 1 substituição(ões) em app.py; CRLF=True; sha antes=866de727f8 depois=4d413d9308
FF                                                                       [100%]
================================== FAILURES ===================================
______ test_d63_valor_lido_no_import_prova_carga_antes_dos_imports[cli] _______
entrada = 'cli'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-135/test_d63_valor_lido_no_import_0')
>       assert dados["gemini_key_igual"] is True, resumo
E       AssertionError: gemini_key_igual=False, sentinela_fase3=1
E       assert False is True
tests\test_carga_env_entrada.py:423: AssertionError
______ test_d63_valor_lido_no_import_prova_carga_antes_dos_imports[web] _______
entrada = 'web'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-135/test_d63_valor_lido_no_import_1')
>       assert dados["gemini_key_igual"] is True, resumo
E       AssertionError: gemini_key_igual=False, sentinela_fase3=1
E       assert False is True
tests\test_carga_env_entrada.py:423: AssertionError
============================== warnings summary ===============================
2 failed, 19 deselected, 13 warnings in 10.88s

######## D6.3b (d63b_warning_antes_do_basicconfig) test_carga_env_entrada -k "d63_warning"
--- SEM mutação
..                                                                       [100%]
============================== warnings summary ===============================
2 passed, 19 deselected, 13 warnings in 11.65s
--- COM mutação
mutação d63b_warning_antes_do_basicconfig: 1 substituição(ões) em src/main.py; CRLF=True; sha antes=3f12b84178 depois=561cbdf520
mutação d63b_warning_antes_do_basicconfig: 1 substituição(ões) em app.py; CRLF=True; sha antes=866de727f8 depois=20612c92b9
FF                                                                       [100%]
================================== FAILURES ===================================
___________ test_d63_warning_de_descarte_depois_do_basicconfig[cli] ___________
entrada = 'cli'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-137/test_d63_warning_de_descarte_d0')
>       assert idx_basic and idx_basic[0] < idx_warn[0], resumo
E       AssertionError: eventos=[['WARNING', 'ORACLE_SANDBOX encontrada no .env foi DESCARTADA: só vale quando definida pelo operador no shell.'], ['basicConfig']]
E       assert ([1] and 1 < 0)
tests\test_carga_env_entrada.py:437: AssertionError
___________ test_d63_warning_de_descarte_depois_do_basicconfig[web] ___________
entrada = 'web'
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-137/test_d63_warning_de_descarte_d1')
>       assert idx_basic and idx_basic[0] < idx_warn[0], resumo
E       AssertionError: eventos=[['WARNING', 'ORACLE_SANDBOX encontrada no .env foi DESCARTADA: só vale quando definida pelo operador no shell.'], ['basicConfig']]
E       assert ([1] and 1 < 0)
tests\test_carga_env_entrada.py:437: AssertionError
============================== warnings summary ===============================
2 failed, 19 deselected, 13 warnings in 9.99s

######## D6.4a (d64a_corpo_da_fixture_apagado) test_guard_sessao_sandbox -k "fixture_guard"
--- SEM mutação
....                                                                     [100%]
============================== warnings summary ===============================
4 passed, 7 deselected, 13 warnings in 1.26s
--- COM mutação
mutação d64a_corpo_da_fixture_apagado: 1 substituição(ões) em tests/conftest.py; CRLF=True; sha antes=ba3cc3d510 depois=c93a212fca
FFFF                                                                     [100%]
================================== FAILURES ===================================
_______ test_fixture_guard_sai_quando_operador_tinha_e_ambiente_nao_tem _______
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000023AA84F8180>
>       with pytest.raises(pytest.exit.Exception) as exc:
E       Failed: DID NOT RAISE Exit
tests\test_guard_sessao_sandbox.py:100: Failed
_______ test_fixture_guard_sai_quando_ambiente_tem_e_operador_nao_tinha _______
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000023AA84F8050>
>       with pytest.raises(pytest.exit.Exception) as exc:
E       Failed: DID NOT RAISE Exit
tests\test_guard_sessao_sandbox.py:113: Failed
____ test_fixture_guard_sem_divergencia_nao_sai_e_toma_o_snapshot[ausente] ____
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000023AA83B3BF0>
valor = None
>       assert conftest._SNAPSHOT_SESSAO_TOMADO is True
E       assert False is True
E        +  where False = conftest._SNAPSHOT_SESSAO_TOMADO
tests\test_guard_sessao_sandbox.py:130: AssertionError
_____ test_fixture_guard_sem_divergencia_nao_sai_e_toma_o_snapshot[zero] ______
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000023AA84539B0>
valor = '0'
>       assert conftest._SNAPSHOT_SESSAO_TOMADO is True
E       assert False is True
E        +  where False = conftest._SNAPSHOT_SESSAO_TOMADO
tests\test_guard_sessao_sandbox.py:130: AssertionError
============================== warnings summary ===============================
4 failed, 7 deselected, 13 warnings in 1.58s

######## D6.4b (d64b_operador_fixo_none) test_guard_sessao_sandbox -k "operador_e_lido"
--- SEM mutação
..                                                                       [100%]
============================== warnings summary ===============================
2 passed, 9 deselected, 13 warnings in 1.99s
--- COM mutação
mutação d64b_operador_fixo_none: 1 substituição(ões) em tests/conftest.py; CRLF=True; sha antes=ba3cc3d510 depois=8d09729d79
.F                                                                       [100%]
================================== FAILURES ===================================
________ test_operador_e_lido_do_ambiente_no_inicio_do_processo[zero] _________
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-141/test_operador_e_lido_do_ambien1')
sandbox_shell = '0'
>       assert json.loads(res.stdout.strip().splitlines()[-1])["operador_visto"] == sandbox_shell
E       AssertionError: assert None == '0'
tests\test_guard_sessao_sandbox.py:161: AssertionError
============================== warnings summary ===============================
1 failed, 1 passed, 9 deselected, 13 warnings in 2.31s

######## D6.5 (d65_settings_load_dotenv) test_isolamento_env 
--- SEM mutação
.                                                                        [100%]
============================== warnings summary ===============================
1 passed, 13 warnings in 3.57s
--- COM mutação
mutação d65_settings_load_dotenv: 1 substituição(ões) em src/config/settings.py; CRLF=True; sha antes=749ee67e1e depois=5353a9392b
F                                                                        [100%]
================================== FAILURES ===================================
__________________ test_imports_de_teste_nao_alteram_environ __________________
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-143/test_imports_de_teste_nao_alte0')
>       assert dados["adicionadas_n"] == 0 and dados["removidas_n"] == 0, resumo
E       AssertionError: adicionadas_n=3, removidas_n=0, alteradas_n=0, nomes_nao_sensiveis=['SENTINELA_CTL']
E       assert (3 == 0)
tests\test_isolamento_env.py:63: AssertionError
============================== warnings summary ===============================
1 failed, 13 warnings in 3.77s

######## D3-diag (d3_diag) test_oracle_kill -k "ausencia_oracle_user_diag"
--- SEM mutação
.                                                                        [100%]
============================== warnings summary ===============================
1 passed, 38 deselected, 13 warnings in 1.29s
--- COM mutação
mutação d3_diag: 4 substituição(ões) em src/tools/oracle_dba.py; CRLF=True; sha antes=51e8c7ed39 depois=f97d5c9a65
F                                                                        [100%]
================================== FAILURES ===================================
_________________ test_ausencia_oracle_user_diag_sem_conexao __________________
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001A26F6ECD60>
>       res_sess = json.loads(coletar_sessoes_ativas())
tests\test_oracle_kill.py:144: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
src\tools\oracle_dba.py:160: in coletar_sessoes_ativas
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
args = ('host-teste:1521/TESTE',), kwargs = {'timeout': 3.0}
>       pytest.fail("verificar_acessibilidade_host não deve ser chamado quando falta ORACLE_USER_DIAG")
E       Failed: verificar_acessibilidade_host não deve ser chamado quando falta ORACLE_USER_DIAG
tests\test_oracle_kill.py:135: Failed
============================== warnings summary ===============================
1 failed, 38 deselected, 13 warnings in 1.62s

######## D3-kill (d3_kill) test_oracle_kill -k "ausencia_oracle_user_kill"
--- SEM mutação
.                                                                        [100%]
============================== warnings summary ===============================
1 passed, 38 deselected, 13 warnings in 1.30s
--- COM mutação
mutação d3_kill: 1 substituição(ões) em src/tools/oracle_dba.py; CRLF=True; sha antes=51e8c7ed39 depois=8a20c0a432
F                                                                        [100%]
================================== FAILURES ===================================
_________________ test_ausencia_oracle_user_kill_sem_conexao __________________
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000016BEB03CD60>
>       res = json.loads(matar_sessao_oracle(sid=10, serial=20, inst_id=1))
tests\test_oracle_kill.py:176: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
src\tools\oracle_dba.py:734: in matar_sessao_oracle
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
args = ('host-teste:1521/TESTE',), kwargs = {'timeout': 3.0}
>       pytest.fail("verificar_acessibilidade_host não deve ser chamado quando falta ORACLE_USER_KILL")
E       Failed: verificar_acessibilidade_host não deve ser chamado quando falta ORACLE_USER_KILL
tests\test_oracle_kill.py:167: Failed
============================== warnings summary ===============================
1 failed, 38 deselected, 13 warnings in 1.51s

######## D3-executor (d3_executor) test_executor -k "t19"
--- SEM mutação
.                                                                        [100%]
============================== warnings summary ===============================
1 passed, 37 deselected, 13 warnings in 1.34s
--- COM mutação
mutação d3_executor: 1 substituição(ões) em src/tools/executor.py; CRLF=True; sha antes=94e6000827 depois=1bac7ad8c1
F                                                                        [100%]
================================== FAILURES ===================================
________________ test_t19_oracle_user_read_ausente_com_select _________________
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x00000130462F1A70>
>       saida_str = executar_script("verificar_dual", {})
tests\test_executor.py:474: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
src\tools\executor.py:778: in executar_script
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
args = ()
kwargs = {'user': None, 'password': 'senha-fake', 'dsn': 'host-teste:1521/TESTE'}
>       pytest.fail("oracledb.connect não deve ser chamado quando falta ORACLE_USER_READ")
E       Failed: oracledb.connect não deve ser chamado quando falta ORACLE_USER_READ
tests\test_executor.py:467: Failed
============================== warnings summary ===============================
1 failed, 37 deselected, 13 warnings in 1.40s
C:/AgentDBA existe depois: False
FIM
```
