# Decisão de segurança: isolamento do .env (passo 2)

Modelo: Opus 5.5 (claude-opus-5-5), subagente `seguranca`. Branch item1/reaplicado, HEAD 673ceb1.
Escopo: somente leitura do código e de docs/entregas/isolamento_env/listagem.md. `.env` não lido (nem chaves, nem valores). Sem ORACLE_SANDBOX, sem Oracle, sem pytest. Nenhum arquivo do projeto editado além deste.
Status: **proposta, aguardando aprovação**. Nada aqui foi implementado.

## 0. Caminho de decisão do kill: o que muda e o que não muda

- **Casos de recusa** (em src/tools/oracle_dba.py, inalterados): PARAM_INVALIDO (:708, :1730), ERRO_CONFIG quando faltam ORACLE_USER_KILL/ORACLE_PASSWORD_KILL/ORACLE_DSN (:720-735; DIAG em :154, :291, :418, :574), HostInacessivelVPN (:744), ALVO_NAO_ENCONTRADO (:624), NAO_USUARIO (:644), USUARIO_PROTEGIDO (:656), ALVO_ALTERADO (:962), APROVACAO_EXPIRADA (:997), FALHA_LOG_APROVACAO (:1525, :1539), ERRO_INTERNO (:1569), ERRO_ORACLE (:672, :817).
- **O que vai ao log**: kill_approval.log em DIRETORIO_LOG_APROVACAO (:39, via AGENTDBA_LOG_DIR), fases INTENCAO e RESULTADO. Mais auditoria_oracle.log (logger) e e-mail após o RESULTADO (:1684).
- **O que a conta KILL executa**: só `OPS_OWNER.PKG_OPS_KILL.KILL_SESSION` (:777), credenciais lidas na chamada (:720-722).
- **Efeito desta mudança**: nenhuma regra muda. Muda só **de onde e quando** os.environ é preenchido. Hoje, `notificador.py:17` (`load_dotenv(override=True)`), chamado em :1684 depois de cada kill, regrava ORACLE_USER_KILL/ORACLE_DSN a partir do .env no meio da vida do processo. Esse comportamento acaba (D4). Em produção, via ponto de entrada, as variáveis ficam iguais. Fora do ponto de entrada não há credencial, e a recusa é ERRO_CONFIG antes de qualquer conexão (fail-closed).

## D1. Ponto único de carga

**Decisão:** app.py:33 e src/main.py:18 são os **únicos** carregamentos de produção. Os dois já estão antes do primeiro import do projeto (app.py:52, src/main.py:39). Forma:

```python
load_dotenv(ROOT_DIR / ".env", override=False)
```

- Caminho explícito `ROOT_DIR / ".env"`. Nunca `load_dotenv()` sem caminho: `find_dotenv` sobe a árvore a partir do frame chamador e pode pegar um `.env` de diretório pai.
- `override=False` escrito explicitamente. O comportamento não muda (já é o padrão), mas o texto deixa clara a precedência: o shell vence o arquivo.
- **Não usar `dotenv_values` + filtro no ponto de entrada.** Motivo: tests/test_fluxo_cli.py:81-82 e tests/test_fluxo_web.py:127-129 neutralizam o .env trocando `dotenv.load_dotenv` antes de importar main/app. tests/test_item1_intencao.py:994-996 injeta um módulo `dotenv` falso que só tem `load_dotenv`. Trocar para `dotenv_values` faria test_fluxo_cli/web **lerem o .env real** e quebraria o subprocesso de test_item1. O import precisa continuar `from dotenv import load_dotenv`, resolvido no import do módulo.
- Nota Streamlit: app.py é reexecutado a cada rerun, então :33 roda a cada interação. Com override=False, isso só preenche chaves ausentes. É idempotente e aceito.

## D2. ORACLE_SANDBOX vinda do .env

**Decisão: descartar (remover de os.environ) e registrar WARNING. Não abortar.** A produção não lê ORACLE_SANDBOX (grep em app.py, src/ e tools/: zero ocorrências), então abortar derrubaria o app por uma chave inerte. Mas um arquivo nunca é fonte de autorização (CLAUDE.md; incidente 01:27), e o processo não deve carregá-la. Se a chave já veio do shell, ela é mantida (override=False não a toca).

```python
_sandbox_no_shell = "ORACLE_SANDBOX" in os.environ
load_dotenv(ROOT_DIR / ".env", override=False)
_SANDBOX_DO_ENV_DESCARTADA = (not _sandbox_no_shell) and os.environ.pop("ORACLE_SANDBOX", None) is not None
# ... logging.basicConfig(...) inalterado ...
if _SANDBOX_DO_ENV_DESCARTADA:
    logging.getLogger(__name__).warning(
        "ORACLE_SANDBOX presente no .env foi descartada; só vale definida no shell da sessão autorizada."
    )
```

- **O WARNING vai depois do `logging.basicConfig`** (app.py:39-48, src/main.py:25-34). Chamar `logging.warning(...)` antes faria um basicConfig implícito, o basicConfig com FileHandler viraria no-op e a auditoria se perderia. O registro leva só o nome da chave, nunca o valor.
- No Streamlit, se o .env tiver a chave, o WARNING se repete a cada rerun. É aceito como sinal de configuração a corrigir.
- Verificação estática (grep e revisão do diff). **Nenhum teste automatizado gravará ORACLE_SANDBOX em arquivo**, nem falso. Foi exatamente esse o vetor de 01:27.

## D3. Carregamentos de módulo: remover todos

**Decisão: remover todos. Nenhum fica.**

| Local | Remoção |
|---|---|
| src/tools/oracle_dba.py:22, :32-33 | `from dotenv import load_dotenv`, `ROOT_DIR` (só usado em :33) e a chamada |
| src/tools/executor.py:25, :34-38 | import, comentário, `load_dotenv()`, `env_personal_agent` e o `if` |
| src/tools/gemini_router.py:16, :18-19 | import e chamada de módulo (a :37 cai em D4) |
| src/tools/notificador.py:10, :12 | import e chamada de módulo (a :17 cai em D4) |
| src/config/settings.py:4, :6 | import e chamada. O módulo não é importado por ninguém, mas sem a remoção um import futuro reintroduziria a carga via find_dotenv |

Justificativa por consumidor:
- O executor não é importado por app.py nem por src/main.py (grep vazio). O único consumidor é a suíte de testes, coberta por D5.
- oracle_dba, gemini_router e notificador só chegam à produção por app.py ou main.py, que carregam antes. tools/__init__.py (:2, :16, :20) deixa de disparar cargas.
- Os blocos `__main__` (gemini_router.py:158, notificador.py:46) são testes manuais. Rodados direto, ficam sem .env e devolvem a mensagem de "chave/credencial ausente" (fail-closed). Residual aceito. Se o responsável quiser manter, faz em commit separado: carga com caminho explícito e override=False **dentro** do bloco `if __name__ == "__main__":`, com import local, nunca no nível do módulo.
- tools/verificar_registro.py, rag_*.py e registry.py não usam dotenv. Sem alteração.

## D4. load_dotenv(override=True) em tempo de chamada

**Decisão: remover** notificador.py:17 e gemini_router.py:37. Não trocar por override=False.

- Vetor 1: `load_dotenv()` sem caminho com override=True **sobrescreve** os.environ com o que o find_dotenv achar subindo a partir de src/tools/. Isso inclui ORACLE_SANDBOX, se existir no arquivo, e qualquer `.env` de diretório pai.
- Vetor 2: notificador.py:17 roda em oracle_dba.py:1684, depois de cada kill. Num processo longo (Streamlit), isso troca ORACLE_USER_KILL, ORACLE_DSN e AGENTDBA_LOG_DIR (este só para quem o reler) entre um kill e a próxima preparação. Em teste, apaga credenciais fictícias de monkeypatch e põe as reais. gemini_router.py:37 roda dentro do laço de ferramentas do LLM, possivelmente entre preparar e executar.
- Vetor 3: inverte a precedência. O arquivo passa a vencer o shell.
- Trocar por override=False seria inútil (o ponto de entrada já carregou) e ainda faria leitura de arquivo em tempo de chamada.
- Perda aceita: a "recarga a quente". Mudança de **valor** no .env passa a exigir reiniciar o Streamlit ou a CLI. Chave **nova** ainda entra no próximo rerun do Streamlit (D1, override=False). Fica documentado no GOVERNANCA_LOG.
- Depois da remoção, gemini_router.py:38 e notificador.py:18-21 continuam lendo os.environ na chamada. Ausência dá retorno de erro, sem rede.

## D5. Credenciais dos testes sandbox

**Decisão: carga única em tests/conftest.py, só quando o operador já definiu ORACLE_SANDBOX=1 no shell, por lista de permissão, sem sobrescrever.** Remover as cargas de import em tests/test_executor.py:16 e :22-24, tests/test_privilegio_read.py:13 e :15-17, e tests/test_privilegio_write_sandbox.py:12 e :14-16. São arquivos de teste, mas a alteração não mexe em expectativa nem em asserção. test_isolamento_env.py fica intocado.

Local: tests/conftest.py, logo depois de :28 (SCRIPTS_REGISTRY_PATH) e antes das fixtures. Assim vale para a coleta e para as chamadas, e vem depois do snapshot de :10.

```python
if ORACLE_SANDBOX_DO_OPERADOR == "1":
    from dotenv import dotenv_values
    _CHAVES_SANDBOX = (
        "ORACLE_DSN", "ORACLE_USER_READ", "ORACLE_PASSWORD_READ", "ORACLE_USER_MUT", "ORACLE_PASSWORD_MUT",
        "ORACLE_USER_DIAG", "ORACLE_PASSWORD_DIAG", "ORACLE_USER_KILL", "ORACLE_PASSWORD_KILL",
        "ORACLE_CALL_TIMEOUT_MS", "ORACLE_SELECT_LIMIT", "ORACLE_LOB_LIMIT",
    )
    _valores_env = dotenv_values(Path(__file__).resolve().parent.parent / ".env")
    for _chave in _CHAVES_SANDBOX:
        if _chave not in os.environ and _valores_env.get(_chave) is not None:
            os.environ[_chave] = _valores_env[_chave]
```

- Lista de permissão, e não lista de bloqueio: ORACLE_SANDBOX, ORACLE_USER e ORACLE_PASSWORD (legado proibido), AGENTDBA_LOG_DIR, SCRIPTS_*, EMAIL_* e GEMINI_* **nunca** entram. AGENTDBA_LOG_DIR e SCRIPTS_REGISTRY_PATH continuam os do conftest. EMAIL_* ausente faz o kill sandbox não enviar e-mail real (menos efeito colateral).
- `dotenv_values` não mexe em os.environ. Só as chaves permitidas são escritas, e só as ausentes.
- O guard de :43-51 continua valendo. Como ORACLE_SANDBOX não é carregada, o guard não dispara por causa da carga.
- **Testes não-sandbox ficam sem nenhum .env.** É o objetivo. Os que precisam de credencial já usam valores fictícios (ambiente_fake em test_oracle_kill.py:267-274; test_fluxo_cli.py:85-90; test_fluxo_web.py:118-124).
- Observação, fora de escopo: test_oracle_kill.py:173 compara com `os.getenv("ORACLE_USER_KILL")`, e o teste só chama `registrar_log_aprovacao_kill`, que nunca conecta. A verificação já era vazia antes e continua vazia. Registrar como item próprio. Não mexer agora.

## D6. Leituras no import: risco depois da mudança e mitigação

| Ponto | Risco depois | Mitigação |
|---|---|---|
| oracle_dba.py:39 AGENTDBA_LOG_DIR | Produção sem mudança: a carga em app.py:33 e main.py:18 vem antes do import. Import direto sem ponto de entrada (REPL, script avulso) ignora o AGENTDBA_LOG_DIR do .env e cai em C:\AgentDBA\logs. Nesse cenário também não há credencial KILL, então a recusa é ERRO_CONFIG antes de conectar | Aceito e documentado. Testes: conftest :21 define antes do import, e test_item1_intencao.py:1028-1045 continua cobrindo |
| gemini_router.py:22/27/28 | Produção sem mudança (carga antes). Em teste, GEMINI_API_KEY fica ausente, então não há genai.configure e GenerativeModel é criado sem chave. A simulação com load_dotenv neutralizado importou sem erro e sem mudar os.environ | Nenhuma agora. Construção preguiçosa do modelo fica como item futuro |
| main.py:91 cliente no import | Produção sem mudança (:18 antes de :91). test_fluxo_cli deixa de herdar a GEMINI_API_KEY real que vazava pelas cargas de src.tools na coleta. Passa a usar "local" | Melhoria. Sem ação |
| app.py:569/578/592 sidebar | Sem mudança: :33 roda antes, a cada rerun. Perde a atualização de valor que vinha do override=True (D4) | Documentar: reiniciar após alterar valor no .env |
| `tools.*` vs `src.tools.*` | Deixa de causar cargas repetidas. Continuam duas cópias de módulo, ambas importadas depois da carga, e por isso leem o mesmo AGENTDBA_LOG_DIR. A duplicação de estado (lock de thread) é pré-existente | Fora de escopo. Item próprio |
| test_fluxo_cli.py:81, test_fluxo_web.py:127 | Passam a ser **efetivas e suficientes**: nenhuma carga de produção acontece antes delas | Exigência (D1): pontos de entrada com `from dotenv import load_dotenv` no import. Proibido `dotenv_values` ou carga em outro módulo |

## D7. Prova e verificação de aceite

**Prova (por construção):** o script do teste importa test_executor, test_oracle_kill e test_item1_intencao. Na cadeia (test_executor, depois src.tools.executor, src.tools.registry, src/tools/__init__, oracle_dba, notificador, gemini_router, os_tools, rag_search; tests.fakes_oracle), as **únicas** chamadas que alteram os.environ são as 6 interceptadas: tests/test_executor.py:24, notificador.py:12, oracle_dba.py:33, gemini_router.py:19, executor.py:35 e :38. D3 e D5 removem as seis. Nenhuma tinha valor de retorno usado, então remover equivale a neutralizar. A simulação da sessão principal com todas neutralizadas deu adicionadas=0, removidas=0, alteradas=0. O conftest não é importado pelo subprocesso. ORACLE_SANDBOX está ausente no ambiente do subprocesso (o teste filtra o prefixo ORACLE_), e AGENTDBA_LOG_DIR e SCRIPTS_REGISTRY_PATH são fixados pelo teste. Conclusão: as asserções :57-60 passam sem alterar o teste.

**Commits (um por correção, nesta ordem, sequenciais: nunca dois agentes em oracle_dba.py, main.py ou app.py):**
1. `refactor: remove carga de .env no import de src/tools e config` (D3)
2. `fix: remove load_dotenv(override=True) em tempo de chamada` (D4)
3. `fix: ponto de entrada carrega .env com override=False e descarta ORACLE_SANDBOX do arquivo` (D1, D2)
4. `test: carga de credenciais sandbox só no conftest, por lista de permissão` (D5)

**Aceite (todos obrigatórios, sem ORACLE_SANDBOX):**
1. `git diff 673ceb1 -- tests/test_isolamento_env.py` vazio.
2. `git grep -n -E "load_dotenv|dotenv_values|find_dotenv" -- src app.py tests` mostra só: app.py (import e :33), src/main.py (import e :18), tests/conftest.py (bloco D5), test_fluxo_cli.py:81-82, test_fluxo_web.py:127-129 e test_item1_intencao.py:995. **Zero** em src/tools/ e src/config/.
3. `git grep -n "override=True" -- src app.py tests` sem resultado.
4. `git grep -n "ORACLE_SANDBOX" -- app.py src` mostra só as linhas de D2 nos dois pontos de entrada. O `pop` vem depois do `load_dotenv`, e o `warning` vem depois do `basicConfig`.
5. `pytest -v -rs` comparado com uma rodada em 673ceb1 na mesma máquina. Única diferença aceita: test_imports_de_teste_nao_alteram_environ passa de FAILED para PASSED. Mesmo número de skips, e todos os sandbox_only pulados. Se o Controle de Aplicativo bloquear a DLL do oracledb, o aceite fica **"não verificado"**, nunca "aprovado".
6. **Sentinela (o teste não pode passar de forma vazia):** extrair `git archive HEAD` para um diretório em %TEMP% (o .env é ignorado pelo git, .gitignore:18, então não é copiado). Lá, criar um `.env` falso **só com nomes fictícios**: `SENTINELA_ISOLAMENTO_ENV=1`, `ORACLE_SENTINELA_FICTICIA=x`, `EMAIL_SENTINELA_FICTICIA=x`, `GEMINI_SENTINELA_FICTICIA=x`. **Nunca ORACLE_SANDBOX, nunca nomes reais.** Rodar `pytest tests/test_isolamento_env.py` na cópia: tem que passar. **Controle negativo:** repetir com `git archive 673ceb1`: tem que falhar com adicionadas_n >= 1. Isso prova que a sentinela seria detectada. Apagar as duas cópias no fim.
7. Opcional (positivo de D1): na cópia com sentinela, `python -I` importando `main` com rede bloqueada confirma `SENTINELA_ISOLAMENTO_ENV` em os.environ. Só se viável sem rede. Caso contrário, registrar como não executado.
8. `git status` limpo de arquivos inesperados. Atualizar docs/GOVERNANCA_LOG.md com status e com a perda da recarga a quente (D4).

## Residuais aceitos
- Import direto de src.tools sem ponto de entrada: sem .env (fail-closed; log no diretório padrão).
- Blocos `__main__` de gemini_router e notificador sem .env (D3).
- Mudança de valor no .env exige reinício (D4).
- WARNING repetido a cada rerun do Streamlit se o .env tiver ORACLE_SANDBOX (D2).
- Fora de escopo, como itens próprios: verificação vazia em test_oracle_kill.py:173; duplicação `tools.*`/`src.tools.*`; construção do GenerativeModel no import.
