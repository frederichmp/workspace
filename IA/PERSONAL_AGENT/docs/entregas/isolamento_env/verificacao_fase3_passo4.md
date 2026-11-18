# Verificação, isolamento do .env, fase 3, passo 4

- Data: 2026-11-18
- Modelo: claude-haiku-5-5
- Papel: `verificador`, antes do commit do passo 4 e do aceite da fase 3 (`docs/plans/isolamento_env_fase3.md` §6; `docs/PROCESSO.md` §5, passos 0 a 4)
- Branch `isolamento-env`, HEAD `427adfc`, working tree com 7 testes e `fase3_controles.md` modificados. Nada foi commitado, sem `git add`.
- Baseline do pedido: 212 passed, 16 skipped. Esperado agora: 226 passed, 16 skipped, 0 failed.
- Nota: o `docs/GOVERNANCA_LOG.md` registra 194 passed na fase 2 (`560a339`); o baseline de 212 é o do pedido e não foi reconferido contra o log.

## Resumo

| Passo | Resultado |
|---|---|
| 0. Perfil do Windows (só nomes) | OK |
| 1. `git status --short -- .` | OK (25 linhas, todas previstas) |
| 2. pytest sem conexão | OK (226 passed, 16 skipped, 0 failed) |
| 3. Greps de regressão (§5.3) | OK |
| 4. Isolamento em cópia (§5.4) | OK (427adfc passa; 673ceb1 falha com adicionadas_n=3) |
| Greps extras | OK, com notas |

Nenhuma FALHA. Nenhum critério de parada da §5 foi acionado.

## Passo 0: perfil do Windows

Comando da §5.0 (só nomes). Resultado: nenhuma linha. Nenhum nome com prefixo `ORACLE_`, `EMAIL_`, `GEMINI_`, `AGENTDBA_` ou `SCRIPTS_`. **OK.**

## Passo 1: estado do git

`git status --short -- .` (25 linhas):

- Modificados (8): `docs/entregas/isolamento_env/fase3_controles.md`; `tests/test_carga_env_entrada.py`; `tests/test_conftest_sandbox_env.py`; `tests/test_env_em_execucao.py`; `tests/test_executor.py`; `tests/test_guard_sessao_sandbox.py`; `tests/test_isolamento_env.py`; `tests/test_oracle_kill.py`.
- Não rastreados previstos (17): `docs/entregas/isolamento_env/verificacao_fase3_passo1.md`, `passo2.md`, `passo3.md`; `docs/entregas/1.11/item1/*` (11 entradas); `db/ops_kill.sqlbkp`; `docs/plans/1.11-item1-B-refeito.md`; `docs/entregas/processo-subagentes/`.

Caminho fora do previsto: nenhum. Os arquivos de `tests/` estão todos na lista, então o pytest não foi bloqueado. **OK.**

`git diff --stat 427adfc -- .`: 8 arquivos, 619 inserções e 2 remoções, coerente com os 8 modificados acima.

## Passo 2: pytest sem conexão

Comando: `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider`. Exit 0.

```
226 passed, 16 skipped, 13 warnings in 138.63s (0:02:18)
SKIPPED [16] tests\conftest.py:188: Teste ignorado: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)
```

- Passed: 226 (esperado 226). Failed: 0 (esperado 0). **OK.**
- Skipped: 16 (baseline 16). Todos os 16 com o motivo "requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)". Nenhum aviso de execução em sandbox. **OK.**
- Os 13 warnings são de `langsmith` (DeprecationWarning de `asyncio.iscoroutinefunction`), fora do escopo.

## Passo 3: greps de regressão (§5.3)

| Grep | Esperado | Obtido | OK/FALHA |
|---|---|---|---|
| `ORACLE_USER\b` em `src/`, `app.py`, `tools/` | vazio | vazio | OK |
| `alter (system\|session)` em `*.py` | vazio | vazio | OK |
| `override=True` em `src/`, `app.py`, `tools/` | vazio | vazio | OK |
| `load_dotenv(` em `src/`, `app.py` | 2 linhas, `override=False` | `app.py:69` e `src/main.py:54`, ambas com `override=False` | OK (números de linha diferem do §5.3, que cita 33 e 18 de versões anteriores; o conteúdo confere) |
| `setenv`/`environ[...] = "1"` de ORACLE_SANDBOX em `tests/*.py` | vazio | vazio | OK |
| credencial em `print`/`logger` | vazio | vazio | OK |
| `git diff --stat 427adfc -- registry/ db/` | vazio | vazio | OK |
| `git ls-files` com `.env` | vazio | vazio | OK |

## Passo 4: isolamento em cópia (§5.4)

Método: `git -C <raiz> archive --format=tar -o <tmp>/<commit>.tar <commit> IA/PERSONAL_AGENT`, extração com `tar --force-local`, em `%TEMP%`. Cada cópia recebeu um `.env` fictício só com os nomes-sentinela `SENTINELA_ISOLAMENTO_ENV`, `ORACLE_SENTINELA_FICTICIA`, `EMAIL_SENTINELA_FICTICIA` e `GEMINI_SENTINELA_FICTICIA`, sem `ORACLE_SANDBOX`. Na cópia de `427adfc`, `tests/test_isolamento_env.py` foi trocado pela versão do working tree (verificado igual). Rodado só `tests/test_isolamento_env.py`, com `env -u ORACLE_SANDBOX`.

| Cópia | Esperado | Obtido | OK/FALHA |
|---|---|---|---|
| `427adfc` + teste do working tree | passa | `1 passed`, exit 0 | OK |
| `673ceb1` (controle negativo) | falha com `adicionadas_n >= 1` | `1 failed`, exit 1: `adicionadas_n=3, removidas_n=0, alteradas_n=0, nomes_nao_sensiveis=[]` | OK |

O controle negativo mostra que o teste detecta a carga do `.env` pela produção. Nenhum valor foi impresso; só contagens e nomes não sensíveis (lista vazia).

## Greps extras

| Verificação | Esperado | Obtido | OK/FALHA |
|---|---|---|---|
| `git diff 427adfc -- src/ app.py tests/conftest.py registry/ db/` | vazio | vazio | OK (o passo 4 é só testes) |
| `ORACLE_SANDBOX['"]?\]? *= *['"]1` ou `setenv(... "1")` em `tests/` | vazio | vazio | OK |
| `sandbox_shell=\|ORACLE_SANDBOX"\] = ` em `tests/*.py` | só valores `"0"` ou ausente | valores abaixo | OK |
| Existência de `C:\AgentDBA` antes e depois | igual | `False` antes e `False` depois | OK |

Listagem do grep de `sandbox_shell=` e atribuições (`tests/*.py`):

- `test_carga_env_entrada.py:225`: `env["ORACLE_SANDBOX"] = sandbox_shell`, com `sandbox_shell` vindo de `None` (não atribui) ou de `"0"` (linha 262). Valores: só `"0"`.
- `test_conftest_sandbox_env.py:91`: `env["ORACLE_SANDBOX"] = sandbox_shell`, parametrizado com `[None, "0"]` e `assert sandbox_shell == "0"`. Valores: só `"0"`.
- `test_guard_sessao_sandbox.py:154`: mesmo padrão, parametrizado com `[None, "0"]` e `assert sandbox_shell == "0"`. Valores: só `"0"`.
- `test_guard_sessao_sandbox.py:111` e `:127`: `monkeypatch.setenv("ORACLE_SANDBOX", "0")` e `valor` de `[None, "0"]`.

Notas (não são falhas):

- `ORACLE_SANDBOX=1` aparece como conteúdo de `.env` fictício gravado em `tmp_path` (`test_carga_env_entrada.py`, linhas 247, 262, 281, 301, 317, 387, 396, 405, 431). Esse arquivo é lido só dentro de subprocesso, e o `.env` real não é lido. Não é atribuição ao ambiente do pytest.
- `"1"` aparece como argumento de operador em `credenciais_sandbox_do_env(arq, "1", ...)` (`test_conftest_sandbox_env.py:42` e `:57`). É um parâmetro de função pura e não toca `os.environ`.
- `load_dotenv` em `tests/` aparece só em mocks e substituições (`test_carga_env_entrada.py`, `test_env_em_execucao.py`, `test_fluxo_cli.py`, `test_fluxo_web.py`, `test_item1_intencao.py`). Não há chamada real ao `.env`.
- Grep de chave sombreada em logger (`-i`): só `src/tools/oracle_dba.py:1689`, que casa por `email_` e registra `Sucesso`, `Assunto` e `Detalhe` do SMTP. Não registra valor de chave. Falso positivo do padrão.

## Conclusão

Todos os itens dos passos 0 a 4 e dos greps extras estão OK. A contagem é 226 passed, 16 skipped, 0 failed. O controle negativo `673ceb1` falha como esperado. O passo 4 pode ser commitado pelo fluxo da §1, e o aceite da fase depende do responsável.

## Saídas e limpeza

- Saída desta verificação: `c:/Users/Frederich/OneDrive - Startup Dados e Sistemas Ltda - EPP/Workspace/IA/PERSONAL_AGENT/docs/entregas/isolamento_env/verificacao_fase3_passo4.md`.
- Temporários em `%TEMP%` (cópias `427adfc` e `673ceb1`, tars, `.env` fictícios, saídas brutas do pytest), removidos ao final.
