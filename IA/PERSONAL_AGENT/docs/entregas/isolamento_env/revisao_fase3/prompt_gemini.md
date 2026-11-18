Você é o revisor adversarial desta mudança. Seu trabalho tem duas partes:
1. confirmar, no código, se os achados da sua revisão anterior estão de fato fechados;
2. atacar duas escolhas novas desta fase.

Um achado só conta com cenário concreto e arquivo:linha. "Fechado" exige o teste que o prova e o motivo pelo qual ele falharia sem a correção.

## Contexto

Projeto: `IA/PERSONAL_AGENT`. Agente DBA com CLI (`src/main.py`), Web Streamlit (`app.py`) e ferramentas em `src/tools/`. Inclui um fluxo de encerramento de sessão Oracle com aprovação humana: conta `ORACLE_USER_KILL`, pacote `OPS_OWNER.PKG_OPS_KILL.KILL_SESSION`, log de aprovação `kill_approval.log`.

Esta é a **fase 3 do isolamento do `.env`**, que corrige os achados da sua revisão de `673ceb1..d05577e` (`docs/entregas/revisao_fases_1_2/revisao_adversarial_gemini.md`).

- **Intervalo:** `d05577e..b0ce169` (branch `isolamento-env`).
- **Diff:** `git diff d05577e b0ce169 -- src/ app.py tests/`. São 1282 linhas, com sha256 `c2ededacf7046e6af2b27e07f9a499dd9df0b693a669be9568c65d0c54800a2c` calculado sobre a saída LF de `git diff`. Gere o diff e confira o hash antes de começar. A cópia em `docs/entregas/isolamento_env/revisao_fase3/diff_d05577e_b0ce169.diff` pode estar em CRLF no seu checkout e ter outro hash.
- **Arquivos:**
  - produção: `app.py`, `src/main.py`, `src/tools/oracle_dba.py`;
  - testes: `test_carga_env_entrada.py`, `test_conftest_sandbox_env.py`, `test_env_em_execucao.py`, `test_executor.py`, `test_fluxo_cli.py`, `test_fluxo_web.py`, `test_guard_sessao_sandbox.py`, `test_isolamento_env.py`, `test_item1_intencao.py`, `test_oracle_kill.py`.
- **Commits de código:**

  | Commit | Passo | Achados |
  |---|---|---|
  | `4aef0b4` | 1 | B4, C1, C2a, R-F2-1 |
  | `3cb6e03` | 2 | A3 |
  | `427adfc` | 3 | B3, C3 |
  | `cfd7890` | 4 | D6, D3 |

  O `350aee4` (teste do guard de sessão) também está no intervalo.
- **Documentos de apoio:** decisão de segurança em `docs/entregas/isolamento_env/decisao_fase3.md`; reprodução prévia em `reproducao_fase3.md`; controles negativos e de mutação em `fase3_controles.md`; plano em `docs/plans/isolamento_env_fase3.md`; histórico em `docs/GOVERNANCA_LOG.md`.

## Regras (inegociáveis)

- **Não** leia, abra, imprima nem peça o conteúdo de `.env`. Qualquer experimento usa um `.env` **fictício**, em cópia do projeto (`git archive`) ou em subprocesso com `dotenv` redirecionado.
- **Não** execute nada contra Oracle.
- **Não** defina `ORACLE_SANDBOX=1` em nenhum processo. Ela só pode aparecer como conteúdo de `.env` fictício lido por subprocesso **sem credenciais**. No ambiente de processo, use só `"0"` ou ausência.
- **Não** edite o repositório. Correções são só sugeridas.
- `pytest` só pelo terminal, nunca pelo executor de testes do VS Code: `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider`. Resultado registrado em `b0ce169`: **226 passed, 16 skipped**, com os 16 skips pelo motivo "requer ambiente de sandbox autorizado". Skipped abaixo de 16 significa sandbox indevido: pare e informe.
- Pode usar `git`, `grep` e leitura de código à vontade. Pode ler o código instalado de `python-dotenv` e `streamlit`.

## Parte 1: confirmar o fechamento

Para cada item, responda **FECHADO**, **NÃO FECHADO** ou **PARCIAL**, com o local da correção, o teste que prova e o motivo pelo qual o teste falharia sem a correção. Se discordar do controle negativo registrado, mostre a mutação que o teste não pega.

| Id | Achado original | Correção declarada | Testes declarados |
|---|---|---|---|
| **B4** | Rerun da Web recarregava o `.env`, e chave nova entrava no processo | Carga uma vez por processo; estado em `vars(sys).setdefault("_personal_agent_estado_env", ...)` com `threading.Lock` (`app.py:57-75`, `src/main.py:42-60`) | `test_b4_web_chave_nova_entre_reruns_nao_entra` (`tests/test_carga_env_entrada.py:269`); `test_r_f2_1_duas_sessoes_uma_carga` (:311) |
| **C1** | Exceção no meio do `load_dotenv` deixava `ORACLE_SANDBOX` do arquivo no processo | `try/finally` que remove `ORACLE_SANDBOX` quando ela não veio do shell (`app.py:67-75`, `src/main.py:52-60`); retrato do shell tirado uma vez | `test_c1_nul_nao_deixa_oracle_sandbox` (:285); `test_c2a_rerun_apos_falha_nao_promove_a_shell` (:297) |
| **A3** | Cópias `tools.*` e `src.tools.*` congelavam destinos diferentes do log | Destino resolvido em tempo de chamada: `_diretorio_log_aprovacao` e `_caminho_log_efetivo` (`src/tools/oracle_dba.py:1005-1016`); `CAMINHO_LOG_APROVACAO_PADRAO` vira gancho de teste (`:37`) | `test_a3_src_tools_antes_da_entrada_mesmo_destino` (:325); asserções acrescentadas em `test_item1_intencao.py` e `test_oracle_kill.py` |
| **B3** | Variável do ambiente sombreava o `.env` sem aviso | `_nomes_sombreados` (`app.py:49`, `src/main.py:34`): só nomes, valores em memória; WARNING, stderr (CLI) e `st.warning` (Web) | `test_b3_nomes_sombreados_sem_valores` (:358) |
| **C3** | WARNING de descarte se perdia com logging pré-configurado e não aparecia ao operador | stderr na CLI (`src/main.py:90`); `st.warning` em todo rerun (`app.py:561-563`) | `test_c3_cli_aviso_em_stderr` (:385), `test_c3_cli_aviso_com_raiz_em_error` (:394), `test_c3_web_st_warning_em_todo_rerun` (:403) |
| **D3** | Testes de `ERRO_CONFIG` passavam por acaso sem o `.env` real | Senha e DSN fictícios por `setenv`; rede e conexão bloqueadas | `test_ausencia_oracle_user_diag_sem_conexao`, `test_ausencia_oracle_user_kill_sem_conexao` (`test_oracle_kill.py`); `test_t19_oracle_user_read_ausente_com_select` (`test_executor.py`) |
| **D6** (5 pontos) | Testes não detectavam mutações diretas | D6.1: `test_conftest_sandbox_env.py:47, :73`. D6.2: `test_env_em_execucao.py:107`. D6.3: `test_carga_env_entrada.py:415, :429`. D6.4: `test_guard_sessao_sandbox.py:96-143`. D6.5: lista ampliada em `test_isolamento_env.py` | os mesmos; controles de mutação em `fase3_controles.md`, seção "Passo 4" |

Confira também o que **não** deveria ter mudado:
- regras de autorização, hash, TTL, lista de protegidos e SQL do kill;
- `load_dotenv` só nos blocos `# >>> carga-env` … `# <<< carga-env` (texto idêntico nas duas entradas), com `override=False`;
- nenhum `override=True`.

## Parte 2: ataques

### Ataque 1: o fail-closed do `.env` malformado pode travar a Web de forma indevida?

**Comportamento atual** (`app.py:62-80`, `src/main.py:47-65`):
- Qualquer `Exception` durante `_nomes_sombreados` ou `load_dotenv` deixa o estado do processo em `"falhou"`.
- Todo rerun da Web levanta `RuntimeError("Carga do .env falhou nesta subida (<Tipo>); ... Corrija o .env e reinicie o processo.")` **até o processo ser reiniciado**, sem nova tentativa.
- Uma `BaseException` (ex.: Ctrl+C) deixa o estado em `"falhou"`, com o tipo "interrompida".
- A decisão está justificada em `decisao_fase3.md`, P1c: recarregar reabriria o B4 e refaria o retrato do shell.

Ataque, com cenário concreto e reprodução sem `.env` real:
- **Erros transitórios.** O projeto fica numa pasta sincronizada pelo OneDrive. `PermissionError` ou `OSError` durante a sincronização, ou um arquivo lido no meio de um salvamento do editor, trava a Web até reiniciar? Isso é indevido? Compare com o custo de reabrir o B4.
- **Que entradas disparam o fail-closed.** Teste: `UnicodeDecodeError` (arquivo salvo em ANSI ou com BOM UTF-16), byte NUL, linha mal formada (o python-dotenv avisa ou levanta?), `.env` ausente, `.env` vazio, diretório no lugar do arquivo.
  - Algum caso trava a subida e **não deveria**, por exemplo um aviso de parse virando exceção?
  - Algum caso **deveria** travar e não trava?
- **Assimetria entre as duas leituras.** Uma falha em `dotenv_values` (B3, só informativo) derruba a carga mesmo quando `load_dotenv` funcionaria. É proporcional?
- **Estado preso no processo do pytest.** Algum teste que roda **no processo do pytest** (não em subprocesso) pode deixar `_personal_agent_estado_env` em `"falhou"` ou em `"ok"` sem carga real, contaminando os testes seguintes? Exemplos: as fixtures de `test_fluxo_cli.py:78`/`test_fluxo_web.py:115`, onde o guarda levanta `AssertionError` **dentro** do `try` da produção e o `except Exception` o converte em `"falhou"`.
- **Pré-semeadura do estado.** Um plugin, um `sitecustomize` ou um import anterior pode gravar `_personal_agent_estado_env` com `"estado": "ok"` antes da entrada e pular a carga e o descarte de `ORACLE_SANDBOX`? Qual o modelo de ameaça realista?
- **Mensagem de erro.** Ela vaza algo além do nome do tipo da exceção? Confira o encadeamento (`raise` fora do `except`) e o que o Streamlit mostra na tela.

### Ataque 2: o guarda do leitor do python-dotenv nos testes tem caminho que leia o `.env` real sem passar por ele?

**Desenho:**
- Os testes trocam `dotenv.dotenv_values` (e `load_dotenv`) por stubs.
- Um guarda em `dotenv.main.DotEnv.__init__` registra e recusa qualquer construção cujo `dotenv_path`, depois de `os.path.normcase(os.path.realpath(...))`, seja igual a `RAIZ/.env`.
- O teste afirma a lista de leituras vazia.
- Implementações: `tests/test_fluxo_cli.py:78-103`, `tests/test_fluxo_web.py:115-140`, `tests/test_carga_env_entrada.py:58-68` (no filho) e `tests/test_env_em_execucao.py:123`, que recusa qualquer construção.

Ataque:
- **Leitores fora do `DotEnv`.** Liste no python-dotenv instalado toda função que abre o arquivo sem passar por `DotEnv.__init__`: `get_key`, `set_key`, `unset_key` (reescrita), `find_dotenv`, `dotenv.parser.parse_stream` com `open` próprio e a CLI do `dotenv`. Alguma é alcançável a partir de `app.py`, `src/` ou dos testes?
- **Streams.** O guarda ignora argumentos com `.read` (`stream=`). Algum caminho passa um stream aberto sobre o `.env` real?
- **Terceiros.** `streamlit`, `openai`, `google-generativeai`, `langchain_community`, `chromadb`, `huggingface_hub`, `oracledb` ou outra dependência importada por `app.py`/`main.py` lê `.env` sozinha, com `python-dotenv` ou com parser próprio?
- **Equivalência de caminho.** O guarda compara `realpath` + `normcase`. Ele falha com:
  - nome curto 8.3 (`C:\Users\FREDER~1\...`, que aparece neste ambiente);
  - prefixo `\\?\` ou caminho UNC;
  - junção ou link simbólico, ou placeholder do OneDrive;
  - caminho relativo resolvido contra outro `cwd`;
  - outra letra de unidade (`subst`)?
- **Escopo.**
  - O guarda só existe nas fixtures citadas. Algum teste **sem** guarda importa uma entrada ou chama código que leia o `.env` real sem `ORACLE_SANDBOX=1`?
  - `tests/conftest.py:62-66` (`credenciais_sandbox_do_env`) lê o `.env` real **de propósito** quando o operador definiu `ORACLE_SANDBOX=1`. Confirme que, sem isso, ele não lê nada.
- **Ordem.**
  - Algum leitor é criado ou ligado **antes** da instalação do guarda (`main_cli` tem escopo de módulo) e lê depois?
  - Uma subclasse de `DotEnv` com `__init__` próprio escaparia?
- **Falha silenciosa.** Na Web (AppTest), a exceção do guarda é engolida pelo Streamlit, e a lista é o que faz o teste falhar. Existe caminho em que a lista não é conferida (ex.: exceção antes do `assert` do teardown)?

## Residuais já conhecidos

Não os reporte como novos. Conteste se a severidade estiver errada.

| Id | Descrição | Situação |
|---|---|---|
| R-F2-2 | `python.envFile` do VS Code injeta o `.env` no Test Explorer e no debug, e o `conftest.py:10` o aceita como se fosse do shell | aberto; depende do responsável |
| C2b | Falta opt-in por invocação (ex.: `--sandbox`); `ORACLE_SANDBOX` herdada de terminal pai ou do perfil é aceita | item futuro |
| GEMINI_API_KEY | Divergência entre cópias `tools.*` × `src.tools.*` (`gemini_router.py`, congelada no import) | item próprio |
| Guarda de sessão | Não há guarda `DotEnv` para a sessão inteira no conftest | item futuro |
| Janela P1b | Entre o `load_dotenv` gravar `ORACLE_SANDBOX` e o `finally` removê-la, só roda o laço do próprio python-dotenv, sob o lock | aceita |
| R-F2-1 | Corrida entre abas: fechado por construção (lock e retrato único); o teste prova uma carga entre duas sessões, sem intercalação determinística de threads | fechado |
| `PYTHON_DOTENV_DISABLED` | No perfil, desliga a carga sem aviso (fail-closed) | item futuro |

## Formato da resposta

1. **Diff conferido:** o sha256 obtido e se bate com o informado; o resultado do `pytest -q` (passed e skipped).
2. **Parte 1:** uma linha por id (B4, C1, A3, B3, C3, D3, D6.1 a D6.5), com veredito, local, teste e, se não for FECHADO, a mutação que o teste não pega.
3. **Parte 2, achados**, do mais grave para o menos grave, um bloco por achado:
   - **Ataque** (1 ou 2) e título curto;
   - **Veredito:** VIOLADO ou INCONCLUSIVO;
   - **Severidade:** alta, média ou baixa, com uma frase de justificativa;
   - **Local:** arquivo:linha;
   - **Cenário:** estado ou entrada concreta → efeito observado;
   - **Reprodução sem Oracle e sem `.env` real:** comando ou teste;
   - **Correção sugerida:** descrição curta, sem editar o repositório.
4. **Hipóteses da Parte 2 descartadas:** lista curta, com o motivo de cada uma.
5. **Residuais contestados**, se houver: id, severidade proposta e motivo.
6. **Limites da revisão:** o que não foi verificado e por quê.

Não inclua elogios nem resumo da mudança. Se um bloco não tiver achado, diga só "nenhum achado".
