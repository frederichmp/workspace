Você é o revisor adversarial desta mudança. Seu trabalho é encontrar onde ela falha: casos em que as garantias abaixo não valem, testes que não provam o que dizem e riscos que a mudança criou. Não é confirmar que está boa. Um achado só conta com cenário concreto e arquivo:linha.

## Contexto

Projeto: `IA/PERSONAL_AGENT` (agente DBA com CLI em `src/main.py`, Web Streamlit em `app.py` e ferramentas em `src/tools/`). Ele inclui um fluxo de encerramento de sessão Oracle com aprovação humana: conta `ORACLE_USER_KILL`, pacote `OPS_OWNER.PKG_OPS_KILL.KILL_SESSION`.

A mudança é o **isolamento do `.env`**. Antes, vários módulos carregavam o `.env` no import, e o e-mail enviado depois de cada kill o recarregava com `override=True`. Num incidente, `ORACLE_SANDBOX=1` vazou para o processo do pytest e testes `sandbox_only` rodaram contra o Oracle sem autorização. Agora o `.env` é lido uma vez nos pontos de entrada, o shell vence o arquivo, e `ORACLE_SANDBOX` vinda do arquivo é descartada.

- Intervalo: `673ceb1..d05577e` (branch `isolamento-env`).
- Commits de código: `86d1eac` (testes/conftest), `c2b6a1d` (remove carga no import), `0313e3b` (remove recarga em tempo de chamada), `560a339` (carga única nos pontos de entrada).
- Diff: `git diff 673ceb1 d05577e -- src/ app.py tests/conftest.py`. São 224 linhas, sha256 `a5f6af6e61f338a8cd60269a31fa4ff6827f357f4da1741618a3bf7b5c022aa4` sobre a saída de `git diff` (LF). Gere o diff e confira o hash antes de começar. Também está em `docs/entregas/revisao_fases_1_2/diff_673ceb1_d05577e.diff`; no seu checkout, essa cópia pode estar em CRLF e ter outro hash.
- Arquivos no diff: `app.py`, `src/main.py`, `src/config/settings.py`, `src/tools/executor.py`, `src/tools/gemini_router.py`, `src/tools/notificador.py`, `src/tools/oracle_dba.py`, `tests/conftest.py`.
- Testes de evidência, fora do diff: `tests/test_isolamento_env.py` (inalterado desde `673ceb1`), `tests/test_conftest_sandbox_env.py`, `tests/test_env_em_execucao.py`, `tests/test_carga_env_entrada.py`, `tests/test_guard_sessao_sandbox.py`.
- Decisões de projeto: `docs/entregas/isolamento_env/decisao.md`; plano em `docs/plans/isolamento_env.md`; histórico e controles negativos em `docs/GOVERNANCA_LOG.md`.

## Regras (inegociáveis)

- **Não** leia, abra, imprima nem peça o conteúdo de `.env`.
- **Não** execute nada contra Oracle e **não** defina `ORACLE_SANDBOX` (nem com valor `1`, nem em arquivo).
- **Não** edite arquivos do repositório. Esta é uma revisão; correções são só sugeridas.
- Pode executar `python -m pytest -q` sem `ORACLE_SANDBOX`. Resultado em `d05577e`: 194 passed, 16 skipped. No HEAD atual, com o teste do guard: 199 passed, 16 skipped.
- Pode usar `git`, `grep` e leitura de código à vontade.

## Garantias a atacar

- **I1.** O `.env` é lido só nos pontos de entrada (`app.py:39`, `src/main.py:24`), uma vez por processo (por rerun, na Web), antes de qualquer import do projeto (`app.py:66`, `src/main.py:53`).
- **I2.** Precedência: uma variável já presente no processo (shell ou perfil) vence o arquivo (`override=False`). Nada recarrega o `.env` depois da subida.
- **I3.** `ORACLE_SANDBOX` só vale se o operador a definir no shell. Se vier do arquivo, é removida logo depois da carga (`app.py:38-43`, `src/main.py:23-28`), com WARNING fixo depois do `basicConfig` (`app.py:60-63`, `src/main.py:47-50`), sem abortar.
- **I4.** Importar módulos de `src/tools/`, `src/config/` ou os módulos de teste não altera `os.environ`.
- **I5.** Nos testes, credenciais reais só entram com `ORACLE_SANDBOX=1` definida pelo operador antes do processo (`tests/conftest.py:10`), só as 12 chaves de `CHAVES_ENV_SANDBOX` (`conftest.py:34-47`), sem sobrescrever o que já existe (`conftest.py:50-66`).
- **I6.** O kill usa as credenciais da subida, mesmo que o `.env` mude em disco durante o processo.

## Checklist

Responda cada item com **VIOLADO**, **NÃO VIOLADO** ou **INCONCLUSIVO**.

### A. Ordem e ponto de carga (I1)
- **A1.** Existe algum import do projeto (`tools.*`, `src.*`), direto ou indireto, executado antes de `app.py:39` ou `src/main.py:24`? Inclua imports de terceiros que importem o projeto.
- **A2.** Algum caminho de execução usa `src/tools/*` sem passar por um ponto de entrada (scripts, blocos `__main__` em `gemini_router.py` e `notificador.py`, `python -m src.tools.*`) e depende de variável que antes vinha do `.env`? O comportamento nesse caso é fail-closed?
- **A3.** A duplicação de módulos `tools.*` × `src.tools.*` ainda permite que alguma cópia leia o ambiente num estado diferente da outra?
- **A4.** Leituras no import (`oracle_dba.py` `AGENTDBA_LOG_DIR`; `gemini_router.py` `GEMINI_API_KEY`/`GEMINI_MODEL`, `genai.configure` e `GenerativeModel`; `main.py` `_inicializar_cliente_coordenador()`): alguma ficou com valor errado ou padrão inseguro por causa da nova ordem?

### B. Precedência e recarga (I2, I6)
- **B1.** Sobrou algum `load_dotenv`, `dotenv_values`, `find_dotenv` ou `override=True` em produção, inclusive em tempo de chamada? Esperado: `load_dotenv` só em `app.py` e `src/main.py`.
- **B2.** Algum código de produção grava em `os.environ` além do `del` de `ORACLE_SANDBOX`?
- **B3.** A mudança de precedência (o shell vence o arquivo) cria risco operacional, por exemplo uma credencial antiga no perfil do Windows prevalecendo sem aviso? A mitigação registrada (verificar nomes no perfil e repetir depois de cada alteração de perfil) basta?
- **B4.** Na Web, `app.py` roda a cada rerun. Uma chave **nova** no `.env` entra no próximo rerun sem reinício, porque `override=False` só protege chaves existentes. Isso afeta credenciais Oracle ou de e-mail?

### C. `ORACLE_SANDBOX` (I3)
- **C1.** Existe algum caminho em que `ORACLE_SANDBOX` do arquivo permanece no processo? Considere outro ponto de entrada, exceção entre a carga e o `del`, rerun concorrente e `python.envFile` do VS Code.
- **C2.** O teste "veio do shell?" (`"ORACLE_SANDBOX" in os.environ` antes da carga) pode ser enganado? Considere valor vazio no shell, variável herdada do processo pai e ferramentas que injetam `.env` (VS Code, Streamlit, IDE).
- **C3.** O WARNING pode deixar de aparecer, por exemplo por logging já configurado por terceiros, nível do logger raiz ou `basicConfig` em no-op? Ele expõe algum valor?
- **C4.** Abortar seria mais seguro que descartar? Avalie a justificativa da decisão: a produção não lê `ORACLE_SANDBOX`.

### D. Testes e conftest (I4, I5)
- **D1.** `credenciais_sandbox_do_env` (`conftest.py:50-59`): alguma entrada (chave com espaços, `export`, maiúsculas e minúsculas, valor vazio, arquivo com BOM) faz entrar chave fora da lista ou sobrescrever chave existente?
- **D2.** `os.environ.update(...)` (`conftest.py:62-66`) recebe só o retorno filtrado? Existe outro `os.environ[...] =` ou `update` em `tests/` que traga valor do `.env`?
- **D3.** Algum teste ainda depende, sem declarar, de valor que antes vinha do `.env` real e passa hoje por acaso?
- **D4.** `tests/test_carga_env_entrada.py` grava `ORACLE_SANDBOX=1` num `.env` fictício. Confirme três coisas: o arquivo só é lido no subprocesso; o subprocesso não tem nenhuma chave `ORACLE_`/`EMAIL_`/`GEMINI_`; nenhum caminho leva esse valor ao processo do pytest.
- **D5.** Os guards de sessão do conftest (`conftest.py:77-91` e `:151-161`) continuam efetivos com a carga de `conftest.py:62`, que roda **depois** do snapshot de `conftest.py:10`?
- **D6.** Os testes provam o que dizem? Para cada teste novo, aponte uma mutação de produção que ele **não** detectaria.

### E. Fluxo de kill (não deve ter mudado)
- **E1.** Nenhuma regra de autorização, hash, TTL, lista de protegidos ou SQL do kill mudou? Os únicos trechos de `oracle_dba.py` no diff devem ser a remoção de `load_dotenv` e `ROOT_DIR`.
- **E2.** Antes de `0313e3b`, o e-mail enviado depois de cada kill recarregava o `.env` com `override=True` e podia trocar `ORACLE_USER_KILL`/`ORACLE_DSN` no meio do processo. Confirme que esse risco deixou de existir e que não sobrou caminho equivalente.

## Residuais já conhecidos

Não os reporte como novos. Conteste se a severidade estiver errada ou se o impacto for maior que o registrado.

| Id | Descrição | Severidade registrada |
|---|---|---|
| R-F2-1 | Corrida entre abas do Streamlit pode manter `ORACLE_SANDBOX` do arquivo no processo, sem WARNING | baixa; impacto atual nulo (a produção não lê a variável) |
| R-F2-2 | `python.envFile` do VS Code injeta o `.env` no Test Explorer e no debug, e `conftest.py:10` o aceita como se viesse do shell | alta; fora do código; decisão do responsável |
| D3 residual | Blocos `__main__` de `gemini_router.py`/`notificador.py` rodam sem `.env` | aceito (fail-closed) |
| Fora de escopo | Duplicação `tools.*` × `src.tools.*`; `GenerativeModel` criado no import; `test_oracle_kill.py:173` sem efeito | itens próprios |

## Formato da resposta

1. **Diff conferido:** o sha256 que você obteve e se bate com o informado.
2. **Achados**, do mais grave para o menos grave, um bloco por achado:
   - **Id do checklist** (ex.: C1) e título curto;
   - **Veredito:** VIOLADO ou INCONCLUSIVO;
   - **Severidade:** alta, média ou baixa, com uma frase de justificativa;
   - **Local:** arquivo:linha;
   - **Cenário:** estado ou entrada concreta → efeito observado;
   - **Reprodução sem Oracle e sem `.env` real:** comando ou teste;
   - **Correção sugerida:** descrição curta, sem editar o repositório.
3. **NÃO VIOLADO:** só a lista de ids.
4. **Residuais contestados**, se houver: id, severidade proposta e motivo.
5. **Limites da revisão:** o que você não conseguiu verificar e por quê.

Não inclua elogios nem resumo da mudança. Se não encontrar nada num bloco, diga só "nenhum achado".
