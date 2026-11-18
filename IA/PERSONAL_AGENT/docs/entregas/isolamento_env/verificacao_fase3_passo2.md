# Verificação fase 3, passo 2 (isolamento do .env), antes do commit

- Modelo: claude-haiku-5-5
- Branch: isolamento-env. HEAD: 4aef0b4, mais working tree.
- Plano: docs/plans/isolamento_env_fase3.md §6. Procedimento: docs/PROCESSO.md §5, passos 0 a 3, mais os greps extras do pedido.
- Baseline: 205 passed, 16 skipped. Esperado agora: 207 passed, 16 skipped, 0 failed.

## Resumo

| Checagem | Esperado | Obtido | OK/FALHA |
|---|---|---|---|
| 0. Perfil do Windows, só nomes com ORACLE_/EMAIL_/GEMINI_/AGENTDBA_/SCRIPTS_ | nenhuma linha | 0 nomes | OK |
| 1. git status --short -- . | só previstos | 20 entradas, todas previstas (5 M, 15 ??) | OK |
| 2. pytest sem ORACLE_SANDBOX | 0 failed, 207 passed, 16 skipped | 207 passed, 16 skipped, 0 failed | OK |
| 2. Motivo dos skips | "requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)" | os 16 com o mesmo motivo | OK |
| 3. ORACLE_USER legado | nenhuma linha | nenhuma linha | OK |
| 3. alter system/session no Python | nenhuma linha | nenhuma linha | OK |
| 3. override=True | nenhuma linha | nenhuma linha | OK |
| 3. load_dotenv( em src/*.py e app.py | 2 linhas, override=False | app.py:57 e src/main.py:42, ambas override=False | OK |
| 3. ORACLE_SANDBOX=1 em tests/*.py | nenhuma linha | nenhuma linha | OK |
| 3. credencial em print ou log | nenhuma linha | nenhuma linha | OK |
| 3. git diff --stat 4aef0b4 -- registry/ db/ | vazio | vazio | OK |
| 3. .env versionado | nenhuma linha | nenhuma linha | OK |
| Extra: DIRETORIO_LOG_APROVACAO no git grep (*.py) | nada | nada | OK |
| Extra: DIRETORIO_LOG_APROVACAO no working tree (src, app.py, tests) | nada | nada | OK |
| Extra: CAMINHO_LOG_APROVACAO_PADRAO, _caminho_log_efetivo, _diretorio_log_aprovacao em oracle_dba.py | definições e uso só via _caminho_log_efetivo | definições em :37, :1005, :1010. Usos de _caminho_log_efetivo em :1180, :1203, :1406. Uso de _diretorio_log_aprovacao e CAMINHO_LOG_APROVACAO_PADRAO só dentro de _caminho_log_efetivo (:1014-1016). :31 é comentário | OK |
| Extra: blocos # >>> carga-env … # <<< carga-env de app.py e src/main.py | diff vazio | diff vazio (36 linhas em cada um) | OK |
| Extra: git diff 4aef0b4 -- app.py src/main.py | vazio | 0 linhas | OK |
| Extra: C:\AgentDBA antes e depois do pytest | igual | ausente antes, ausente depois | OK |

## Passo 0: perfil

Nenhum nome com prefixo proibido. Nenhum valor foi lido.

## Passo 1: git status --short -- .

Entradas (20), todas previstas:

- M: docs/entregas/isolamento_env/fase3_controles.md, src/tools/oracle_dba.py, tests/test_carga_env_entrada.py, tests/test_item1_intencao.py, tests/test_oracle_kill.py
- ??: db/ops_kill.sqlbkp; docs/entregas/1.11/item1/ (abc/, diff_producao.diff, diff_revisao_gemini.diff, diff_testes.diff, diff_tests.txt, greps.txt, o1o2/, pytest_run1.txt, pytest_run2.txt, revisao_adversarial_gemini.md, verificacao.md); docs/entregas/isolamento_env/verificacao_fase3_passo1.md; docs/entregas/processo-subagentes/; docs/plans/1.11-item1-B-refeito.md

Nenhum caminho fora do previsto, em tests/, src/ ou na raiz. O pytest foi liberado.

## Passo 2: pytest

Comando: `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider`

Resultado: `207 passed, 16 skipped, 13 warnings in 82.30s`, exit 0.

Skip (16x): `tests\conftest.py:188: Teste ignorado: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)`

Os 13 avisos são DeprecationWarning de `asyncio.iscoroutinefunction` dentro do langsmith, fora do projeto. A saída bruta ficou no scratchpad, por causa da regra de gravar só este arquivo em `docs/entregas`.

## Não executado (fora do pedido)

- PROCESSO §5.4 (cópia sem .env, teste de isolamento no HEAD e em 673ceb1) e os controles negativos do §4. O plano §6 os exige antes do commit; o pedido restringiu a verificação aos passos 0 a 3 e aos greps extras, então não foram rodados.

## Conclusão

Passos 0 a 3 e greps extras: todos OK. Não houve FALHA. Pytest: 207 passed, 16 skipped, 0 failed, igual ao esperado.
