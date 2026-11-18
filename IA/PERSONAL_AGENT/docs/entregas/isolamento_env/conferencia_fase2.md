# Conferência de segurança: fase 2 (D1/D2), antes do commit 3

Modelo: Opus 5.5 (claude-opus-5-5), subagente `seguranca`. Branch isolamento-env, HEAD bbe0e9b. Alterações conferidas: app.py e src/main.py (modificados, não commitados) e tests/test_carga_env_entrada.py (untracked).
Escopo: nenhum código editado; `.env` não lido (só testei se o arquivo existe); ORACLE_SANDBOX ausente no shell (`env | grep -c ^ORACLE_SANDBOX=` deu 0); sem Oracle.
Execução: `env -u ORACLE_SANDBOX python -m pytest -q tests/test_carga_env_entrada.py` deu **4 passed**. Depois disso, `git status` não mostrou nenhum arquivo novo além dos já listados.

## Veredito: CONFORME para o commit 3, com dois residuais registrados (R-F2-1 e R-F2-2). Nenhum dos dois bloqueia o commit.

## 1. Carga única, override=False, `from dotenv import load_dotenv`: CONFORME
- app.py:19 e src/main.py:8 mantêm `from dotenv import load_dotenv`, resolvido no import. A neutralização de test_fluxo_cli.py:82 e test_fluxo_web.py:129 continua valendo.
- app.py:39 e src/main.py:24: `load_dotenv(ROOT_DIR / ".env", override=False)`, com caminho explícito e override explícito.
- A carga vem antes do primeiro import do projeto (app.py:66, src/main.py:53). Antes dela só há stdlib, pandas, streamlit, dotenv e openai.
- `git grep` de `load_dotenv|dotenv_values|find_dotenv` fora de docs/: nenhuma ocorrência em src/tools, src/config ou tools/. As únicas cargas reais são app.py:39, src/main.py:24 e tests/conftest.py:54 (lista de permissão, D5). O resto é neutralização em teste.

## 2. Descarte só se ausente do shell; shell intocado; sem abortar; janela limpa: CONFORME (ver R-F2-1)
- app.py:38-43 e src/main.py:23-28: a presença no shell é testada antes da carga (`in`, que também pega valor vazio). O `del` só ocorre se a chave estava ausente antes e apareceu depois. Se veio do shell, nada acontece. Não há abort.
- Entre a carga e o `del` só existem `_ORACLE_SANDBOX_DESCARTADA = False` e o teste `in`. Nenhum código de terceiros roda nessa janela.
- **R-F2-1 (novo, severidade baixa; falha da minha própria D2, que só considerou o caso de uma sessão):** no Streamlit, cada sessão (aba) roda app.py na sua própria thread, e o teste "veio do shell?" é refeito a cada rerun a partir do os.environ **atual**. Uma intercalação entre duas sessões deixa a chave no processo:
  1. A testa: ausente.
  2. A carrega: a chave entra.
  3. B testa: presente, e B conclui que veio do shell.
  4. A apaga.
  5. B carrega: a chave volta, porque com override=False uma chave ausente é preenchida.
  6. B não apaga.

  A partir daí, todo rerun trata a chave como vinda do shell, e ela fica no processo sem WARNING. Impacto atual: nenhum. A produção não lê ORACLE_SANDBOX (git grep em app.py, src e tools: só as linhas da D2) e não cria subprocesso. A CLI (main.py) roda uma vez por processo e não tem essa intercalação.
  Mitigação, como item separado: tomar o retrato "do shell" **uma vez por processo**, num módulo só de stdlib que fique em cache entre reruns, e pôr um `threading.Lock` em volta do teste, da carga e do `del`. Não precisa estar no commit 3.

## 3. WARNING depois do basicConfig, sem dado sensível, repetido a cada rerun: CONFORME
- app.py:60-63 vem depois de app.py:49-57 (basicConfig) e :58 (silenciamento de loggers). src/main.py:47-50 vem depois de :35-46.
- Entre o `del` e o basicConfig não há nenhuma chamada de logging que pudesse configurar o log de forma implícita.
- A mensagem é constante: tem o nome da chave e nenhum valor. Usa `logging.getLogger(__name__)`; no Streamlit isso é `__main__`, que propaga para os FileHandlers de auditoria.
- A repetição a cada rerun é aceitável (decisão D2): é sinal de configuração a corrigir no .env. Se o R-F2-1 ocorrer, o aviso para de sair. Esse é mais um motivo para a mitigação de R-F2-1.

## 4. Teste tests/test_carga_env_entrada.py: CONFORME, com duas melhorias não bloqueantes
- ORACLE_SANDBOX=1 só aparece no arquivo fictício (:88, :102), lido **dentro do subprocesso** (:77-80). O ambiente do filho é uma cópia sem ORACLE_, EMAIL_ e GEMINI_ (:72). O filho não tem nenhuma credencial: nem no shell, nem no arquivo fictício. Então qualquer caminho Oracle termina em ERRO_CONFIG.
- O processo do pytest nunca recebe a chave: `env` é um dict novo, e o caso de shell usa `"0"` (:102), nunca "1".
- O .env real nunca é lido: o wrapper (:29-35) troca o caminho pelo fictício. A rede está neutralizada (:49-52). O handler na raiz (:45-47) transforma o basicConfig em no-op, então nada é gravado nos logs reais.
- Asserções:
  - a sentinela (:90) prova que o fictício foi carregado;
  - o descarte (:91) e o aviso único (:92-93) estão cobertos;
  - há uma chamada só, com caminho `RAIZ/.env` e `override is False` (:94-97);
  - o valor do shell prevalece e não sai aviso (:104-105).
- O controle negativo relatado (o caso "descartada" falha em 0313e3b) bate com o esperado.
- Limitações, que não bloqueiam:
  - (a) a ordem do WARNING em relação ao basicConfig não dá para provar com esse arranjo, porque o handler é pré-instalado. Fica verificada de forma estática (item 3).
  - (b) o caso `prevalece` não confere a sentinela nem `chamadas`. Recomendo acrescentar `SENTINELA_FASE2=1` ao arquivo e `assert dados["sentinela"] == "1"`, para o caso não passar de forma vazia se a carga deixar de acontecer.
  - (c) o AppTest roda uma vez só, então o rerun e o R-F2-1 não são exercitados.

## 5. Outros caminhos para ORACLE_SANDBOX do arquivo
| Caminho | Situação |
|---|---|
| Rerun do AppTest ou do Streamlit (uma sessão) | Cada run testa, carrega e apaga, em sequência. Fechado |
| Reruns concorrentes (várias sessões) | **Aberto: R-F2-1** (baixa severidade; chave inerte) |
| Import de `tools.*` antes da carga | Não ocorre (app.py:66, src/main.py:53) |
| src/config/settings.py | Sem carga desde c2b6a1d (git grep) |
| src/agent, src/__init__, src/config/__init__ | Vazios (0 bytes) |
| tools/*.py (rag_*, verificar_registro) | Sem dotenv; verificar_registro.py:17 lê só SCRIPTS_REGISTRY_PATH |
| tests/conftest.py:54 | Lista de permissão (:34-47) sem ORACLE_SANDBOX. Fechado |
| Streamlit (biblioteca) | grep por "dotenv" em site-packages/streamlit: nenhuma ocorrência |
| **Fora do código: VS Code** | **R-F2-2.** Ver abaixo |

**R-F2-2 (fora do código, prioridade alta, não verificado em execução):** a extensão Python do VS Code injeta `python.envFile` (padrão `${workspaceFolder}/.env`) no ambiente de execuções de **teste (Test Explorer) e debug**. Essa injeção é separada de `python.terminal.useEnvFile`.
- Se a pasta aberta for PERSONAL_AGENT, o .env deste projeto existe (só verifiquei a existência). Se ele tiver ORACLE_SANDBOX, a chave chega ao pytest **como se viesse do shell**: `ORACLE_SANDBOX_DO_OPERADOR == "1"` em conftest.py:10, e os testes sandbox_only rodam contra o Oracle. É a mesma classe do incidente 01:27, e nenhuma linha de código consegue distinguir isso.
- Estado atual: PERSONAL_AGENT/.vscode/settings.json tem `python.terminal.useEnvFile: false` e não define `python.envFile`. Workspace/.vscode/settings.json tem `useEnvFile: true`, mas Workspace/.env não existe.
- Recomendação, como item próprio:
  - (i) o operador confere, **sem expor o conteúdo ao agente**, que o .env não tem a chave ORACLE_SANDBOX, e a remove se tiver;
  - (ii) definir em PERSONAL_AGENT/.vscode/settings.json um `python.envFile` apontando para um arquivo inexistente ou vazio.

## Recomendação
Liberar o commit 3 (app.py e src/main.py, mais tests/test_carga_env_entrada.py), um commit por correção, com a lista de alterações citando R-F2-1 e R-F2-2 como residuais. A melhoria 4(b) no teste é opcional: se entrar, entra antes do commit e reforça a asserção.
