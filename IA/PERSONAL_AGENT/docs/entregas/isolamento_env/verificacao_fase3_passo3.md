# Verificação fase 3, passo 3 (B3 e C3, avisos visíveis)

- Modelo: claude-haiku-5-5
- Branch: isolamento-env. HEAD: 3cb6e03. Working tree com as alterações do passo 3 (não commitadas).
- Baseline do pedido: 207 passed, 16 skipped. Esperado agora: 212 passed, 16 skipped, 0 failed.
- Base dos greps de `registry/` e `db/`: HEAD.
- Nenhum commit, add ou push foi feito. Esta verificação não grava nada além deste arquivo. A saída do pytest está resumida abaixo, em vez de um arquivo separado, porque a permissão de escrita é só este arquivo.

## Resultado geral

**OK.** Todos os itens de `docs/PROCESSO.md` §5 (passos 0 a 3) e os greps extras estão conforme o esperado. Não houve FALHA. A verificação não encontrou motivo para parar antes do pytest.

## Tabela

| Checagem | Esperado | Obtido | OK/FALHA |
|---|---|---|---|
| Passo 0, perfil do Windows (só nomes, prefixos ORACLE_/EMAIL_/GEMINI_/AGENTDBA_/SCRIPTS_) | nenhuma linha | nenhuma linha | OK |
| Passo 1, `git status --short -- .` | só os previstos no pedido | M app.py; M src/main.py; M tests/test_carga_env_entrada.py; M tests/test_fluxo_cli.py; M tests/test_fluxo_web.py; M docs/entregas/isolamento_env/fase3_controles.md; ?? verificacao_fase3_passo1.md; ?? verificacao_fase3_passo2.md; não rastreados pré-existentes: docs/entregas/1.11/item1/* (vários), db/ops_kill.sqlbkp, docs/plans/1.11-item1-B-refeito.md, docs/entregas/processo-subagentes/. Este arquivo ainda não existia no início. | OK |
| Sandbox no ambiente da sessão (`ORACLE_SANDBOX`) | ausente | ausente | OK |
| Passo 2, pytest sem conexão (`env -u ORACLE_SANDBOX ... pytest -q -rs -p no:cacheprovider`) | 0 failed; 212 passed; 16 skipped | 212 passed, 16 skipped, 0 failed; exit 0; 99,6 s | OK |
| Passo 2, motivo de cada skip | "requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)" | 16 skips com esse motivo (tests/conftest.py:188) | OK |
| Passo 2, avisos do pytest | nenhum erro de importação (oracledb) | 13 DeprecationWarning de langsmith (asyncio.iscoroutinefunction); não é falha | OK |
| Passo 3, G1 `ORACLE_USER\b` em src, app.py, tools | nenhuma linha | nenhuma linha | OK |
| Passo 3, G2 `alter system/session` em *.py | nenhuma linha | nenhuma linha | OK |
| Passo 3, G3 `override=True` | nenhuma linha | nenhuma linha | OK |
| Passo 3, G4 `load_dotenv(` em src e app.py | 2 linhas, override=False | app.py:69 e src/main.py:54, ambas com `override=False` | OK |
| Passo 3, G5 teste que liga o sandbox (setenv/environ = "1") | nenhuma linha | nenhuma linha | OK |
| Passo 3, G6 credencial em print/log | nenhuma linha | nenhuma linha | OK |
| Passo 3, G7 `git diff --stat HEAD -- registry/ db/` | vazio | vazio | OK |
| Passo 3, G8 `.env` versionado | nenhuma linha | nenhuma linha | OK |
| Extra 1, `load_dotenv(` / `dotenv_values(` em app.py, src, src/tools, src/config | só app.py e src/main.py, dentro do bloco carga-env | app.py:52 (dotenv_values) e :69 (load_dotenv), dentro de 34-81; src/main.py:37 (dotenv_values) e :54 (load_dotenv), dentro de 19-66 | OK |
| Extra 2, diff entre os blocos carga-env de app.py e src/main.py | vazio | vazio (48 linhas em cada bloco) | OK |
| Extra 3, `.warning(`/`print(`/`st.warning(` com `sombreadas` | só `", ".join(_ESTADO_ENV["sombreadas"])` ou f-string equivalente | app.py:103 `_log_carga.warning(_AVISO_SOMBREADAS + ", ".join(...))`; app.py:563 `st.warning(_AVISO_SOMBREADAS + ", ".join(...))`; src/main.py:92 `_log_carga.warning(...)` igual; src/main.py:93 `print(f"...{', '.join(_ESTADO_ENV['sombreadas'])}", file=sys.stderr)`. `_AVISO_SOMBREADAS` é texto fixo (app.py:46, src/main.py:31). Nenhum valor de .env aparece. | OK |
| Extra 4, `_personal_agent_estado_env` em app.py, src, tests | só app.py e src/main.py; em tests só docstring | app.py:58 e src/main.py:43 (chave do estado); tests/test_carga_env_entrada.py:9 (docstring) | OK |
| Extra 5, `dotenv_values` nas fixtures de test_fluxo_cli.py e test_fluxo_web.py | stub presente nas duas | test_fluxo_cli.py:101 e test_fluxo_web.py:138, `lambda *a, **k: {}` | OK |
| Extra 6, `C:\AgentDBA` antes e depois do pytest | igual | inexistente antes e inexistente depois | OK |
| Extra 7, leitura de `ORACLE_SANDBOX` em tests (grep bruto) | só leituras, nenhuma gravação com "1" | conftest.py:187, test_executor.py:38, test_privilegio_write_sandbox.py:18 são comparações (`!= "1"`) | OK |

## Observações

- Os greps do passo 3 usam `git grep`, que lê os arquivos rastreados no working tree. Por isso as alterações não commitadas de `app.py` e `src/main.py` entram na conferência.
- O grep de `dotenv_values` e `load_dotenv` foi feito também no working tree, porque a árvore tem alterações não commitadas.
- Não há `.env` versionado. O conteúdo do `.env` não foi lido.
- O `.env` e o perfil foram conferidos só por nomes. Nenhum valor foi impresso.

## Conclusão

Passo 3 conforme. O pytest fechou em 212 passed, 16 skipped, 0 failed, igual ao esperado. Pode seguir para o commit do passo 3, que é decisão da sessão principal e não desta verificação.
