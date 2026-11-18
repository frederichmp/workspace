# Revisão adversarial: isolamento do `.env`, fases 1 e 2

**Para:** revisor adversarial (Gemini / Antigravity).
**Status:** material **preparado, não revisado**. Nenhum modelo novo revisou este diff. As conferências anteriores (`seguranca`, Opus) estão citadas só como contexto e não substituem esta revisão.

## 1. Escopo

| Item | Valor |
|---|---|
| Intervalo | `673ceb1..d05577e` (branch `isolamento-env`) |
| Diff | `diff_673ceb1_d05577e.diff`: 224 linhas, sha256 `a5f6af6e61f338a8cd60269a31fa4ff6827f357f4da1741618a3bf7b5c022aa4` |
| Arquivos no diff | `app.py`, `src/main.py`, `src/config/settings.py`, `src/tools/executor.py`, `src/tools/gemini_router.py`, `src/tools/notificador.py`, `src/tools/oracle_dba.py`, `tests/conftest.py` (8 arquivos, +68 −27) |
| Fora do diff, mas úteis como evidência | `tests/test_isolamento_env.py` (inalterado desde `673ceb1`), `tests/test_conftest_sandbox_env.py`, `tests/test_env_em_execucao.py`, `tests/test_carga_env_entrada.py`, `tests/test_executor.py`, `tests/test_privilegio_read.py`, `tests/test_privilegio_write_sandbox.py` |
| Commits de código | `86d1eac` (D5, testes), `c2b6a1d` (D3), `0313e3b` (D4), `560a339` (D1/D2) |
| Decisões | `docs/entregas/isolamento_env/decisao.md` (D1–D7); plano `docs/plans/isolamento_env.md` |

Gere o diff de novo com `git diff 673ceb1 d05577e -- src/ app.py tests/conftest.py` e confira o sha256 antes de revisar.

## 2. O que a mudança pretende garantir (invariantes a atacar)

- **I1.** O `.env` é lido só nos pontos de entrada (`app.py:39`, `src/main.py:24`), uma vez por processo (por rerun, na Web), antes de qualquer import do projeto (`app.py:66`, `src/main.py:53`).
- **I2.** Precedência: uma variável já presente no processo (shell ou perfil) vence o arquivo (`override=False`). Nada recarrega o `.env` depois da subida.
- **I3.** `ORACLE_SANDBOX` só vale se o operador a definir no shell. Se vier do arquivo, é removida logo depois da carga (`app.py:38-43`, `src/main.py:23-28`), com WARNING fixo depois do `basicConfig` (`app.py:60-63`, `src/main.py:47-50`), sem abortar.
- **I4.** Importar módulos de `src/tools/`, `src/config/` ou os módulos de teste não altera `os.environ`.
- **I5.** Nos testes, credenciais reais só entram com `ORACLE_SANDBOX=1` definida pelo operador antes do processo (`conftest.py:10`), só as 12 chaves de `CHAVES_ENV_SANDBOX` (`conftest.py:34-47`), sem sobrescrever o que já existe (`conftest.py:50-66`).
- **I6.** O kill (`OPS_OWNER.PKG_OPS_KILL.KILL_SESSION`, conta `ORACLE_USER_KILL`) usa as credenciais da subida, mesmo que o `.env` mude em disco durante o processo.

## 3. Checklist adversarial

Para cada item, responda **VIOLADO / NÃO VIOLADO / INCONCLUSIVO**, com arquivo:linha e um cenário concreto (entrada → efeito).

### A. Ordem e ponto de carga (I1)
- [ ] A1. Existe algum import do projeto (`tools.*`, `src.*`), direto ou indireto, executado antes de `app.py:39` ou `src/main.py:24`? Inclua imports de terceiros que importem o projeto.
- [ ] A2. Algum caminho de execução usa `src/tools/*` sem passar por um ponto de entrada (scripts, blocos `__main__` em `gemini_router.py` e `notificador.py`, `python -m src.tools.*`) e depende de variável que antes vinha do `.env`? O comportamento nesse caso é fail-closed?
- [ ] A3. A duplicação de módulos `tools.*` × `src.tools.*` ainda permite que alguma cópia leia o ambiente num estado diferente da outra?
- [ ] A4. Leituras no import (`oracle_dba.py` `AGENTDBA_LOG_DIR`; `gemini_router.py` `GEMINI_API_KEY`/`GEMINI_MODEL` e `genai.configure`/`GenerativeModel`; `main.py` `_inicializar_cliente_coordenador()` no import): alguma ficou com valor errado ou padrão inseguro por causa da nova ordem?

### B. Precedência e recarga (I2, I6)
- [ ] B1. Sobrou algum `load_dotenv`, `dotenv_values`, `find_dotenv` ou `override=True` em produção, inclusive em tempo de chamada? Grep esperado: `load_dotenv` só em `app.py` e `src/main.py`.
- [ ] B2. Algum código de produção grava em `os.environ` (além do `del` de `ORACLE_SANDBOX`)?
- [ ] B3. A mudança de precedência (o shell vence o arquivo) cria um risco operacional, por exemplo uma credencial antiga no perfil do Windows prevalecendo sem aviso? A mitigação registrada (verificação de nomes no perfil, repetida depois de cada alteração de perfil) basta?
- [ ] B4. Na Web, `app.py` roda a cada rerun: há algum cenário em que um valor alterado no `.env` entra no processo sem reinício (chave **nova** entra no próximo rerun, já que `override=False` só protege chaves existentes)? Isso afeta credenciais Oracle ou e-mail?

### C. `ORACLE_SANDBOX` (I3)
- [ ] C1. Existe algum caminho em que `ORACLE_SANDBOX` do arquivo permanece no processo (outro ponto de entrada; exceção entre a carga e o `del`; rerun concorrente; `python.envFile` do VS Code)?
- [ ] C2. O teste "veio do shell?" (`"ORACLE_SANDBOX" in os.environ` antes da carga) pode ser enganado? Considere valor vazio no shell, variável herdada do processo pai e ferramentas que injetam `.env` (VS Code, Streamlit, IDE).
- [ ] C3. O WARNING pode deixar de aparecer, por exemplo por logging já configurado por terceiros, nível do logger raiz ou `basicConfig` em no-op? Ele expõe algum valor?
- [ ] C4. Abortar seria mais seguro que descartar? Avalie a justificativa da D2: a produção não lê `ORACLE_SANDBOX`.

### D. Testes e conftest (I4, I5)
- [ ] D1. `credenciais_sandbox_do_env` (`conftest.py:50-59`): alguma entrada (chave com espaços, `export`, maiúsculas e minúsculas, valor vazio, arquivo com BOM) faz entrar chave fora da lista ou sobrescrever chave existente?
- [ ] D2. `os.environ.update(...)` (`conftest.py:62-66`) recebe só o retorno filtrado? Existe outro `os.environ[...] =` ou `update` em `tests/` que traga valor do `.env`?
- [ ] D3. Algum teste ainda depende, sem declarar, de valor que antes vinha do `.env` real (passando por acaso hoje)?
- [ ] D4. `tests/test_carga_env_entrada.py` grava `ORACLE_SANDBOX=1` num `.env` fictício: confirme que o arquivo só é lido no subprocesso, que o subprocesso não tem nenhuma chave `ORACLE_`/`EMAIL_`/`GEMINI_` e que nenhum caminho leva esse valor ao processo do pytest.
- [ ] D5. Os guards de sessão do conftest (`conftest.py:77-91`, `:151-161`) continuam efetivos com a carga nova de `conftest.py:62`, que roda **depois** do snapshot de `conftest.py:10`?
- [ ] D6. Os testes provam o que dizem? Para cada teste novo, aponte uma mutação de produção que ele **não** detectaria. Os controles negativos registrados estão no GOVERNANCA_LOG.

### E. Segurança do fluxo de kill (não deve ter mudado)
- [ ] E1. Nenhuma regra de autorização, hash, TTL, lista de protegidos ou SQL do kill mudou no diff? Os únicos trechos de `oracle_dba.py` no diff devem ser a remoção de `load_dotenv`/`ROOT_DIR`.
- [ ] E2. Antes de `0313e3b`, o e-mail depois de cada kill recarregava o `.env` com `override=True`. Confirme que o risco descrito (troca de `ORACLE_USER_KILL`/`ORACLE_DSN` no meio do processo) deixou de existir e que nenhum caminho equivalente sobrou.

## 4. Residuais já conhecidos (não reportar como novos; contestar se a severidade estiver errada)

| Id | Descrição | Severidade registrada |
|---|---|---|
| R-F2-1 | Corrida entre abas do Streamlit pode manter `ORACLE_SANDBOX` do arquivo, sem WARNING | baixa; impacto atual nulo |
| R-F2-2 | `python.envFile` do VS Code injeta o `.env` no Test Explorer e no debug, e o `conftest.py:10` aceita como se fosse do shell | alta; fora do código, decisão do responsável |
| D3 residual | Blocos `__main__` de `gemini_router.py`/`notificador.py` rodam sem `.env` | aceito (fail-closed) |
| Fora de escopo | `tools.*` × `src.tools.*`; `GenerativeModel` no import; `test_oracle_kill.py:173` sem efeito | itens próprios |

## 5. Regras para a revisão
- **Não** ler, abrir ou pedir o conteúdo de `.env`. **Não** executar nada contra Oracle. **Não** definir `ORACLE_SANDBOX`.
- Pode executar `pytest -q` sem `ORACLE_SANDBOX`. Resultado registrado em `d05577e`: 194 passed, 16 skipped.
- Saída esperada: lista de achados, do mais grave para o menos grave, cada um com: id do checklist, VIOLADO/INCONCLUSIVO, arquivo:linha, cenário concreto, como reproduzir sem Oracle e correção sugerida. Itens NÃO VIOLADO só como lista de ids.
