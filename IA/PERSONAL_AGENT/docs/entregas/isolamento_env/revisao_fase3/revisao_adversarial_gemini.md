# Revisão Adversarial — Fase 3 do Isolamento do `.env` (`d05577e..b0ce169`)

## 1. Diff conferido e suíte `pytest`

- **Diff (`git diff --no-ext-diff d05577e b0ce169 -- src/ app.py tests/`):** `60771` bytes, `1282` linhas, `sha256: c2ededacf7046e6af2b27e07f9a499dd9df0b693a669be9568c65d0c54800a2c` (confere com o hash informado em `docs/entregas/isolamento_env/revisao_fase3/prompt_gemini.md`).
- **Blocos `# >>> carga-env` .. `# <<< carga-env` e `override`:** idênticos entre `app.py:34-81` e `src/main.py:19-66`; `git grep` em `app.py` e `src/` confirma `load_dotenv`/`dotenv_values` apenas nesses blocos, sem `override=True`, e nenhuma alteração em regras de autorização, hash, TTL, lista de protegidos ou SQL do kill.
- **Suíte (`Remove-Item Env:ORACLE_SANDBOX; $env:PYTHONDONTWRITEBYTECODE="1"; python -m pytest -q -rs -p no:cacheprovider`):** `226 passed, 16 skipped, 13 warnings in 127.73s` (`16` skips em `tests/conftest.py:188` por ausência de `ORACLE_SANDBOX=1`).

---

## 2. Parte 1 — Confirmação do fechamento

- **B4 — FECHADO** | Local: `app.py:57-75`, `src/main.py:42-60` (`_personal_agent_estado_env` em `vars(sys)` com `threading.Lock`) | Teste: `test_b4_web_chave_nova_entre_reruns_nao_entra` (`tests/test_carga_env_entrada.py:269`) e `test_r_f2_1_duas_sessoes_uma_carga` (`:311`) | Sem a correção, o rerun 2 recarregaria `.env`, gravando `SENTINELA_TARDIA_FASE3='1'` e resultando em `len(chamadas) == 2`.
- **C1 — FECHADO** | Local: `app.py:66-75`, `src/main.py:51-60` (`try/finally` com retrato único `_sandbox_do_shell`) | Teste: `test_c1_nul_nao_deixa_oracle_sandbox` (`tests/test_carga_env_entrada.py:285`) e `test_c2a_rerun_apos_falha_nao_promove_a_shell` (`:297`) | Sem a correção, `ValueError` do byte NUL abortaria antes da remoção de `ORACLE_SANDBOX`, deixando `'1'` em `os.environ` e promovendo-o a "do shell" no rerun seguinte.
- **A3 — FECHADO** | Local: `src/tools/oracle_dba.py:34-37, 1005-1016` (`_diretorio_log_aprovacao` e `_caminho_log_efetivo` resolvidos na chamada; `CAMINHO_LOG_APROVACAO_PADRAO: Optional[Path] = None`) | Teste: `test_a3_src_tools_antes_da_entrada_mesmo_destino` (`tests/test_carga_env_entrada.py:325`), além de `tests/test_item1_intencao.py:1001-1004, 1046-1050` e `tests/test_oracle_kill.py:658` | Sem a correção, o import prévio de `src.tools.oracle_dba` congelaria `C:\AgentDBA\logs\kill_approval.log`.
- **B3 — FECHADO** | Local: `app.py:49-54, 98-103, 562-563` e `src/main.py:34-39, 85-93` (`_nomes_sombreados`, armazenando só nomes) | Teste: `test_b3_nomes_sombreados_sem_valores` (`tests/test_carga_env_entrada.py:358`) | Sem a correção, nenhum `WARNING` com `ORACLE_DSN` seria emitido (`len(sombreados) == 0`).
- **C3 — FECHADO** | Local: `src/main.py:85-93` (`print(..., file=sys.stderr)`) e `app.py:560-563` (`st.warning` em todo rerun) | Testes: `test_c3_cli_aviso_em_stderr`, `test_c3_cli_aviso_com_raiz_em_error`, `test_c3_web_st_warning_em_todo_rerun` (`tests/test_carga_env_entrada.py:385-412`) | Sem a correção, `stderr` da CLI e `at.warning` da Web ficariam vazios.
- **D3 — FECHADO** | Local: `tests/test_oracle_kill.py:134-174` e `tests/test_executor.py:466-473` (`setenv` de senha e DSN fictícios + falha imediata ao tentar conectar) | Testes: `test_ausencia_oracle_user_diag_sem_conexao`, `test_ausencia_oracle_user_kill_sem_conexao`, `test_t19_oracle_user_read_ausente_com_select` | Sem a correção, remover a validação de `user` não seria detectado por ausência simultânea de senha/DSN.
- **D6.1 — FECHADO** | Local/Teste: `tests/test_conftest_sandbox_env.py:42-100` (`KEY=`, `KEY` e ligação real de `conftest.py` em subprocesso) | Sem a correção (mutações `d61a` e `d61b`), valores vazios ou chaves do `.env` entrariam em `os.environ`.
- **D6.2 — PARCIAL** | Local/Teste: `test_fluxo_nao_le_nem_recarrega_dotenv` (`tests/test_env_em_execucao.py:107-178`) | Pega mutações em `notificador.py` e `gemini_router.py`, mas **não exercita** `executar_script` (`src/tools/executor.py`) nem `buscar_script_interno` (`src/tools/rag_search.py`). **Mutação não pega:** reintroduzir `load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)` dentro de `executar_script` ou `buscar_script_interno` passa em `test_fluxo_nao_le_nem_recarrega_dotenv`.
- **D6.3 — FECHADO** | Local/Teste: `test_d63_valor_lido_no_import_prova_carga_antes_dos_imports` e `test_d63_warning_de_descarte_depois_do_basicconfig` (`tests/test_carga_env_entrada.py:415-440`) | Falha com `gemini_key_igual=False` se a carga vier depois dos imports e com `idx_basic < idx_warn` falso se o `WARNING` vier antes de `basicConfig`.
- **D6.4 — PARCIAL** | Local/Teste: `test_fixture_guard_*` e `test_operador_e_lido_do_ambiente_no_inicio_do_processo` (`tests/test_guard_sessao_sandbox.py:81-161`) | O teste invoca `_corpo_da_fixture_guard()()` diretamente como função Python (`:83-88`) e nunca verifica que a fixture é `autouse=True` / `scope="session"` no pytest. **Mutação não pega:** remover `autouse=True` (ou `scope="session"`) de `@pytest.fixture(scope="session", autouse=True)` em `tests/conftest.py:77` mantém `test_guard_sessao_sandbox.py` passando integralmente, embora a sessão de testes deixe de executar a guarda automaticamente.
- **D6.5 — FECHADO** | Local/Teste: `test_imports_de_teste_nao_alteram_environ` (`tests/test_isolamento_env.py:25-29`) | Lista inclui `src.config.settings`, `test_privilegio_read` e `test_privilegio_write_sandbox` (além dos submódulos de `src.tools.*` importados via `src.tools.__init__`).

---

## 3. Parte 2 — Achados

### Achado 1 — Ataque 1: Erro transitório de I/O (OneDrive / editor) ou falha só no `dotenv_values` do B3 trava a Web até reiniciar
- **Veredito:** VIOLADO
- **Severidade:** média — numa pasta sincronizada pelo OneDrive no Windows, uma contenção momentânea na primeira subida de `app.py` (antes mesmo de qualquer chave ser lida) paralisa permanentemente o servidor Web, exigindo reinício manual do processo; abrir o `.env` duas vezes (`dotenv_values` + `load_dotenv`) dobra essa janela e submete toda a aplicação a erro na leitura apenas informativa de B3.
- **Local:** `app.py:49-80`, `src/main.py:34-65`
- **Cenário:** Na primeira execução de `app.py`, o OneDrive ou editor segura um lock de arquivo em `ROOT_DIR / ".env"`. `_nomes_sombreados` (`app.py:68`) ou `load_dotenv` (`:69`) levanta `PermissionError`; `_ESTADO_ENV["estado"]` permanece `"falhou"` e `"falha"` fica `"PermissionError"`. Mesmo após o lock desaparecer instantes depois, nenhum rerun ou nova aba consegue subir (`app.py:76-80`: `Carga do .env falhou nesta subida (PermissionError)`), embora nenhuma chave do `.env` tenha entrado em `os.environ` (não há segundo snapshot nem reabertura do B4 nesse caso).
- **Reprodução sem Oracle e sem `.env` real:** Em cópia `git archive` com `.env` fictício válido, interceptar `builtins.open` na 1ª abertura do `.env` para lançar `PermissionError` uma única vez no run 1 do `AppTest` e liberar no run 2: o run 2 continua falhando com `Carga do .env falhou nesta subida (PermissionError)`.
- **Correção sugerida:** Fazer uma única leitura do `.env` sob `_ESTADO_ENV["lock"]` (passando `io.StringIO` em memória para `dotenv_values` e `load_dotenv(stream=...)`, reduzindo a 1 abertura) e fazer retry curto sob o lock ou manter `"estado": None` especificamente quando `OSError`/`PermissionError` ocorrer antes de qualquer escrita em `os.environ`.

### Achado 2 — Ataque 1 + Ataque 2: Estado compartilhado em `sys` anula a carga em `test_fluxo_web` na suíte completa e `AssertionError` do guarda prende o processo em `"falhou"`
- **Veredito:** VIOLADO
- **Severidade:** média — no processo único do `pytest`, a ordem alfabética faz `test_fluxo_cli` gravar `"estado": "ok"` em `sys._personal_agent_estado_env`, desativando o caminho de carga de `.env` em `test_fluxo_web`; inversamente, qualquer disparo do guarda `DotEnv.__init__` dentro do `try` de produção converte `AssertionError` em `"falhou"` permanente e contamina os testes seguintes de CLI/Web (além de poder pular o assert `leituras_env_reais == []`).
- **Local:** `app.py:57-76`, `src/main.py:42-61`, `tests/test_fluxo_cli.py:133-144`, `tests/test_fluxo_web.py:213-234`
- **Cenário:**
  1. `test_fluxo_cli` executa `import main`, gravando `sys._personal_agent_estado_env["estado"] = "ok"`, e no teardown (`tests/test_fluxo_cli.py:140-144`) desfaz `mp.undo()` e `sys.modules.pop("main")`, mas preserva `sys._personal_agent_estado_env`. Ao rodar `test_fluxo_web` em seguida, `app.py:63` encontra `estado == "ok"` e pula `if _ESTADO_ENV["estado"] is None:`, não exercitando `carga-env` nem o stub/guarda de `test_fluxo_web`.
  2. Se em qualquer teste in-process `_guarda_init` levantar `AssertionError` dentro de `src/main.py:52-55` ou `app.py:67-70`, o `except Exception` captura `AssertionError`, fixa `"estado": "falhou"` em `sys`, faz `tests/test_fluxo_cli.py:134` abortar no `RuntimeError` antes das linhas `:137` e `:139` (`assert leituras_env_reais == []` fora do `finally:`), e derruba os testes seguintes de `test_fluxo_web` com `Carga do .env falhou nesta subida (AssertionError)`. Adicionalmente, em `tests/test_fluxo_web.py:231-234`, se `assert amb.destinos_inesperados == []` (`:233`) falhar, `assert amb.leituras_env_reais == []` (`:234`) não executa.
- **Reprodução sem Oracle e sem `.env` real:** Remover temporariamente os stubs de `load_dotenv`/`dotenv_values` em `tests/test_fluxo_web.py`: rodando `pytest -q tests/test_fluxo_cli.py tests/test_fluxo_web.py`, a suíte passa por herdar `"estado": "ok"`; rodando `pytest -q tests/test_fluxo_web.py` isolado, todos os testes subsequentes ao primeiro falham no `RuntimeError` de estado `"falhou"`.
- **Correção sugerida:** Fazer `_guarda_init` levantar uma `BaseException` própria (não capturada por `except Exception`), mover `assert leituras_env_reais == []` para o `finally:` em `tests/test_fluxo_cli.py:140` e colocá-lo antes de `destinos_inesperados` em `tests/test_fluxo_web.py:233`.

### Achado 3 — Ataque 1: Entradas estruturalmente inválidas (diretório no lugar de `.env`, linhas malformadas e NUL em chave sombreada) sobem com `estado = "ok"`
- **Veredito:** VIOLADO
- **Severidade:** baixa — em vez de abortar fail-closed diante de `.env` corrompido ou substituído por diretório, `python-dotenv` ignora silenciosamente o diretório ou as linhas com erro de sintaxe, subindo o agente sem essas chaves (ou emitindo apenas `logger.warning` no stderr via `logging.lastResort`).
- **Local:** `app.py:52, 68-71`, `src/main.py:37, 53-55` (via `dotenv/main.py:62, 105, 475-486` e `dotenv/parser.py:178-185`)
- **Cenário:**
  1. `.env` como diretório: `_is_file_or_fifo` (`dotenv/main.py:475-486`) retorna `False` e `_get_stream` (`:73`) entrega `io.StringIO("")` → `estado = "ok"`, nenhuma variável carregada.
  2. Linha malformada (ex.: `CHAVE="aspas_abertas` ou `LINHA SEM IGUAL`): `parse_binding` (`dotenv/parser.py:178-185`) captura `Error` e `with_warn_for_invalid_lines` chama `logger.warning(...)` sem levantar exceção → `estado = "ok"`, linha descartada silenciosamente.
  3. Valor com byte NUL (`X=a\x00b`) quando `X` já existe no shell: `load_dotenv(..., override=False)` (`dotenv/main.py:105`) pula `X`, não chama `os.putenv` e sobe com `estado = "ok"` apesar do `.env` inválido (enquanto NUL na chave ou em valor não sombreado falha com `ValueError`, e ANSI/UTF-16 falha com `UnicodeDecodeError`).
- **Reprodução sem Oracle e sem `.env` real:** Em cópia `git archive HEAD` com `AppTest` sobre `.env` fictício nas três variações acima: todas retornam `estado="ok"` e `at.exception == []`.
- **Correção sugerida:** Verificar explicitamente `(ROOT_DIR / ".env").exists() and not (ROOT_DIR / ".env").is_file()` antes da leitura e, se desejar reprovar sintaxe quebrada ou NUL sombreado, validar linhas com `binding.error` via `parse_stream` e presença de `"\x00"`.

### Achado 4 — Ataque 2: Terceiro importado (`chromadb.config.Settings` via `rag_search.py`) lê `cwd/.env` com referência ligada de `dotenv_values` no import
- **Veredito:** VIOLADO
- **Severidade:** baixa — não altera `os.environ` e não é atingido pelos testes atuais nem apenas pelo `import app`/`main`, mas re-lê `.env` em runtime durante `buscar_script_interno` fora do `carga-env` e contorna stubs que substituem apenas `dotenv.dotenv_values`.
- **Local:** `src/tools/rag_search.py:14, 32`, `chromadb/config.py:320` (`pydantic_settings/sources/providers/dotenv.py:12, 92`)
- **Cenário:** `chromadb.config.Settings` define `model_config = {"env_file": ".env", ...}`. Ao chamar `Chroma(...)` (via `_obter_vectorstore` em `src/tools/rag_search.py:32`), `pydantic_settings` invoca a referência `dotenv_values` capturada no import (`from dotenv import dotenv_values` em `pydantic_settings/sources/providers/dotenv.py:12`), construindo `DotEnv('.env')` 8 vezes sobre o `.env` do diretório corrente. O guarda `DotEnv.__init__` bloqueia isso se estiver instalado e `cwd == RAIZ`, mas o stub `monkeypatch.setattr(dotenv, "dotenv_values", ...)` não o intercepta.
- **Reprodução sem Oracle e sem `.env` real:** Executar em diretório temporário com `.env` mínimo e wrapper em `DotEnv.__init__`: `from langchain_community.vectorstores import Chroma` registra `[]`, mas `Chroma(persist_directory=...)` registra 8 construções de `DotEnv('.env')`.
- **Correção sugerida:** Passar `client_settings=chromadb.Settings(env_file=None)` ou desabilitar `env_file` em `src/tools/rag_search.py:32` se quiser eliminar leitura tardia de `.env` fora de `carga-env`.

### Achado 5 — Ataque 2: Evasão do guarda `DotEnv.__init__` por prefixo `\\?\`, caminho `bytes`, `stream=` aberto ou leitores fora de `DotEnv`
- **Veredito:** VIOLADO
- **Severidade:** baixa — nenhum caminho em `app.py`, `src/` ou `tests/` utiliza hoje esses formatos ou funções, mas o guarda nas fixtures aceita leituras equivalentes do `.env` real sem disparar.
- **Local:** `tests/test_fluxo_cli.py:86-99`, `tests/test_fluxo_web.py:123-136`, `tests/test_carga_env_entrada.py:36, 59-67`
- **Cenário:** O guarda compara `os.path.normcase(os.path.realpath(os.fspath(caminho))) == real` somente quando `caminho is not None and not hasattr(caminho, "read")`. Em Windows/Python 3.15:
  1. Prefixo `\\?\` (`\\?\C:\...\PERSONAL_AGENT\.env`): `os.path.realpath` preserva `\\?\` e a igualdade com `real` resulta `False`.
  2. Caminho em `bytes` (`os.fsencode(caminho)`): `os.path.realpath` devolve `bytes`, e `bytes == str` resulta silenciosamente `False`, embora `open(bytes)` abra o arquivo.
  3. `DotEnv(None, stream=open(...))`: `caminho is None` pula a verificação.
  4. `dotenv.main.set_key`/`unset_key` (`rewrite` em `dotenv/main.py:148`), `dotenv.parser.parse_stream` (`dotenv/parser.py:188`) e `dotenv.cli` (`stream_file` em `dotenv/cli.py:68`) abrem o arquivo sem passar por `DotEnv.__init__`.
- **Reprodução sem Oracle e sem `.env` real:** Testado em Python 3.15 sobre arquivo `.env` temporário com a mesma expressão do guarda: `variant=ext_prefix` (`\\?\`) e `variant=bytes` retornaram `match=False` (`match=True` apenas para `str` e nome curto 8.3).
- **Correção sugerida:** Normalizar com `os.fsdecode`, remover eventual prefixo `\\?\` ou validar adicionalmente `os.path.samefile(alvo, real)` quando o arquivo existir, além de inspecionar `getattr(stream, "name", None)` e neutralizar `set_key`/`unset_key`/`parse_stream` caso se queira guarda amplo.

---

## 4. Hipóteses da Parte 2 descartadas

- **Ataque 1 — Aviso de parse (`with_warn_for_invalid_lines`) virando exceção:** descartada; `dotenv/main.py:32-39` apenas chama `logger.warning`, que usa `logging.lastResort` sem alterar `logging.getLogger().handlers` (`[]` antes e depois) e não levanta exceção.
- **Ataque 1 — Mensagem de erro ou encadeamento vazando dados do `.env`:** descartada; `raise RuntimeError(...)` em `app.py:77` e `src/main.py:62` ocorre fora do `except Exception`, com `__cause__` e `__context__` nulos, expondo apenas `type(exc).__name__` (ou `'interrompida'`).
- **Ataque 1 — Pré-semeadura maliciosa de `sys._personal_agent_estado_env` em produção:** descartada como vetor realista de ataque (quem já executa Python via `sitecustomize`/`.pth` antes da entrada já controla `os.environ` diretamente); o impacto prático restringe-se a isolamento entre entradas no mesmo processo (`pytest`, tratado no Achado 2).
- **Ataque 1 — `.env` ausente, vazio ou com BOM UTF-8 travando a subida:** descartada; todos resultam em `estado = "ok"`, e `Reader.__init__` (`dotenv/parser.py:73`) remove `\ufeff` normalmente.
- **Ataque 2 — Nome curto 8.3 (`C:\Users\FREDER~1\...`) e caminho relativo com `cwd == RAIZ`:** descartada; verificado neste ambiente Windows/Python 3.15 que `os.path.realpath` expande `FREDER~1\ONEDRI~1\...` para o caminho longo e coincide com `real`.
- **Ataque 2 — Outros leitores de terceiros no import/fluxo principal:** descartada para `streamlit`, `openai`, `google-generativeai` e `oracledb` (`0` ocorrências de `.env`/`dotenv` nos pacotes instalados) e para `huggingface_hub` (`utils/_dotenv.py` usado apenas pela CLI interna do pacote).
- **Ataque 2 — Outros testes importando `app.py`/`main.py` ou `conftest.py:62-66` lendo `.env` sem `ORACLE_SANDBOX=1`:** descartada; `git grep` confirma apenas `test_fluxo_cli.py`, `test_fluxo_web.py` e `test_carga_env_entrada.py` acionando as entradas, e `tests/conftest.py:52` retorna `{}` antes de chamar `dotenv_values` quando `operador != "1"`.
- **Ataque 2 — Subclasse de `DotEnv` ou `get_key` escapando de `DotEnv.__init__`:** descartada; `get_key` (`dotenv/main.py:135`) instancia `DotEnv` normalmente e não há subclasses de `DotEnv` no código nem no `python-dotenv`.

---

## 5. Residuais contestados

- **`PYTHON_DOTENV_DISABLED` (no perfil, "desliga a carga sem aviso (fail-closed)")** — **Qualificação/severidade:** continua `baixa`, porém o comportamento **não é totalmente fail-closed na subida**: `load_dotenv` retorna `False` sem erro (`dotenv/main.py:418-422`), de modo que `_ESTADO_ENV["estado"]` vira `"ok"` (`app.py:70`, `src/main.py:55`), `oracle_dba.py` falha apenas para Oracle (`ERRO_CONFIG`) mas `AGENTDBA_LOG_DIR` do `.env` é silenciosamente ignorado com fallback em `C:\AgentDBA\logs` (`src/tools/oracle_dba.py:34, 1007`), e se o `.env` tiver erro de leitura (`UnicodeDecodeError`), `dotenv_values` (`dotenv/main.py:438-472`, que não checa `PYTHON_DOTENV_DISABLED`) ainda derruba a subida.

---

## 6. Limites da revisão

- **`.env` real e Oracle:** o `.env` real não foi lido/aberto, `ORACLE_SANDBOX=1` não foi definido no ambiente e nenhuma conexão Oracle foi realizada.
- **Formas de caminho Windows não testadas empiricamente:** prefixo UNC de rede (`\\localhost\c$\...`), letra por `subst`, criação de junção/link simbólico NTFS e arquivo em estado placeholder "somente online" do OneDrive sobre uma entrada `.env` não foram testados em disco neste ambiente (apenas nome curto 8.3, `\\?\`, `bytes` e caminho relativo foram testados em Python 3.15).
- **Controles negativos e mutações da Fase 3:** aceitos conforme código inspecionado e saídas registradas em `docs/entregas/isolamento_env/fase3_controles.md`, sem reexecutar as mutações em `d05577e`.
