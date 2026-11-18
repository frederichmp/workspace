# Plano: isolamento do .env

**Status: AGUARDANDO APROVAÇÃO. Nenhum código foi editado.**

- Base: `673ceb1` (branch `item1/reaplicado`).
- Insumos:
  - listagem do `verificador` (claude-haiku-5-5): `docs/entregas/isolamento_env/listagem.md`;
  - decisão do `seguranca` (claude-opus-5-5): `docs/entregas/isolamento_env/decisao.md`.
- Motivo: `tests/test_isolamento_env.py::test_imports_de_teste_nao_alteram_environ` falha em HEAD. O import dos módulos de teste acrescenta variáveis ao `os.environ`: 18 no pytest e 22 na simulação.

## 1. `load_dotenv` em `src/` e `app.py`

| Arquivo:linha | Nível | Forma | Destino |
|---|---|---|---|
| `app.py:33` | módulo | `load_dotenv(ROOT_DIR / ".env")` | **fica** (ponto de entrada), com `override=False` explícito |
| `src/main.py:18` | módulo | `load_dotenv(ROOT_DIR / ".env")` | **fica** (ponto de entrada), com `override=False` explícito |
| `src/tools/oracle_dba.py:33` | módulo | caminho explícito | sai |
| `src/tools/executor.py:35` | módulo | sem caminho (`find_dotenv`) | sai |
| `src/tools/executor.py:38` | módulo, dentro de `if` | caminho explícito, `override=False` | sai |
| `src/tools/gemini_router.py:19` | módulo | sem caminho | sai |
| `src/tools/notificador.py:12` | módulo | sem caminho | sai |
| `src/config/settings.py:6` | módulo | sem caminho (nenhum módulo importa o `settings`) | sai |
| `src/tools/gemini_router.py:37` | função (`analisar_log_complexo`) | `override=True` a cada chamada | sai (D4) |
| `src/tools/notificador.py:17` | função (`enviar_alerta_email`) | `override=True` a cada envio | sai (D4) |

Os imports de `dotenv` que ficarem sem uso também saem.

`src/tools/__init__.py` importa `oracle_dba`, `gemini_router` e `notificador`. Por isso, qualquer import de `tools.*` ou `src.tools.*` dispara hoje três carregamentos.

## 2. Ponto de carga (decisão do `seguranca`)

- **D1.** Só `app.py:33` e `src/main.py:18` carregam o `.env`. Os dois já estão antes do primeiro import do projeto (`app.py:52`, `main.py:39`). A forma é `load_dotenv(ROOT_DIR / ".env", override=False)`.
  - `dotenv_values` não é usado no ponto de entrada. Motivo: `test_fluxo_cli.py:81-82`, `test_fluxo_web.py:127-129` e `test_item1_intencao.py:994-996` neutralizam o `.env` trocando só `load_dotenv`.
- **D2.** Se `ORACLE_SANDBOX` vier do arquivo e não estava no shell antes da carga, ela é descartada com WARNING; a aplicação não aborta. Se veio do shell, fica.
  - A produção não lê `ORACLE_SANDBOX` (conferido: zero ocorrências em `app.py` e `src/`).
  - O WARNING é emitido depois do `logging.basicConfig`. Um `logging.warning` antes dele configuraria o logging implicitamente e descartaria os FileHandlers de auditoria.
- **D3.** Remover todos os carregamentos de módulo listados no passo 1 como "sai". Nenhum precisa ficar: o `executor` só é importado pelos testes.
  - Residual aceito: os blocos `__main__` de `gemini_router.py:158` e `notificador.py:46` passam a rodar sem `.env` e devolvem "credencial ausente" (fail-closed).
- **D4.** Remover os `load_dotenv(override=True)` em tempo de chamada. Hoje `notificador.py:17` roda depois de cada kill (`oracle_dba.py:1684`) e pode regravar `ORACLE_USER_KILL`, `ORACLE_DSN` e `ORACLE_SANDBOX` a partir de qualquer `.env` encontrado subindo a árvore.
  - Perda aceita: mudar o valor de uma chave no `.env` passa a exigir reinício da CLI ou da Web.

## 3. Testes que hoje recebem o `.env` no import

| Teste | Hoje | Depois |
|---|---|---|
| `tests/test_executor.py:24` | `load_dotenv(..., override=False)` no import, antes de `from src.tools.executor` | a linha e o import sem uso saem; expectativas e asserções inalteradas |
| `tests/test_privilegio_read.py:10` | carga no import, dentro de `if` | sai |
| `tests/test_privilegio_write_sandbox.py:9` | carga no import, dentro de `if` | sai |
| Testes `sandbox_only` (`test_executor` T9/T13 e fixture `setup_banco_teste`; `test_oracle_kill` `test_sandbox_*`; `test_privilegio_*`) | credenciais vêm das cargas acima ou da produção | **carga explícita única em `tests/conftest.py`, logo depois da linha 28**, nas condições abaixo |
| Testes não-sandbox | herdavam o `.env` real | **nenhum `.env`**; usam `monkeypatch`/fakes, como já fazem (listagem D2) |

Condições da carga explícita no conftest (D5):
- só roda se `ORACLE_SANDBOX_DO_OPERADOR == "1"` (`conftest.py:10`), isto é, se o operador definiu a variável no shell;
- usa `dotenv_values` com lista de permissão: DSN, contas READ/MUT/DIAG/KILL e os três limites `ORACLE_*`;
- só preenche chaves ausentes;
- **nunca** traz `ORACLE_SANDBOX`, `ORACLE_USER`/`ORACLE_PASSWORD` legados, `AGENTDBA_LOG_DIR`, `SCRIPTS_*`, `EMAIL_*` ou `GEMINI_*`.

O teste de isolamento não é alterado. **`tests/test_executor.py` é alterado** (remoção da carga). Não é mudança de expectativa; fica registrada na lista de alterações.

## 4. `test_imports_de_teste_nao_alteram_environ` passa sem alterar o teste

- **Simulação, sem editar código.** O mesmo conjunto de imports do teste, com `dotenv.load_dotenv` neutralizado antes deles:
  - neutralizado: 0 adicionadas, 0 removidas, 0 alteradas;
  - original: 22 adicionadas.
  - Chamadas interceptadas: `tests/test_executor.py:24`, `notificador.py:12`, `oracle_dba.py:33`, `gemini_router.py:19`, `executor.py:35` e `:38`. Os passos 1 e 3 removem todas.
- **Por que remover equivale a neutralizar:** nenhuma dessas chamadas tem o retorno usado. Além disso, o subprocesso do teste não importa o conftest (a carga do D5 não roda lá) e filtra os prefixos `ORACLE_`, `EMAIL_` e `GEMINI_`.
- **Verificação no aceite (sem `ORACLE_SANDBOX`):**
  1. `git diff 673ceb1 -- tests/test_isolamento_env.py` vazio.
  2. Sentinela: extrair `git archive HEAD` em pasta temporária (o `.env` é ignorado pelo git e não vai junto). Criar ali um `.env` falso só com nomes fictícios: `SENTINELA_ISOLAMENTO_ENV`, `ORACLE_SENTINELA_FICTICIA`, `EMAIL_SENTINELA_FICTICIA`, `GEMINI_SENTINELA_FICTICIA`. **Nunca `ORACLE_SANDBOX`.** O teste tem de passar.
  3. Controle negativo: o mesmo procedimento com `git archive 673ceb1`. O teste tem de falhar com `adicionadas_n >= 1`, o que prova que a sentinela seria detectada.

## 5. Riscos

**Ordem de carga**
- Os pontos de entrada carregam antes do primeiro import do projeto, mas qualquer import de `tools.*` acima da linha de carga quebraria isso. Grep no aceite: nenhum `from tools`/`import tools` antes de `app.py:33` e de `main.py:18`.
- `override=False` muda a precedência: o shell passa a vencer o arquivo. Hoje `notificador.py:17` fazia o contrário em tempo de execução.
- A duplicação `tools.*` × `src.tools.*` continua (fica como item próprio). Sem carga no import, ela não repete o `.env`.

**Leitura no import (não na chamada)**

| Ponto | Risco depois da mudança | Mitigação |
|---|---|---|
| `oracle_dba.py:39` `AGENTDBA_LOG_DIR` | na produção, nenhum. Import direto fora do ponto de entrada usa `C:\AgentDBA\logs`; sem credencial, a resposta é ERRO_CONFIG | documentar |
| `gemini_router.py:22/27/28` (`GEMINI_API_KEY`, `genai.configure`, `GenerativeModel` no import) | na produção, nenhum. Em teste, importa sem chave (a simulação confirmou) | `GenerativeModel` no import fica como item próprio |
| `main.py:91` (cliente LLM no import) | em teste, deixa de herdar a `GEMINI_API_KEY` real | é uma melhoria |
| `app.py:569/578/592` (sidebar) | sem mudança; `app.py:33` roda a cada rerun | documentar que mudar um valor no `.env` exige reinício |
| `test_fluxo_cli.py:81` e `test_fluxo_web.py:127` (trocam `dotenv.load_dotenv`) | hoje a troca é ineficaz para módulos já importados na coleta. Depois passa a ser suficiente, porque só os pontos de entrada carregam | manter `from dotenv import load_dotenv` nos pontos de entrada |

**Outros**
- O `pytest -v -rs` pode não rodar se o Controle de Aplicativo bloquear a DLL do oracledb. Nesse caso o status do aceite é "não verificado", não "aprovado".
- Sandbox: a carga do conftest pode preencher credenciais reais **só** com `ORACLE_SANDBOX=1` vindo do shell. A guarda de `conftest.py:41-51` e `:114-120` continua valendo.

## Execução (após aprovação)

| # | Commit | Arquivos | Agente |
|---|---|---|---|
| 1 | `refactor: remove load_dotenv de módulo em src/tools e src/config` (D3) | `oracle_dba.py`, `executor.py`, `gemini_router.py`, `notificador.py`, `settings.py` | `mecanico` |
| 2 | `fix: remove load_dotenv(override=True) em tempo de chamada` (D4) | `notificador.py`, `gemini_router.py` | `mecanico` |
| 3 | `fix: carga única do .env nos pontos de entrada, sem ORACLE_SANDBOX do arquivo` (D1, D2) | `app.py`, `src/main.py` | sessão principal |
| 4 | `test: credenciais de sandbox só pelo conftest, com lista de permissão` (D5) | `tests/conftest.py`, `tests/test_executor.py`, `tests/test_privilegio_read.py`, `tests/test_privilegio_write_sandbox.py` | `mecanico` |
| 5 | `docs: isolamento do .env` | `docs/GOVERNANCA_LOG.md`, entregas | sessão principal |

- Commits sequenciais; nunca dois agentes em `oracle_dba.py`, `main.py` ou `app.py`.
- Conferência do `seguranca` antes do commit 3.
- O `verificador` roda `git status`, `pytest -q`, os greps e as verificações do passo 4, com saídas em `docs/entregas/isolamento_env/`.

Greps do aceite:
- nenhuma ocorrência de `load_dotenv|dotenv_values|find_dotenv` em `src/tools/` e `src/config/`;
- nenhuma ocorrência de `override=True`;
- `ORACLE_SANDBOX` em `app.py` e `src/` só nas linhas da D2.

## Fora de escopo (itens próprios)
- A duplicação `tools.*` × `src.tools.*`.
- O `GenerativeModel` criado no import de `gemini_router.py`.
- `test_oracle_kill.py:173`: o teste nunca conecta, então a comparação com `ORACLE_USER_KILL` não verifica nada.
- Tarefa 1.11-V2 (`docs/plans/1.11-V2.md`): aguarda aprovação. Faz sentido executar depois desta, para que o `pytest -q` entregue nela esteja verde.
