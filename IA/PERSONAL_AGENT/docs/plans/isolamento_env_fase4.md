# Plano — isolamento-env, fase 4 (revisão Gemini da fase 3)

Destino no repositório: `docs/plans/isolamento_env_fase4.md` (cópia literal deste arquivo; primeiro ato da execução).

## 1. Contexto

Pedido do responsável (2026-11-18): tratar os Achados 1 a 5 e os parciais D6.2 e D6.4 de `docs/entregas/isolamento_env/revisao_fase3/revisao_adversarial_gemini.md`. Sem Oracle, sem ler/alterar `.env`, sem tocar `.vscode/settings.json`, sem push. Última rodada do isolamento: após aceite, merge sem nova revisão Gemini.

Achados da investigação (só leitura, sessão Opus 5.5):

- **I1. Ordem (L13).** Leitura única do Achado 1 implica a produção abrir o `.env` ela mesma (`open` + `stream=`). Hoje nenhum teste intercepta `open`: as fixtures de `test_fluxo_cli.py`/`test_fluxo_web.py` só trocam `load_dotenv`/`dotenv_values` e vigiam `DotEnv.__init__` por caminho; o harness de `test_carga_env_entrada.py` (subprocesso com `raiz` = raiz **real**, `:25`) só redireciona essas duas funções. Mudar a produção antes faria a suíte abrir o `.env` real. **As proteções dos testes vêm antes da produção** (reordena o pedido: itens Achado 2/5 do antigo Passo 3 sobem para o Passo 1).
- **I2. Achado 4 — `env_file=None` não funciona.** `chromadb.config.Settings` (chromadb 1.5.9) tem `model_config = {"env_file": ".env", ..., "extra": "ignore"}` (`chromadb/config.py:320`): o kwarg `env_file=None` é ignorado em silêncio. Medido em diretório temporário com `.env` fictício: `Chroma(persist_directory=d)` → 1 `DotEnv('.env')`; com `Settings(is_persistent=True, env_file=None)` → 1; com `Settings(is_persistent=True, _env_file=None)` → **0**.
- **I3. Achado 4 — resíduo no import.** `import chromadb` constrói `Settings()` em 7 argumentos-padrão (`chromadb/__init__.py:112,465`, `api/client.py:67,669`, `api/async_client.py:65,526`, `api/shared_system_client.py:22`) e cada um lê `cwd/.env` (só para campos do `Settings`, não `os.environ`). Ocorre na 1ª chamada de `Chroma(...)`. Não é removível pelo `rag_search.py` sem patch do pacote → residual registrado. Nenhum teste importa `chromadb` hoje (`git grep`).
- **I4. Expectativas que mudam com `stream=`.** `test_carga_env_entrada.py:255` e `:381` afirmam `caminho == RAIZ/.env` em `load_dotenv`/`dotenv_values`; com `stream=` o caminho é `None`. Troca proposta: afirmar que a **única abertura** registrada pelo harness foi de `RAIZ/.env` (mesma força, mais estrita).

**Passo 0** (reprodução dos Achados 1, 2 e 4 pelo `verificador`, cópia de `b0ce169`, `.env` fictício; scripts em scratchpad `passo0/repro_achado1.py` e `repro_achado4.py`, que recusam a raiz real): **parcial**. O `verificador` (claude-haiku-5-5) fez o §5.0 (perfil: nenhuma linha) e a cópia de `b0ce169`, e parou quando a sessão entrou em modo de plano. **Achados 1, 2 e 4 ainda NÃO VERIFICADOS.** Primeiro ato após a aprovação: retomar o mesmo `verificador` para os passos 2 a 6 do pedido; saída em `docs/entregas/isolamento_env/fase4/passo0_reproducao.md`. Achado não reproduzido sai do plano (com o passo correspondente) e é só reportado; os passos seguintes só começam depois desse retorno.

## 2. Base

Branch `isolamento-env`, HEAD `3ff2b79` (código = `b0ce169`). Baseline: **226 passed, 16 skipped** (revisão Gemini em `b0ce169`; reconferido pelo `verificador` antes do Passo 1).

## 3. Arquivos por passo

| Passo | Arquivos | Quem (modelo) |
|---|---|---|
| 1 | `tests/_guarda_env.py` (novo, helper), `tests/test_guarda_env.py` (novo), `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`, `tests/test_carga_env_entrada.py` (só o harness) | `mecanico` (sonnet); revisão Opus |
| 2 | decisão: `docs/entregas/isolamento_env/fase4/decisao_fase4.md` | `seguranca` (opus) |
| 2 | `app.py` e `src/main.py` (só bloco `carga-env` + avisos), `tests/test_carga_env_entrada.py` | sessão principal (Opus 5.5) |
| 3 | `src/tools/rag_search.py`, `tests/test_rag_search_env.py` (novo) | sessão principal (Opus 5.5) |
| 4 | `tests/test_env_em_execucao.py`, `tests/test_guard_sessao_sandbox.py` | `mecanico` (sonnet) |
| 5 | `docs/GOVERNANCA_LOG.md`, `docs/PROCESSO.md` §7, `docs/plans/isolamento_env_fase4.md` | sessão principal |

Sem paralelismo (2 e 1 tocam `test_carga_env_entrada.py`; 2 toca `app.py`/`main.py`). `tests/conftest.py` não muda.

## 4. Passos

**Passo 1 — Proteger os testes antes da produção (Achados 2 e 5).** Commit `test:`.
- Helper `tests/_guarda_env.py`, usado pelas duas fixtures de fluxo e importado pelo script do harness (substitui as 3 cópias de `_guarda_init`):
  - `LeituraEnvRealBloqueada(BaseException)` (não capturável pelo `except Exception` da carga).
  - Identidade do alvo: `os.fsdecode(os.fspath(x))`, depois `os.path.samefile(alvo, real)` quando ambos existem; senão `normcase(realpath)` (cobre `\\?\`, `bytes`, 8.3).
  - `DotEnv.__init__`: bloqueia caminho do `.env` real **e** `stream` cujo `getattr(stream, "name", None)` seja o `.env` real.
  - `builtins.open`/`io.open` e `os.stat`: **redirecionam** o `.env` real para um fictício do teste e registram a abertura (`aberturas_redirecionadas`), para que a produção do Passo 2 leia o fictício. Qualquer outra forma de leitura do real → `LeituraEnvRealBloqueada` e registro em `leituras_env_reais`.
- Fixtures (Achado 2): `monkeypatch.delattr(sys, "_personal_agent_estado_env", raising=False)` antes de cada import/AppTest e restauração no teardown; `assert leituras_env_reais == []` no `finally` (CLI, `test_fluxo_cli.py:133-144`) e antes de `destinos_inesperados` (Web, `test_fluxo_web.py:231-234`).
- Harness de `test_carga_env_entrada.py`: mesmo redirecionamento de `open`/`io.open`/`os.stat` do `.env` real para `env_ficticio`, com contagem de aberturas por run. Nenhuma asserção existente muda neste passo (a produção ainda não abre o arquivo).
- Testes novos e controle:
  - `test_guarda_env.py`: `\\?\`, `bytes`, `stream` com nome, `open`/`io.open` e `os.stat` redirecionados, exceção não é `Exception`. Controle por mutação: helper com a comparação antiga (`normcase(realpath(fspath))` só em caminho) → falham.
  - Carga exercida em todo teste Web/CLI: o stub registra chamadas e cada teste afirma ≥ 1 carga. Controle direto em `b0ce169` (cópia, ordem CLI→Web e Web isolado): falha.

**Passo 2 — Carga única e fail-closed estrutural (Achados 1 e 3).** `seguranca` decide; sessão principal implementa. Commit `fix:`.
- Proposta a decidir (texto idêntico em `app.py` e `src/main.py`, sob o lock):
  1. `os.stat` do caminho: ausente → texto vazio (comportamento atual); existe e não é arquivo regular → `falhou` (Achado 3a).
  2. Uma abertura (`open(..., encoding="utf-8")`) e leitura para memória. `OSError` aqui, antes de qualquer escrita em `os.environ` → `estado = None` (nova tentativa no próximo rerun; esta subida ainda levanta `RuntimeError` com só o nome do tipo).
  3. `dotenv_values(stream=StringIO(t))` para B3, `load_dotenv(stream=StringIO(t), override=False)` para a carga, `dotenv.parser.parse_stream` para contar linhas com erro.
  4. Qualquer exceção depois de começar a escrever (`os.environ` diferente do retrato) → `falhou` (fail-closed até reiniciar). `finally` do `ORACLE_SANDBOX` inalterado.
  5. Linhas malformadas: não aborta; `WARNING` com **só a contagem**, no mesmo padrão do C3 (log + `stderr` na CLI, `st.warning` na Web). A decidir pelo `seguranca`.
  6. A produção toca o caminho só via `open` e `os.stat` (ambos cobertos pelo helper do Passo 1).
- Testes (harness): (a) PermissionError só na 1ª abertura → run 2 sobe, sentinela carregada (falha direta em `b0ce169`); (b) 1 abertura por run (em `b0ce169`: 2); (c) `.env` diretório → `falhou` (em `b0ce169`: `ok`); (d) linhas malformadas → `ok` + WARNING com a contagem e sem o conteúdo (em `b0ce169`: sem aviso); (e) `OSError` depois de escrita parcial → `falhou` e run 2 não recarrega (controle por mutação: tratar todo `OSError` como `None`).
- Expectativas alteradas (I4): `:255` e `:381`, de "caminho = `RAIZ/.env`" para "única abertura registrada = `RAIZ/.env`". Nenhuma outra asserção muda.

**Passo 3 — Chroma sem `.env` (Achado 4).** Commit `fix:`.
- `rag_search._obter_vectorstore`: `Chroma(..., client_settings=chromadb.config.Settings(is_persistent=True, _env_file=None))` (I2: **`_env_file`**, não `env_file`).
- Teste novo: `monkeypatch.chdir(tmp_path)` com `.env` fictício **antes** de importar `chromadb`; `HuggingFaceEmbeddings` e `chromadb.Client` trocados por falsos; contar `DotEnv` com caminho durante `_obter_vectorstore()` → 0. Controle direto em `b0ce169`: 1.

**Passo 4 — Parciais D6.2 e D6.4.** Commit `test:`.
- D6.2: `test_fluxo_nao_le_nem_recarrega_dotenv` passa a chamar `executar_script` (script do registro de teste, Oracle falso) e `buscar_script_interno` (`CHROMA_DB_DIR` em `tmp_path`, `_obter_vectorstore` falso). Controle por mutação em cópia de `b0ce169`: `load_dotenv(..., override=True)` dentro de cada uma → falha.
- D6.4: teste que, sem pedir a fixture, afirma `"guard_oracle_sandbox" in request.fixturenames` (autouse) e `scope == "session"` da `FixtureDef`. Controle por mutação em `tests/conftest.py:77` da cópia (sem `autouse`; sem `scope`) → falha.

**Passo 5 — Registro.** Commit `docs:`. GOVERNANCA_LOG (§7 abaixo), lições novas no `PROCESSO.md` §7, plano versionado.

Cada passo: diff inteiro revisado pela sessão principal, `verificador` (§6), `git diff` mostrado, commit com caminhos explícitos e coautoria de todo modelo que escreveu.

## 5. Decisões do responsável

Aprovadas em 2026-11-18, com a aprovação deste plano:
- **D1.** Reordenar: proteções dos testes (Achados 2 e 5) antes da produção (I1).
- **D2.** Achado 4 com `_env_file=None` (I2) e as 7 leituras do import do `chromadb` como residual (I3).
- **D3.** Trocar as expectativas `test_carga_env_entrada.py:255` e `:381` como em I4, se o `seguranca` confirmar `stream=`.
- **D4.** Visibilidade da contagem de linhas malformadas no padrão C3 (CLI `stderr` + Web `st.warning`), salvo decisão diferente do `seguranca`.

Decididas pelo responsável em 2026-11-18, sobre `docs/entregas/isolamento_env/fase4/decisao_fase4.md` §6:
- **P1.** `.env` ausente ⇒ `estado = None` ("Nova tentativa"), opção (B): sem o `except FileNotFoundError`; o teste (c') espera nova tentativa.
- **P2.** Sem teste determinístico da corrida entre abas: fechada por construção (I4/I5) e conferida na revisão do diff, sem exceção à regra P1a.

Aprovadas no pedido (2026-11-18): escopo, agentes por passo, um commit por passo, residuais a registrar, merge após aceite sem nova revisão Gemini.

## 6. Verificação (`verificador`, a cada passo)

- `docs/PROCESSO.md` §5, passos 0 a 3. Esperado: 0 failed; **16 skipped**, todos com o motivo do sandbox; passed = 226 + testes novos.
- §5.4 em cópia (`git archive`) com `.env` fictício: controles diretos contra `b0ce169` e mutações listadas no §4 (L3: conferir substituição e fim de linha; L14: ao menos uma variante falha, registrar as que passam).
- Greps extras: `git grep -n -E 'load_dotenv\(' -- 'src/*.py' app.py` → 2 linhas, `override=False`, `stream=`; `git grep -n 'env_file=None' -- src/` → 0 (só `_env_file=None`); `git grep -n -E '(print|warning)\(.*sombread|malformad' -- app.py src/main.py` sem valores.
- Entrega final: `git log -5 --oneline`; `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider`; `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider tests/test_fluxo_web.py`.

## 7. GOVERNANCA_LOG (linhas previstas)

Uma por commit (Passos 1 a 4) no formato do §6 do PROCESSO, mais a linha de residuais:
- **NUL sombreado:** valor com byte NUL numa chave que o ambiente já define é pulado por `override=False` e não falha (Achado 3.3).
- **`PYTHON_DOTENV_DISABLED`:** `load_dotenv` retorna `False` sem erro → `estado = "ok"` sem chaves do `.env`; não é totalmente fail-closed (AGENTDBA_LOG_DIR cai no padrão).
- **chromadb no import:** 7 leituras de `cwd/.env` para campos do `Settings` (I3).
- **Achado 5.4:** `set_key`/`unset_key`/`parse_stream`/`dotenv.cli` com caminho não passam por `DotEnv`; cobertos só se abrirem via `open`.

## 8. Fora de escopo

Itens já abertos da fase 3 (C2b `--sandbox`, GEMINI_API_KEY divergente); `.vscode/settings.json`; `.env`; patch em pacotes de terceiros; formas de caminho não testadas pelo Gemini (UNC, `subst`, junção NTFS, placeholder do OneDrive).
