# Revisão Adversarial — Isolamento do `.env` (`673ceb1..d05577e`)

## 1. Diff conferido

- Comando: `git diff 673ceb1 d05577e -- src/ app.py tests/conftest.py`
- Linhas: `224` (`9382` bytes em LF)
- SHA-256 obtido: `a5f6af6e61f338a8cd60269a31fa4ff6827f357f4da1741618a3bf7b5c022aa4`
- Conferência: **bate exatamente** com o informado em `docs/entregas/revisao_fases_1_2/prompt_gemini.md`.
- Execução `python -m pytest -q` (sem `ORACLE_SANDBOX`): `199 passed, 16 skipped, 13 warnings in 59.64s`.

---

## 2. Achados

### B4 — Recarga do `.env` a cada rerun da Web injeta novas credenciais Oracle/SMTP no meio do processo
- **Veredito:** VIOLADO
- **Severidade:** média — quebra I1 ("uma vez por processo"), I2 ("Nada recarrega o `.env` depois da subida") e I6 para chaves ausentes na subida, permitindo que `ORACLE_USER_KILL`, `ORACLE_PASSWORD_KILL`, `ORACLE_DSN` ou `EMAIL_*` entrem em vigor durante a sessão sem reinício.
- **Local:** `app.py:38-43` (especialmente `app.py:39`)
- **Cenário:** A Web sobe com `.env` contendo apenas credenciais `DIAG` (sem `ORACLE_USER_KILL`/`ORACLE_PASSWORD_KILL` ou sem `EMAIL_*`, modo diagnóstico apenas). Com o servidor rodando — inclusive entre a preparação do painel HITL e o clique em `"✅ Aprovar Execução"` — novas chaves `ORACLE_USER_KILL` e `ORACLE_PASSWORD_KILL` (ou `EMAIL_*`) são adicionadas ao `.env`. No próximo rerun do Streamlit, `app.py:39` executa `load_dotenv(ROOT_DIR / ".env", override=False)` novamente e carrega essas chaves ausentes em `os.environ`, habilitando o kill ou alterando o envio SMTP no meio do processo sem reinício.
- **Reprodução sem Oracle e sem `.env` real:** Em subprocesso isolado sem credenciais (mesmo modelo de `tests/test_carga_env_entrada.py`), redirecionar `dotenv.load_dotenv` para `tmp_path / "ficticio.env"`, gravar apenas `SENTINELA=1`, executar `at = AppTest.from_file("app.py"); at.run()`, acrescentar `ORACLE_USER_KILL=kill_tardio` a `ficticio.env` e rodar `at.run()`: após o 2º rerun, `os.environ.get("ORACLE_USER_KILL") == "kill_tardio"`.
- **Correção sugerida:** Proteger o bloco `app.py:38-43` com uma sentinela de processo (ex.: `if not getattr(sys, "_personal_agent_env_loaded", False): ...; sys._personal_agent_env_loaded = True`), garantindo carga realmente única por processo na Web.

### C1 — Exceção no meio de `load_dotenv` deixa `ORACLE_SANDBOX` do arquivo em `os.environ` e a promove a "do shell" na Web
- **Veredito:** VIOLADO
- **Severidade:** média — viola I3 de forma determinística (em uma única aba, sem corrida entre abas), pois `load_dotenv` grava chave a chave em `os.environ` antes do `del` e não há `try/finally`.
- **Local:** `app.py:38-43` e `src/main.py:23-28`
- **Cenário:** O `.env` contém `ORACLE_SANDBOX=1` em uma linha anterior a uma linha cujo valor provoca `ValueError` em `os.environ[k] = v` (ex.: byte NUL `\x00` no valor) ou ocorre `StopException`/`KeyboardInterrupt` durante o laço de `dotenv.main.DotEnv.set_as_environment_variables`. `os.environ["ORACLE_SANDBOX"] = "1"` é executada antes da exceção e o `del os.environ["ORACLE_SANDBOX"]` (`app.py:42`, `src/main.py:27`) não roda. No Streamlit, o `ScriptRunner` captura a exceção sem derrubar o servidor; no rerun seguinte, `_ORACLE_SANDBOX_DO_SHELL = "ORACLE_SANDBOX" in os.environ` (`app.py:38`) passa a ser `True`, mantendo `ORACLE_SANDBOX` vinda do arquivo permanentemente no processo e sem emitir WARNING.
- **Reprodução sem Oracle e sem `.env` real:**
  ```powershell
  python -c "import io, os; from dotenv import load_dotenv; s = io.StringIO('FOO_FIRST=1\nFOO_BAD=abc\x00def\n');
  try: load_dotenv(stream=s, override=False)
  except ValueError as e: print(type(e).__name__, 'FOO_FIRST in environ:', 'FOO_FIRST' in os.environ)"
  ```
  Saída verificada: `ValueError FOO_FIRST in environ: True`. Com o mesmo conteúdo usando `ORACLE_SANDBOX=1` em `.env` fictício de subprocesso isolado sem credenciais executando `AppTest.from_file("app.py")`, a variável sobrevive à exceção e é aceita como "do shell" no rerun seguinte.
- **Correção sugerida:** Envolver `load_dotenv(ROOT_DIR / ".env", override=False)` em `try ... finally` que sempre remove `ORACLE_SANDBOX` quando `not _ORACLE_SANDBOX_DO_SHELL` (`os.environ.pop("ORACLE_SANDBOX", None)`), combinada com carga única por processo em `app.py`.

### D6 — Testes novos não detectam mutações diretas nas garantias I1, I2, I3, I4 e I5
- **Veredito:** VIOLADO
- **Severidade:** média — todos os quatro novos arquivos de teste (mais `test_isolamento_env.py`) passam diante de mutações de uma linha em produção ou no `conftest.py` que violam as garantias declaradas.
- **Local:** `tests/test_conftest_sandbox_env.py:8-36`, `tests/test_env_em_execucao.py:60-101`, `tests/test_carga_env_entrada.py:19-105`, `tests/test_guard_sessao_sandbox.py:14-73`, `tests/test_isolamento_env.py:24`
- **Cenário:** Mutações não detectadas por arquivo de teste:
  1. `tests/test_conftest_sandbox_env.py`: substituir `tests/conftest.py:62-66` por `load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)` (ignorando `credenciais_sandbox_do_env`) ou remover `and v` em `tests/conftest.py:58` (aceitando valores vazios) — o teste só chama a função pura, sem testar valor vazio (`KEY=`) nem a ligação real no módulo `conftest.py`.
  2. `tests/test_env_em_execucao.py`: reintroduzir `load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)` com caminho explícito em `src/tools/notificador.py:12` (não passa por `find_dotenv`, único gancho mockado na linha `70`), ou reintroduzir `load_dotenv(override=True)` em `src/tools/gemini_router.py:27` (`analisar_log_complexo` nunca é invocada pelo teste).
  3. `tests/test_carga_env_entrada.py`: mover `load_dotenv` em `app.py`/`src/main.py` para **depois** dos imports `from tools.*` (violando I1 — o teste não confere `tools.oracle_dba.DIRETORIO_LOG_APROVACAO` nem `tools.gemini_router.GEMINI_API_KEY`), **ou** mover o `WARNING` de `ORACLE_SANDBOX` para **antes** de `logging.basicConfig` (o `_Captura()` anexado à raiz na linha `46` já torna `basicConfig` no-op e captura o warning mesmo quebrando `auditoria_oracle.log`).
  4. `tests/test_guard_sessao_sandbox.py`: apagar o corpo de `guard_oracle_sandbox` (`tests/conftest.py:77-91`) ou fixar `ORACLE_SANDBOX_DO_OPERADOR = None` (`tests/conftest.py:10`) — o teste só invoca `conftest.pytest_sessionfinish` (`linha 33`) com atributos injetados via `monkeypatch` (`linha 24`).
  5. `tests/test_isolamento_env.py`: reintroduzir `load_dotenv()` no topo de `src/config/settings.py` ou `tests/test_privilegio_read.py`/`tests/test_privilegio_write_sandbox.py` — a linha `24` importa apenas `("test_executor", "test_oracle_kill", "test_item1_intencao")`.
- **Reprodução sem Oracle e sem `.env` real:** Extrair `git archive HEAD` para `%TEMP%`, aplicar qualquer uma das mutações acima (com `.env` fictício de sentinelas) e rodar `python -m pytest -q` sobre o arquivo de teste correspondente: o teste continua passando.
- **Correção sugerida:** (1) Adicionar caso com valor vazio (`ORACLE_DSN=`) e teste em subprocesso da carga de `conftest.py`; (2) em `test_env_em_execucao.py`, interceptar `dotenv.load_dotenv` e `dotenv.dotenv_values` (falhando o teste se chamados) e exercitar `analisar_log_complexo`; (3) em `test_carga_env_entrada.py`, verificar leitura de import (ex.: `AGENTDBA_LOG_DIR` em `tools.oracle_dba.DIRETORIO_LOG_APROVACAO`) e testar a ordem `basicConfig` antes do `WARNING`; (4) testar `guard_oracle_sandbox` em `test_guard_sessao_sandbox.py`; (5) adicionar `src.config.settings` e `test_privilegio_*` à lista de `test_isolamento_env.py:24`.

### A3 — Duplicação `tools.*` × `src.tools.*` permite que as duas cópias congelem estados diferentes de `os.environ`
- **Veredito:** VIOLADO
- **Severidade:** média — após remover `load_dotenv` dos módulos de `src/tools/`, qualquer import de `src.tools.*` anterior ao ponto de entrada fixa constantes de import (ex.: `DIRETORIO_LOG_APROVACAO`, `GEMINI_API_KEY`) com o ambiente pré-carga enquanto `tools.*` fixa os valores pós-`.env` no mesmo processo.
- **Local:** `app.py:29-31,39,66-86`, `src/main.py:14-16,24,53-75`, `src/tools/os_tools.py:5`, `src/tools/__init__.py:2-24`, `src/tools/oracle_dba.py:34-37` e `src/tools/gemini_router.py:18-24`
- **Cenário:** Se `src.tools.oracle_dba` (ou `src.tools.os_tools`, que importa `src.tools.payloads` e dispara `src/tools/__init__.py`) for importado antes de `main.py:24` ou `app.py:39` (como ocorre na própria suíte pytest via `tests/conftest.py:143`), `src.tools.oracle_dba.DIRETORIO_LOG_APROVACAO` recebe `C:\AgentDBA\logs` (ou o valor pré-carga) e `src.tools.gemini_router.GEMINI_API_KEY` recebe `""`, enquanto a cópia `tools.oracle_dba`/`tools.gemini_router` importada depois da carga do `.env` recebe os valores do `.env`, criando duas cópias com configuração divergente no mesmo processo.
- **Reprodução sem Oracle e sem `.env` real:** Em subprocesso isolado sem credenciais com `.env` fictício contendo `AGENTDBA_LOG_DIR=<tmp>/dir_env`, importar `src.tools.oracle_dba`, depois importar `main` com `dotenv.load_dotenv` redirecionado para o fictício e `socket.create_connection` bloqueado: `src.tools.oracle_dba.DIRETORIO_LOG_APROVACAO != tools.oracle_dba.DIRETORIO_LOG_APROVACAO`.
- **Correção sugerida:** Padronizar imports de `app.py` e `src/main.py` em `src.tools.*` (removendo `SRC_DIR` de `sys.path`) e/ou resolver `DIRETORIO_LOG_APROVACAO` em função chamada em tempo de execução.

### B3 — Variável obsoleta no perfil do Windows/shell vence o `.env` silenciosamente
- **Veredito:** VIOLADO
- **Severidade:** média — uma credencial ou `ORACLE_DSN` antiga esquecida no perfil do Windows (ex.: banco de produção) prevalece sobre `.env` (ex.: homologação) sem nenhum registro de alerta; a mitigação puramente manual não impede o erro operacional silencioso.
- **Local:** `app.py:39` e `src/main.py:24`
- **Cenário:** O ambiente do usuário Windows possui `ORACLE_DSN=prod:1521/PROD` (ou `ORACLE_USER_KILL` antigo), enquanto `ROOT_DIR / ".env"` define `ORACLE_DSN=homol:1521/HOMOL`. `load_dotenv(ROOT_DIR / ".env", override=False)` mantém o valor do perfil silenciosamente, sem logar nem exibir qualquer aviso de sobrescrita.
- **Reprodução sem Oracle e sem `.env` real:** Em subprocesso isolado com `ORACLE_DSN=dsn_perfil` no `env` e `.env` fictício contendo `ORACLE_DSN=dsn_arquivo`, importar `main` (com `load_dotenv` redirecionado e rede bloqueada): `os.environ["ORACLE_DSN"] == "dsn_perfil"` e nenhum WARNING é emitido.
- **Correção sugerida:** Após `logging.basicConfig`, inspecionar em memória as chaves de `ROOT_DIR / ".env"` que já existiam em `os.environ` com valor diferente (em especial `ORACLE_*`, `AGENTDBA_LOG_DIR`, `EMAIL_*`) e emitir um `WARNING` citando apenas os nomes das chaves sombreadas (nunca os valores).

### C2 — Heurística `"ORACLE_SANDBOX" in os.environ` é enganada por herança de processo pai/perfil e por rerun pós-exceção na Web
- **Veredito:** VIOLADO
- **Severidade:** baixa — em produção a variável não é lida hoje, mas o teste não distingue definição explícita para a invocação atual de variável herdada de terminal pai/perfil persistente (`setx`) nem de resíduo deixado em `os.environ` por rerun abortado (C1). *(Valor vazio `ORACLE_SANDBOX=""` no shell não ativa sandbox pois `override=False` preserva `""`; `python.envFile` do VS Code já consta em `R-F2-2`.)*
- **Local:** `app.py:38`, `src/main.py:23` e `tests/conftest.py:10`
- **Cenário:** (a) Após uma exceção em `load_dotenv` no rerun 1 da Web (C1), no rerun 2 `app.py:38` avalia `_ORACLE_SANDBOX_DO_SHELL = True` para a variável que veio do arquivo; (b) uma variável `ORACLE_SANDBOX` definida anteriormente no mesmo shell ou no perfil do Windows é herdada por execuções posteriores de `pytest` ou `app.py` e aceita como autorização explícita da sessão atual.
- **Reprodução sem Oracle e sem `.env` real:** Para (a), reproduzir C1 em dois reruns de `AppTest`. Para (b), definir `ORACLE_SANDBOX=0` num processo pai e disparar subprocesso de `main` com `.env` fictício contendo `ORACLE_SANDBOX=1`: `src/main.py:23` marca `_ORACLE_SANDBOX_DO_SHELL = True` sem WARNING.
- **Correção sugerida:** Resolver C1 com `try/finally` + carga única por processo em `app.py`; para o pytest, exigir também opt-in explícito por invocação (ex.: flag de CLI `--sandbox`) em item futuro.

### C3 — WARNING de descarte de `ORACLE_SANDBOX` é perdido se o logger raiz já estiver configurado e não é exibido ao operador
- **Veredito:** VIOLADO
- **Severidade:** baixa — em subida limpa de CLI/Web nenhuma dependência pré-configura o logger raiz (verificado: `root.handlers == []`) e o texto não expõe nenhum valor, mas qualquer configuração prévia do logger raiz (`NullHandler` ou nível `>= ERROR`) transforma `basicConfig` em no-op e suprime silenciosamente o WARNING; além disso, em subida normal o aviso vai apenas a `auditoria_oracle.log` (sem console/UI).
- **Local:** `app.py:49-63` e `src/main.py:35-50`
- **Cenário:** Um wrapper ou importador executa `logging.basicConfig(level=logging.ERROR)` (ou adiciona `NullHandler`) antes de importar `main`; `src/main.py:35` vira no-op e `logging.getLogger(__name__).warning(...)` (`src/main.py:48`) é descartado sem saída em arquivo nem em `stderr`. Em execução normal, o operador da Web/CLI não vê o aviso na tela.
- **Reprodução sem Oracle e sem `.env` real:** Em subprocesso isolado sem credenciais, chamar `logging.basicConfig(level=logging.ERROR)` antes de importar `main` com `.env` fictício contendo `ORACLE_SANDBOX=1` (rede bloqueada): nenhum WARNING aparece em `stderr` nem em log.
- **Correção sugerida:** Além do `logger.warning`, emitir aviso fixo (sem o valor) em `sys.stderr` na CLI e via `st.warning` na Web quando `_ORACLE_SANDBOX_DESCARTADA` for `True`.

### D3 — Três testes de `ERRO_CONFIG` passaram a passar por acaso sem o `.env` real
- **Veredito:** VIOLADO
- **Severidade:** baixa — não gera vazamento, mas enfraquece a cobertura de regressão de `ERRO_CONFIG` por ausência de `ORACLE_USER_*`.
- **Local:** `tests/test_oracle_kill.py:129-165` (`test_ausencia_oracle_user_diag_sem_conexao`, `test_ausencia_oracle_user_kill_sem_conexao`) e `tests/test_executor.py:464-472` (`test_t19_oracle_user_read_ausente_com_select`)
- **Cenário:** Os três testes apenas removem `ORACLE_USER_DIAG`, `ORACLE_USER_KILL` ou `ORACLE_USER_READ` com `monkeypatch.delenv(..., raising=False)`, sem definir `ORACLE_PASSWORD_*` nem `ORACLE_DSN`. Antes da mudança, essas variáveis vinham do `.env`; agora também ficam ausentes (`None`), fazendo `if not all([user, password, dsn]):` (`src/tools/oracle_dba.py:145,282,409,566,719`) e `if not user or not password:` (`src/tools/executor.py:726`) retornarem `ERRO_CONFIG` mesmo se a checagem de `user` for removida.
- **Reprodução sem Oracle e sem `.env` real:** Alterar temporariamente `src/tools/oracle_dba.py:719` para `if not all([password, dsn]):` e executar `python -m pytest -q tests/test_oracle_kill.py -k test_ausencia_oracle_user_kill_sem_conexao`: o teste continua passando.
- **Correção sugerida:** Definir valores fictícios para `ORACLE_PASSWORD_*` e `ORACLE_DSN` com `monkeypatch.setenv` dentro desses três testes, deixando ausente apenas `ORACLE_USER_*`.

### C4 — Justificativa de descartar em vez de abortar ("a produção não lê `ORACLE_SANDBOX`") deixa risco sistêmico aberto
- **Veredito:** INCONCLUSIVO
- **Severidade:** baixa — a premissa é verdadeira no código de produção atual (zero leituras de `ORACLE_SANDBOX` em `app.py`, `src/` e `tools/`), mas insuficiente como defesa em profundidade frente a `R-F2-2`, `C1` e herança para subprocessos.
- **Local:** `app.py:38-43,60-63` e `src/main.py:23-28,47-50`
- **Cenário:** `ORACLE_SANDBOX=1` presente no `.env` é descartada silenciosamente para `auditoria_oracle.log` (sem aviso visível na tela/stderr e sem abortar). A chave proibida permanece gravada no `.env` em disco, deixando a armadilha ativa para a próxima abertura do Test Explorer/debug do VS Code (`R-F2-2`), e pode permanecer em `os.environ` (propagando a subprocessos filhos) caso ocorra C1 ou R-F2-1.
- **Reprodução sem Oracle e sem `.env` real:** Executar `test_oracle_sandbox_do_env_descartada` (`tests/test_carga_env_entrada.py:87-97`): o processo sobe normalmente e o arquivo `.env` fictício continua contendo `ORACLE_SANDBOX=1` sem sinalização na saída padrão ou na UI.
- **Correção sugerida:** Se abortar na subida for considerado excessivo para disponibilidade, ao menos (a) nunca gravar `ORACLE_SANDBOX` em `os.environ` (filtrar antes ou `try/finally` + carga única) e (b) exibir alerta explícito em `st.error`/`st.warning` na Web e em `stderr` na CLI enquanto a chave permanecer no `.env`.

---

## 3. NÃO VIOLADO

`A1`, `A2`, `A4`, `B1`, `B2`, `D1`, `D2`, `D4`, `D5`, `E1`, `E2`

---

## 4. Residuais contestados

* **`R-F2-1`** — **Severidade proposta:** `média` (registrada como `baixa; impacto atual nulo (a produção não lê a variável)`).
  * **Motivo:** (1) `os.environ` é herdado por qualquer subprocesso criado pelo processo Web, de modo que manter `ORACLE_SANDBOX=1` no ambiente do processo não tem impacto garantidamente nulo a médio prazo e viola diretamente I3 sem emitir o WARNING; (2) conforme demonstrado em **C1**, o mesmo estado (variável promovida a "do shell" sem WARNING) ocorre deterministicamente numa única aba em caso de exceção dentro de `load_dotenv`, não dependendo apenas de corrida entre abas; (3) carregar o `.env` uma única vez por processo em `app.py` (com `try/finally`) elimina simultaneamente `R-F2-1`, `C1` e `B4` com custo mínimo.

---

## 5. Limites da revisão

- **`.env` real não lido:** não foi possível verificar quais chaves existem hoje no `.env` local nem no perfil de variáveis de ambiente do Windows do operador (relevante para B3 e R-F2-2).
- **Testes `sandbox_only` não executados:** os 16 testes marcados com `sandbox_only` permaneceram pulados (`ORACLE_SANDBOX` não definida), portanto o caminho real de `conftest.py:62-66` com `ORACLE_SANDBOX=1` contra instância Oracle viva não foi exercitado (apenas inspecionado estaticamente e testado via `tests/test_conftest_sandbox_env.py` e testes em memória de `dotenv_values`).
- **Servidor Streamlit real (`streamlit run app.py` com múltiplas abas/concorrência de threads):** não foi iniciado; a verificação de logging e reruns do Streamlit foi feita via inspeção do código-fonte instalado de `streamlit.logger` / `streamlit.web.*`, execução de `tests/test_carga_env_entrada.py` (`AppTest`) e testes Python isolados em memória.
- **Ambiente Linux/POSIX:** os testes e verificações de `os.environ` (incluindo sensibilidade a caixa) e `python-dotenv` rodaram exclusivamente em Windows (Python 3.15.2).
