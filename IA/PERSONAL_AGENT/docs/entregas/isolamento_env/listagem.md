# Listagem de carregamento de .env (passo 1, somente leitura)

Modelo: Haiku 5.5 (claude-haiku-5-5). Branch item1/reaplicado, HEAD 673ceb1.
Escopo: nenhum arquivo do projeto editado; `.env` não lido; ORACLE_SANDBOX não definida; sem conexão Oracle; pytest não executado.
Valores de variáveis: omitidos. Apenas nomes.

## Comandos executados

- `git status --short` e `git rev-parse --short HEAD`: sem alteração em arquivos rastreados. Só entradas `??` já existentes.
- Grep (ripgrep) por `load_dotenv|dotenv_values|find_dotenv|dotenv` em `src/`, `app.py`, `tests/`.
- Grep por `os.getenv|os.environ|environ.get|BaseSettings|GOOGLE_API_KEY|GEMINI_API_KEY` em `src/` e `app.py`.
- Grep de linhas iniciadas em coluna 0 (nível de módulo) em `app.py`, `src/main.py`, `src/config/settings.py`, `src/tools/*.py`.
- Grep de `^\s*def` e `with st.sidebar` em `app.py`, `gemini_router.py`, `notificador.py`.
- Grep de `monkeypatch`, `setenv`, `delenv`, `skip`, `sandbox_only`, `ORACLE_*` em `tests/`.
- Leitura de trechos curtos (`sed -n`) de `tests/conftest.py`, `src/tools/oracle_dba.py`, `src/tools/executor.py`, `tests/test_executor.py`, `src/main.py`, `app.py`, `src/tools/__init__.py`.
- Leitura de fontes de terceiros em `site-packages` (`dotenv/main.py`, `google/generativeai/client.py`, `openai/lib/_client_auth.py`) via grep.

## A) Chamadas a load_dotenv / dotenv_values / find_dotenv (src/ e app.py)

Não há chamadas a `dotenv_values` nem `find_dotenv` em `src/` ou `app.py`.

| Arquivo:linha | Texto exato | Nível | Argumento |
|---|---|---|---|
| app.py:33 | `load_dotenv(ROOT_DIR / ".env")` | MÓDULO (import) | caminho explícito; override padrão (False) |
| src/config/settings.py:6 | `load_dotenv()` | MÓDULO (import) | sem argumento: busca `.env` subindo a partir do arquivo chamador |
| src/main.py:18 | `load_dotenv(ROOT_DIR / ".env")` | MÓDULO (import) | caminho explícito; override padrão (False) |
| src/tools/executor.py:35 | `load_dotenv()` | MÓDULO (import) | sem argumento |
| src/tools/executor.py:38 | `    load_dotenv(dotenv_path=env_personal_agent, override=False)` | MÓDULO, dentro de `if env_personal_agent.is_file():` (linha 37) | caminho explícito; override=False |
| src/tools/gemini_router.py:19 | `load_dotenv()` | MÓDULO (import) | sem argumento |
| src/tools/gemini_router.py:37 | `    load_dotenv(override=True)` | DENTRO DE FUNÇÃO: `analisar_log_complexo` (def na linha 31) | sem caminho; override=True (sobrescreve os.environ a cada chamada) |
| src/tools/notificador.py:12 | `load_dotenv()` | MÓDULO (import) | sem argumento |
| src/tools/notificador.py:17 | `    load_dotenv(override=True)` | DENTRO DE FUNÇÃO: `enviar_alerta_email` (def na linha 15) | sem caminho; override=True (sobrescreve a cada envio) |
| src/tools/oracle_dba.py:33 | `load_dotenv(ROOT_DIR / ".env")` | MÓDULO (import) | caminho explícito; override padrão (False) |

Observação: `src/tools/__init__.py` não chama dotenv, mas importa `src.tools.oracle_dba` (linha 2), `src.tools.gemini_router` (linha 16) e `src.tools.notificador` (linha 20). Qualquer `import` de `src.tools.*` ou `tools.*` executa esses três módulos, portanto dispara os carregamentos de oracle_dba:33, gemini_router:19 e notificador:12 antes do código do módulo pedido.

## B) Leituras de variável de ambiente

### B1. Nível de módulo (executam no import)

| Arquivo:linha | Texto exato | Variável | Constante |
|---|---|---|---|
| src/config/settings.py:13 | `AGENT_NAME = os.getenv("AGENT_NAME", "PersonalAgent")` | AGENT_NAME | AGENT_NAME |
| src/config/settings.py:14 | `MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-pro")` | MODEL_NAME | MODEL_NAME |
| src/config/settings.py:15 | `LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")` | LOG_LEVEL | LOG_LEVEL |
| src/tools/gemini_router.py:22 | `GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")` | GEMINI_API_KEY | GEMINI_API_KEY |
| src/tools/gemini_router.py:27 | `MODELO_GEMINI_PADRAO = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")` | GEMINI_MODEL | MODELO_GEMINI_PADRAO |
| src/tools/oracle_dba.py:39 | `DIRETORIO_LOG_APROVACAO = Path(os.getenv("AGENTDBA_LOG_DIR") or DIRETORIO_LOG_PADRAO)` | AGENTDBA_LOG_DIR | DIRETORIO_LOG_APROVACAO (e, via linha 42, CAMINHO_LOG_APROVACAO_PADRAO) |
| app.py:569 (dentro de `with st.sidebar:`, linha 551, corpo do script Streamlit, sem def) | `    gemini_key_cfg = os.getenv("GEMINI_API_KEY", "")` | GEMINI_API_KEY | gemini_key_cfg |
| app.py:578 (mesmo bloco) | `    dsn_atual = os.getenv("ORACLE_DSN", "NAO_CONFIGURADO")` | ORACLE_DSN | dsn_atual |
| app.py:592 (mesmo bloco) | `    email_dest = os.getenv("EMAIL_DESTINATARIO", "")` | EMAIL_DESTINATARIO | email_dest |

Notas:
- app.py:572 lê GEMINI_MODEL dentro de f-string de `st.markdown` (bloco do sidebar, nível de script). Não é constante.
- src/main.py:91 (`client, MODELO = _inicializar_cliente_coordenador()`) é chamada de módulo. Executa no import e, se o Ollama estiver offline, lê GEMINI_API_KEY em src/main.py:81 (dentro da função). Leitura indireta, nível de módulo.
- src/tools/gemini_router.py:28 (`model = genai.GenerativeModel(MODELO_GEMINI_PADRAO)`) é construção de módulo, sem leitura direta de env. Pode acionar leitura de env da biblioteca (ver E).
- Não há leitura de env em nível de módulo em src/tools/executor.py, src/tools/notificador.py, src/tools/registry.py nem src/main.py (fora da chamada indireta acima).

### B2. Dentro de função (contagem e nomes)

| Arquivo | Reads | Nomes de variável |
|---|---|---|
| src/tools/executor.py (função `executar_script`, def linha 556) | 8 | ORACLE_USER_READ, ORACLE_PASSWORD_READ, ORACLE_USER_MUT, ORACLE_PASSWORD_MUT, ORACLE_DSN, ORACLE_CALL_TIMEOUT_MS, ORACLE_SELECT_LIMIT, ORACLE_LOB_LIMIT |
| src/tools/oracle_dba.py (5 funções: coletar_sessoes_ativas, coletar_top_sql, coletar_plano_execucao, consultar_alvo_sessao_diag, matar_sessao_oracle) | 15 | ORACLE_USER_DIAG (4x), ORACLE_PASSWORD_DIAG (4x), ORACLE_DSN (5x), ORACLE_USER_KILL (1x), ORACLE_PASSWORD_KILL (1x) |
| src/tools/registry.py (3 funções: obter_diretorio_raiz, obter_caminho_registro, obter_caminho_scripts_dir) | 3 | PERSONAL_AGENT_ROOT, SCRIPTS_REGISTRY_PATH, SCRIPTS_DIR_PATH |
| src/tools/gemini_router.py (`analisar_log_complexo`) | 1 | GEMINI_API_KEY (linha 38) |
| src/tools/notificador.py (`enviar_alerta_email`) | 3 | EMAIL_REMETENTE, EMAIL_SENHA_APP, EMAIL_DESTINATARIO |
| src/main.py (`_inicializar_cliente_coordenador`) | 1 | GEMINI_API_KEY (linha 81) |
| app.py (`obter_cliente_llm`, def linha 108) | 2 | MODEL_NAME (linha 116), GEMINI_API_KEY (linha 119) |

## C) Ordem de import nos pontos de entrada

### app.py

| Linha | Conteúdo |
|---|---|
| 9-15 | stdlib (json, logging, os, socket, sys, pathlib, typing) |
| 17 | `import pandas as pd` |
| 18 | `import streamlit as st` |
| 19 | `from dotenv import load_dotenv` |
| 20 | `from openai import OpenAI` |
| 25-27 | BASE_DIR / SRC_DIR / ROOT_DIR |
| 29-31 | laço que insere ROOT_DIR e SRC_DIR em sys.path |
| **33** | **`load_dotenv(ROOT_DIR / ".env")`** |
| 52 | `from tools.os_tools import (` (primeiro import do projeto) |
| 57 | `from tools.oracle_dba import (` |
| 69 | `from tools.gemini_router import (` |
| 73 | `from tools.rag_search import (` |

Situação: o carregamento (33) já está antes de qualquer import do projeto (52). Não há carregamento "tarde" em app.py. A ressalva é que o primeiro import do projeto aciona `tools/__init__.py`, que reimporta `src.tools.*` e repete os carregamentos de oracle_dba, gemini_router e notificador (ver A).

### src/main.py

| Linha | Conteúdo |
|---|---|
| 2-7 | stdlib (json, logging, os, socket, sys, pathlib) |
| 8 | `from dotenv import load_dotenv` |
| 9 | `from openai import OpenAI` |
| 12-13 | SRC_DIR / ROOT_DIR |
| 14-16 | laço de sys.path |
| **18** | **`load_dotenv(ROOT_DIR / ".env")`** |
| 39 | `from tools.os_tools import (` (primeiro import do projeto) |
| 46 | `from tools.oracle_dba import (` |
| 58 | `from tools.gemini_router import (` |
| 62 | `from tools.rag_search import (` |
| 91 | `client, MODELO = _inicializar_cliente_coordenador()` (chamada de módulo, após os imports) |

Situação: o carregamento (18) já está antes do primeiro import do projeto (39). Ponto de inserção "antes de qualquer import do projeto": linha 18 (já ocupada). Diferença a registrar para o passo 2: `src/main.py` importa `tools.*` (sem prefixo `src.`), enquanto `tests/` e `app.py`/`src/tools/executor.py` usam `src.tools.*`. Isso gera módulos duplicados com carregamentos repetidos.

## D) Testes (tests/, inclusive conftest.py)

### D1. Chamadas a load_dotenv

| Arquivo:linha | Texto exato | Nível |
|---|---|---|
| tests/test_executor.py:16 | `from dotenv import load_dotenv` | import |
| tests/test_executor.py:24 | `load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)` | MÓDULO, executada na coleta do pytest (antes de `from src.tools.executor` na linha 26) |
| tests/test_privilegio_read.py:10 | `    load_dotenv(dotenv_path=env_path, override=False)` | MÓDULO, dentro de `if env_path.is_file():` (linha 9), executada na coleta |
| tests/test_privilegio_write_sandbox.py:9 | `    load_dotenv(dotenv_path=env_path, override=False)` | MÓDULO, dentro de `if env_path.is_file():` (linha 8), executada na coleta |

Efeito: essas três linhas leem `.env` em toda execução de `pytest`, mesmo sem ORACLE_SANDBOX. Os testes sandbox_only são pulados depois, mas o carregamento já ocorreu na coleta.

conftest.py não chama load_dotenv. Ele define variáveis de processo no import (sem monkeypatch):
- tests/conftest.py:10 `ORACLE_SANDBOX_DO_OPERADOR = os.environ.get("ORACLE_SANDBOX")` (snapshot antes de qualquer import de produção)
- tests/conftest.py:21 `os.environ["AGENTDBA_LOG_DIR"] = _DIR_LOG_TESTE`
- tests/conftest.py:28 `os.environ["SCRIPTS_REGISTRY_PATH"] = str(test_registry_path)`
- tests/conftest.py:43-51 e 114-120: governança que aborta a sessão se ORACLE_SANDBOX mudar.
- tests/conftest.py:149-150 `if os.getenv("ORACLE_SANDBOX") != "1": pytest.skip(...)` (gate de sandbox_only).

### D2. monkeypatch / setenv / delenv de variáveis ORACLE_*, EMAIL_*, GEMINI_*, AGENTDBA_*, SCRIPTS_*

| Arquivo:linha | Texto exato (nomes) | Teste |
|---|---|---|
| tests/test_fluxo_cli.py:81-82 | `import dotenv` / `mp.setattr(dotenv, "load_dotenv", lambda *a, **k: False)` | fixture `main_cli` (linha 78, scope module) |
| tests/test_fluxo_cli.py:85-90 | setenv ORACLE_USER_DIAG, ORACLE_PASSWORD_DIAG, ORACLE_USER_KILL, ORACLE_PASSWORD_KILL, ORACLE_DSN; delenv ORACLE_SANDBOX | `main_cli` |
| tests/test_fluxo_web.py:118-124 | setenv ORACLE_USER_DIAG, ORACLE_PASSWORD_DIAG, ORACLE_USER_KILL, ORACLE_PASSWORD_KILL, ORACLE_DSN, EMAIL_DESTINATARIO, GEMINI_API_KEY | `_montar` (linha 115), usada por todos os test_web_* |
| tests/test_fluxo_web.py:126-129 | `monkeypatch.setattr(dotenv, "load_dotenv", ...)` | `_montar` |
| tests/test_oracle_kill.py:135 | `monkeypatch.delenv("ORACLE_USER_DIAG", raising=False)` | test_ausencia_oracle_user_diag_sem_conexao (linha 129) |
| tests/test_oracle_kill.py:160 | `monkeypatch.delenv("ORACLE_USER_KILL", raising=False)` | test_ausencia_oracle_user_kill_sem_conexao (linha 154) |
| tests/test_oracle_kill.py:173 | `if user_conectado == os.getenv("ORACLE_USER_KILL"):` | test_aprovacao_negada_ou_sem_identificacao_sem_chamada_kill (linha 167) |
| tests/test_oracle_kill.py:270-274 | setenv ORACLE_USER_DIAG, ORACLE_PASSWORD_DIAG, ORACLE_USER_KILL, ORACLE_PASSWORD_KILL, ORACLE_DSN | fixture `ambiente_fake` (linha 267) |
| tests/test_executor.py:471 | `monkeypatch.delenv("ORACLE_USER_READ", raising=False)` | test_t19_oracle_user_read_ausente_com_select (linha 469) |
| tests/test_item1_intencao.py:505, 507 | `monkeypatch.delenv("ORACLE_USER_DIAG")` / `("ORACLE_USER_KILL")` | test_resultado_por_caso_de_falha (linha 468) |
| tests/test_item1_intencao.py:1019-1021 | setenv ORACLE_USER_KILL, EMAIL_SENHA_APP, GEMINI_API_KEY, ORACLE_PREFIXO_TESTE, OUTRA_VAR | test_env_de_subprocesso_sem_segredos (linha 1018) |
| tests/test_item1_intencao.py:865-871 | `_env_sem_segredos` remove prefixos ORACLE_, EMAIL_, GEMINI_ | helper usado por testes de subprocesso |
| tests/test_item1_intencao.py:994-996 | módulo falso `dotenv` com `load_dotenv = lambda *a, **k: False` (dentro de string de subprocesso, `python -I`) | _CODIGO_FILHO_IMPORT (linha ~990) |
| tests/test_item1_intencao.py:1008 | `env = ...remover=("AGENTDBA_LOG_DIR",)` | test de subprocesso (ligado a 1028 e 1036) |
| tests/test_item1_intencao.py:1030 | `{"AGENTDBA_LOG_DIR": str(alvo)}` | test_import_nao_cria_a_pasta_do_log (linha 1028) |
| tests/test_item1_intencao.py:1044-1045 | `os.environ["AGENTDBA_LOG_DIR"]` | test_conftest_define_diretorio_antes_do_import (linha 1043) |
| tests/test_corpus_adversarial.py:110 | `monkeypatch.setenv("SCRIPTS_DIR_PATH", str(CORPUS_DIR))` | test_l3_executar_script_adversarial_sem_conexao (linha 87) |
| tests/conftest.py:21, 28 | ver D1 (os.environ direto, sem monkeypatch) | sessão inteira |

### D3. Testes que dependem de credenciais do .env (ou dão skip quando faltam)

| Arquivo:linha | Texto exato (nomes) | Teste | Condição |
|---|---|---|---|
| tests/test_executor.py:36-58 | `setup_banco_teste` (autouse, scope session): lê ORACLE_USER_MUT, ORACLE_PASSWORD_MUT, ORACLE_DSN; `pytest.skip("Credenciais Oracle não configuradas no .env...")` na linha 50; default `ORACLE_USER_READ` = "startup_read" na linha 90 | fixture de sessão | retorna sem ação se ORACLE_SANDBOX != "1"; com ORACLE_SANDBOX=1 e credencial ausente, pula |
| tests/test_executor.py:257-259 | `os.getenv("ORACLE_USER_MUT")`, `ORACLE_PASSWORD_MUT`, `ORACLE_DSN` | test_t9_bind_injetado_sem_alteracao_statement_v_sql (linha 255) | sandbox_only |
| tests/test_executor.py:367-369 | idem | test_t13_falha_no_meio_de_dml_rollback (linha 365) | sandbox_only |
| tests/test_oracle_kill.py:678-680 | `ORACLE_USER_DIAG`, `ORACLE_PASSWORD_DIAG`, `ORACLE_DSN` | test_sandbox_kill_sessao_valida_encerrada (linha 676) | sandbox_only |
| tests/test_oracle_kill.py:705-711 | sem leitura direta; chama matar_sessao_oracle, que lê ORACLE_*_KILL/DIAG de src | test_sandbox_kill_alvo_nao_encontrado (linha 706) | sandbox_only |
| tests/test_oracle_kill.py:724-726 | `ORACLE_USER_MUT`, `ORACLE_PASSWORD_MUT`, `ORACLE_DSN` | test_sandbox_kill_propria_sessao_ou_usuario_protegido (linha 722) | sandbox_only |
| tests/test_oracle_kill.py:750-752 | `ORACLE_USER_DIAG`, `ORACLE_PASSWORD_DIAG`, `ORACLE_DSN` | test_sandbox_privilegio_negativo_startup_diag (linha 748) | sandbox_only |
| tests/test_oracle_kill.py:769-771 | `ORACLE_USER_KILL`, `ORACLE_PASSWORD_KILL`, `ORACLE_DSN` | test_sandbox_privilegio_negativo_startup_kill (linha 767) | sandbox_only |
| tests/test_privilegio_read.py:37-43 | `ORACLE_USER_READ`, `ORACLE_PASSWORD_READ`, `ORACLE_DSN`; `assert` (falha, não pula) com mensagem "deve estar configurada no .env" | test_privilegio_read_sem_permissoes_de_escrita (linha 35) | sandbox_only |
| tests/test_privilegio_write_sandbox.py:27-33, 57-58 | `ORACLE_USER_READ`, `ORACLE_PASSWORD_READ`, `ORACLE_DSN`, `ORACLE_USER_MUT`, `ORACLE_PASSWORD_MUT`; `pytest.skip` com ORACLE_SANDBOX != "1" (linha 25) | test_privilegio_write_insert_rejeitado_sandbox (linha 22) | sandbox_only |

Sem skip por credencial ausente nos testes não sandbox (grep de `skip` em tests/ mostra skips apenas em test_executor.py:23-24/50, conftest.py:150, test_privilegio_write_sandbox.py:25 e test_executor.py:43). Testes não sandbox que usam ORACLE_* fixam as variáveis via monkeypatch (D2) ou falham antes de precisar de credencial (ex.: test_executor.py:471 test_t19). Não foi verificado, nesta etapa, se algum teste não sandbox depende de valor vindo do `.env` real.

### D4. Fixtures que neutralizam load_dotenv (risco a registrar no passo 2)

tests/test_fluxo_cli.py:81-82 e tests/test_fluxo_web.py:127-129 trocam `dotenv.load_dotenv` por lambda no nível do módulo `dotenv`. Como os módulos de produção fazem `from dotenv import load_dotenv` no import, a troca só vale para módulos importados depois da fixture. Pela coleta (D1, test_executor.py:26 e test_corpus_adversarial.py:13 importam `src.tools.executor` na coleta), os carregamentos de produção já ocorreram antes dessas fixtures. Inferido do código, não executado.

## E) Leitura implícita por terceiros ou módulos do projeto

| Origem | Variáveis | Quando | Evidência |
|---|---|---|---|
| python-dotenv (biblioteca) | nenhuma automática | só quando chamada | `dotenv/main.py:372-373` (find_dotenv usa frame do chamador quando `load_dotenv()` não recebe caminho) |
| pytest-dotenv (plugin) | — | não instalado | site-packages contém `dotenv` e `python_dotenv`, sem `pytest_dotenv`. pytest.ini só define o marker sandbox_only |
| google-generativeai | GEMINI_API_KEY, GOOGLE_API_KEY | ao criar o cliente padrão (`google/generativeai/client.py:191` e `:196`) | src/tools/gemini_router.py:28 cria `genai.GenerativeModel` no import, o que pode disparar essa criação. Não verificado em runtime |
| openai (SDK) | OPENAI_API_KEY, OPENAI_BASE_URL | só quando o argumento não é passado ao construir `OpenAI()` (`openai/lib/_client_auth.py:179` e `:228`) | src/main.py:91 (chamada de módulo que constrói `OpenAI`) e app.py:108-129 passam api_key e base_url explícitos |
| pydantic | nenhuma | — | src/tools/registry.py usa BaseModel; não há BaseSettings no projeto (grep sem resultado) |
| src/config/settings.py | AGENT_NAME, MODEL_NAME, LOG_LEVEL; carrega .env em :6 | só se importado | nenhum import de `config.settings` ou `src.config` em src/, app.py ou tests/. Módulo não usado |
| src/tools/__init__.py | nenhuma direta | ao importar qualquer `src.tools.*` | importa oracle_dba (linha 2), gemini_router (linha 16), notificador (linha 20), disparando seus carregamentos |
| oracledb, streamlit | — | não verificado | não inspecionado nesta etapa |

## Itens para o passo 2 (apenas registro, sem decisão)

1. Carregamento do .env em 10 pontos de produção/teste (app.py:33, src/config/settings.py:6, src/main.py:18, src/tools/executor.py:35 e :38, src/tools/gemini_router.py:19 e :37, src/tools/notificador.py:12 e :17, src/tools/oracle_dba.py:33, tests/test_executor.py:24, tests/test_privilegio_read.py:10, tests/test_privilegio_write_sandbox.py:9).
2. Dois carregamentos com override=True em tempo de execução: gemini_router.py:37 e notificador.py:17 (sobrescrevem os.environ a cada chamada).
3. Dois prefixos de import distintos (`tools.*` e `src.tools.*`) geram módulos duplicados e carregamentos repetidos.
4. Testes de sandbox leem credenciais diretamente de os.environ; o carregamento vem de tests/test_executor.py:24 e dos módulos de produção.
5. Teste test_isolamento_env.py:42 já caracteriza o comportamento: importar módulos de teste não pode alterar os.environ (executa em subprocesso com ORACLE_*, EMAIL_*, GEMINI_* removidos).
