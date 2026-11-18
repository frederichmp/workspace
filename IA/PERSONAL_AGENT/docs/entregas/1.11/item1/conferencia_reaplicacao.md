Conferência do seguranca (claude-opus-5-5) da reaplicação do item 1 na branch item1/reaplicado; nenhum arquivo de código alterado

# Item 1 (1.11): conferência da reaplicação

- **Data:** 2026-11-18. **Modelo:** claude-opus-5-5 (Claude Opus 5.5), subagente `seguranca`.
- **Objeto:** o diff não commitado sobre `a89791a` (`git diff`, mais o arquivo novo `tests/test_item1_intencao.py`). `docs/plans/1.11.md` foi conferido como especificação, não como código.
- **Especificação:** `docs/entregas/1.11/item1/decisao.md` (inclusive a coluna "aa9a0a5 revertido" da seção e); `docs/plans/1.11.md`, item 1 (decisões do passo 2, o desvio, 1c e 1d); `docs/GOVERNANCA_LOG.md`, registros de 2026-11-18.
- **O que foi executado:** só `env -u ORACLE_SANDBOX python -m pytest -q -p no:cacheprovider`, com o resultado **183 passed, 16 skipped**, e comandos `git diff`/`grep`/`comm`. Não li `.env`, não conectei ao Oracle, não usei `ORACLE_SANDBOX` e não editei nenhum arquivo além deste.
- As linhas citadas são do working tree atual.

---

## 1. Caminho de decisão conferido (ordem real)

| # | Passo | Arquivo:linha | Conexão |
|---|---|---|---|
| 1 | Validação local + pré-consulta DIAG (antes da decisão) | `oracle_dba.py:1746` → `consultar_alvo_sessao_diag` (sonda 582, connect 594) | DIAG |
| 2 | Decisão humana | CLI `main.py:110-140`; Web `app.py:754` → `processar_decisao_hitl` | nenhuma |
| 3 | Web: cópia e limpeza da pendência | `app.py:334`, `app.py:352` | nenhuma |
| 4 | Relógio nº 1, aprovador, `destino_log`, **`id_intervencao`**, SEM_IDENTIFICACAO, TTL nº 1 | `oracle_dba.py:1399-1414` | nenhuma |
| 5 | Ramo não aprovado: 1 linha RESULTADO (falha → `logger.error`) e retorno | `oracle_dba.py:1416-1494` | nenhuma |
| 6 | **INTENCAO** (`_gravar_linha_jsonl_duravel`); qualquer `Exception` → FALHA_LOG_APROVACAO e retorno | `oracle_dba.py:1500-1547` | nenhuma |
| 7 | `executar_kill_verificado`: reconsulta DIAG, hash, elegibilidade, **TTL nº 2**, `matar_sessao_oracle` | `oracle_dba.py:1553` → 932 / 954 / 975 / 989 / 1007 | DIAG e depois KILL |
| 8 | `except Exception` → ERRO_INTERNO, segue; `except BaseException` → INTERROMPIDO, grava, CRITICAL, `raise` | `oracle_dba.py:1560-1612` | — |
| 9 | RESULTADO (falha → CRITICAL com o registro); log; e-mail (com marcador se a RESULTADO falhou) | `oracle_dba.py:1623-1684` | SMTP |

**Único caminho até a conta KILL:** `matar_sessao_oracle` só é chamada em `oracle_dba.py:1007`, e `executar_kill_verificado` só em `oracle_dba.py:1553`, depois da INTENCAO (1500). Nem `src/` nem `app.py` têm outro chamador (grep).

### 1.1 Recusas, o que vai ao log e o que a conta KILL executa (nesta base)

| Momento | Recusas | JSONL | Conta KILL |
|---|---|---|---|
| Antes da decisão | PARAM_INVALIDO, ALVO_NAO_ENCONTRADO, NAO_USUARIO, USUARIO_PROTEGIDO, ERRO_CONFIG, HostInacessivelVPN, ERRO_ORACLE (pré-consulta) | nenhuma linha | não tocada |
| Na decisão | SEM_IDENTIFICACAO, REJEITADO_PELO_APROVADOR, TIMEOUT / APROVACAO_EXPIRADA | 1 RESULTADO | não tocada |
| Falha da INTENCAO | FALHA_LOG_APROVACAO | 0 linhas, ou uma INTENCAO órfã (a6) | não tocada |
| Depois da INTENCAO, antes da KILL | PARAM_INVALIDO (reconsulta), ALVO_NAO_ENCONTRADO, ERRO_CONFIG, HostInacessivelVPN, ERRO_ORACLE da DIAG, ALVO_ALTERADO, NAO_USUARIO, USUARIO_PROTEGIDO, APROVACAO_EXPIRADA (TTL nº 2), ERRO_CONFIG / HostInacessivelVPN da KILL, ERRO_INTERNO | INTENCAO + RESULTADO | não tocada |
| Conta KILL | status do PKG v1; ERRO_ORACLE no connect ("NÃO executada"); ERRO_ORACLE a partir do execute ("resultado desconhecido"); nome da classe | INTENCAO + RESULTADO | 1 `connect` + 1 `execute` de `OPS_OWNER.PKG_OPS_KILL.KILL_SESSION` com 4 binds nomeados (`oracle_dba.py:764-789`) |

---

## 2. Vereditos por item

### a) Gravação durável

| Item | Evidência | Veredito |
|---|---|---|
| a1, ponto único | Todas as gravações passam por `_gravar_linha_jsonl_duravel` (`oracle_dba.py:1096-1109`), via `registrar_log_aprovacao_kill` (1176). A única exceção é o reconciliador, que chama `_anexar_linha_sem_lock` (1254) **sob os dois locks** (1204-1205). Não há outro `open` de escrita no módulo (grep: só 1079 `a+b` e 1209 `rb`) | CONFORME |
| a1, `a+b`, `write`, `flush`, `os.fsync`, separador | `oracle_dba.py:1079-1088`; separador em 1081-1084 | CONFORME |
| a1, encode estrito antes do open | `_codificar_linha` (1091-1093) é chamada em 1103, antes do lock, do `makedirs` e do `open` | CONFORME |
| a1, `threading.Lock` + lock de arquivo em toda gravação | `_LOCK_LOG_APROVACAO` (1104) mais `_lock_arquivo_log` (1106) em INTENCAO, RESULTADO, REJEITADO/TIMEOUT e INTERROMPIDO, todas por 1176; o reconciliador usa 1204-1205. `<log>.lock`, `msvcrt.locking` / `fcntl.flock` sem bloqueio, novas tentativas até o prazo (1015-1061) | CONFORME |
| a2 | `_FSYNC_DIRETORIO = os.name == "posix"` (49); só com `arquivo_novo` (1108-1109); `_fsync_diretorio` em 1064-1070. T5 cobre os dois valores | CONFORME |
| a3 | `fase` e `id_intervencao` keyword-only sem default (1156-1158 e 1120-1122); validação em `_montar_registro_aprovacao_kill` (1124-1131) antes do disco; regex de nome neutro `_REGEX_ID_INTERVENCAO` com `fullmatch` (47); `import uuid` acrescentado (seção e); id gerado em 1404, antes do ramo 1406 | CONFORME |
| a4 | O `try/except Exception` (1500-1512) cobre validação, encode, `makedirs` (1105), abertura do `.lock` (1043), lock indisponível (`LockLogAprovacaoIndisponivel` é subclasse de `TimeoutError`, portanto de `OSError`, 61), `open`, `write`, `flush`, `fsync`, `close` e fsync do diretório. T2 tem 9 modos, inclusive `lock_indisponivel` e `makedirs_falha` | CONFORME |
| a5 | Retorno 1535-1547 igual ao especificado; `resultado_tool` (1520-1534) sem o id; `logger.error` (1515-1519) com tipo e errno, sem a mensagem; sem RESULTADO e sem e-mail (retorna antes de 1553) | CONFORME |

### b) Nenhuma conexão depois da decisão sem a INTENCAO

| Item | Evidência | Veredito |
|---|---|---|
| Ordem em `registrar_decisao_kill` | Entre a decisão e a INTENCAO, 1399-1414 só leem o relógio, montam dados e geram o uuid. Não há `getenv` da KILL, sonda ou `connect`. A reconsulta, a sonda e o `getenv`/`connect` da KILL só ocorrem dentro de 1553 | CONFORME |
| T1 (`test_item1_intencao.py:180`) | **Por conta:** os eventos guardam `user` de cada `connect`. **Por momento:** cada `connect` registra as fases presentes no JSONL, e a ordem exigida é `DIAG []` → `fsync` → `DIAG [INTENCAO]` → `KILL [INTENCAO]` → `fsync`. Confere também os 4 binds v1 | CONFORME |
| T2 (`:226`) | **Por conta:** `kill_permitido=False` e `fake.conexoes == [USER_DIAG_FAKE]`. **Por momento:** snapshot de conexões, SQL e sonda no instante da decisão, igual ao estado final, com `sonda == 1`. Como a INTENCAO falha, qualquer sonda ou conexão posta antes dela seria detectada | CONFORME |
| Limite | Nenhum teste prova a ausência do `os.getenv("ORACLE_USER_KILL")` depois da decisão, que não é conexão. Fica provado pela leitura do código (720 só é alcançável por 1007) | aceito |

### c) RESULTADO

| Item | Evidência | Veredito |
|---|---|---|
| c1, campos | RESULTADO com o mesmo id e `motivo = motivo_resultado`: `None`, ou o nome da classe em ERRO_INTERNO e INTERROMPIDO (1561, 1585). `executado` e `falha_registro` ficam fora do JSONL. O retorno (1692-1705) tem os campos de c1, mais `resultado_desconhecido` | CONFORME |
| c2, TTL nº 2 | `aprovacao_expirada: Callable[[], bool]` keyword-only, sem default (911-918). É a última checagem antes de `matar_sessao_oracle` (989 → 1007). O lambda (1558) usa `relogio()` e o mesmo `_aprovacao_expirada`. A docstring "lido uma única vez" foi corrigida (1389-1390). Desvio do plano registrado em `docs/plans/1.11.md:69` | CONFORME |
| c2, ERRO_INTERNO | `except Exception` (1560-1577): só a classe no log e no JSON, e o fluxo segue para RESULTADO e e-mail "NÃO executada". T9 confere que `segredo-xyz` não aparece no JSONL, no `resultado_tool` nem no caplog | CONFORME |
| c2, INTERROMPIDO | `except BaseException` (1578-1612): grava uma vez dentro de `try/except Exception`, `logger.critical` (com o registro se a gravação falhou), `raise`, sem e-mail. T10 | CONFORME |
| c3 | Falha da RESULTADO depois do kill: CRITICAL com o JSON do registro (1637-1656), sem propagação; marcador e linha no corpo do e-mail (1677-1682); aviso na tela (`main.py:179`, `app.py:441`). T11. Em REJEITADO/TIMEOUT: `logger.error` com o registro (1436-1454), `falha_registro="RESULTADO"`, sem e-mail. T12 | CONFORME |
| c3, conteúdo do registro serializado | O registro serializado em REJEITADO/TIMEOUT (1443-1453) e em INTERROMPIDO (1579-1588) não tem o campo `alvo`. O de APROVADO tem. Nenhum dos três tem `timestamp`, mas a linha do logger tem o seu. Os dois casos não dependem do `alvo` para concluir: em REJEITADO não houve kill, e em INTERROMPIDO o desfecho é desconhecido de qualquer forma. A chave de conferência (`parametros`, `hash_payload` e id) está presente | DESVIO aceitável (O1, não bloqueante) |

### Decisões do responsável no passo 2

| Item | Evidência | Veredito |
|---|---|---|
| `AGENTDBA_LOG_DIR` | Padrão `r"C:\AgentDBA\logs"` (38-39), lido depois do `load_dotenv` (33). Nada é criado no import: o `makedirs` só roda na gravação (1105). `.env.example:39-40` sem OneDrive. `conftest.py:16-17` define a variável antes de qualquer import, e `pytest_sessionfinish` vigia `C:\AgentDBA`. Testes: `test_import_nao_cria_a_pasta_do_log`, `test_import_com_padrao_nao_cria_C_AgentDBA`, `test_padrao_fora_do_onedrive`, `test_env_example_log_dir_sem_onedrive`. Os `auditoria_oracle.log` ficam no repositório, conforme a exceção de 2026-11-18 | CONFORME |
| Lock de 5 s | `LOCK_LOG_TIMEOUT_SEGUNDOS = 5.0` (50), lido na chamada (1041). Teste entre processos reais (`:872`, `:900`) e com threads (`:915`). Sem lock, a INTENCAO dá FALHA_LOG_APROVACAO (T2 `lock_indisponivel`), e a RESULTADO cai no `except Exception` de c3 (CRITICAL e marcador) | CONFORME |
| Reconciliador | Idade mínima `APROVACAO_TTL_SEGUNDOS + 300` (76). Roda sob os dois locks (1204-1205). Grava NAO_CONCLUIDA / RECONCILIADO_NA_SUBIDA com id, aprovador, hash, `parametros` e `alvo` copiados da INTENCAO (1243-1253). Não toca: INTENCAO recente (1240-1242), timestamp ilegível ou sem fuso (1233-1239), linha inválida ou sem `fase` (1214-1224), arquivo inexistente (1201-1202, antes de criar o `.lock`). Chamado na subida: `main.py:356` e `app.py:527-545`; uma falha vira aviso e não derruba a aplicação. Há 9 testes de reconciliador | CONFORME |
| "resultado desconhecido" | `execute_iniciado = True` em `oracle_dba.py:773`, imediatamente antes do `cursor.execute` (774), e depois de `connect`, `cursor` e `var` (764-772). Só o `except oracledb.Error` (809-825) usa a flag. Um erro de `connect` da KILL mantém a flag `False`, e a mensagem continua "NÃO executada" (`montar_notificacao_kill` com `resultado_desconhecido=False`). Prova: T8 `erro_connect_kill` ("NÃO executada", `resultado_desconhecido False`) e `ora00600` / `test_pls00306_no_execute_e_resultado_desconhecido` ("resultado desconhecido" no e-mail, na tela e no `resultado_tool`) | CONFORME |

### e) Nada do item 6; chamada v1 intacta

| Item | Evidência | Veredito |
|---|---|---|
| Resíduos do item 6 | `git diff -U0 src app.py \| grep 'ref_aprovacao\|identidade_esperada\|logon_time\|LOGON_TIME\|ALVO_DIVERGENTE'` sai vazio | CONFORME |
| `matar_sessao_oracle` | Nenhuma linha `-`/`+` na assinatura (694) nem nos binds (777-788). Só foram acrescentadas `execute_iniciado` e a mensagem. T1 exige exatamente `{p_inst_id, p_sid, p_serial, p_status}` | CONFORME |
| Regressão | Nenhum `ALTER SYSTEM` e nenhum `getenv("ORACLE_USER")` em `src/` nem em `app.py` | CONFORME |

### 1c / 1d

| Item | Evidência | Veredito |
|---|---|---|
| 1c, Web | Cópia da pendência em `app.py:334`; checagem de aprovador vazio em 344-346; limpeza em 352, antes de `registrar_decisao_kill` (356). O `try/except Exception` (355-399) faz `st.error`, envia mensagem `tool` com `executado: null` e "estado desconhecido; consulte OPS_KILL_AUDIT" (sem `str(exc)`), cancela `calls_restantes`, retorna `True` sem fechamento pelo LLM. Ramos FALHA_LOG (414), resultado desconhecido (421) e falha da RESULTADO (441). Testes: `test_web_falha_log_aprovacao`, `test_web_excecao_em_registrar_decisao`, `test_web_clique_repetido_nao_reaproveita_pendencia` | CONFORME |
| 1d, CLI | Ramos `main.py:156`, 163 e 179. O `except` da rota kill (310-321) imprime `[Sistema]: ERRO interno no fluxo de kill; estado desconhecido`, com `executado: null` e sem `str(e)`. Testes: `test_cli_falha_log_aprovacao`, `test_cli_excecao_rota_kill` | CONFORME |

### Testes

| Item | Evidência | Veredito |
|---|---|---|
| Expectativas alteradas | As linhas `-` em `tests/` são só estas: os 3 `_um_registro` da CLI, os 3 `(reg,) = amb.registros()` da Web, `test_aprovacao_dentro_do_ttl_executa` (`len == 1` → 2) e `test_registro_log_contem_decisao...` (2 → 3). São exatamente as 8 do §d2. As outras linhas `-` são assinaturas do fake e do cenário (parâmetros novos com default `None`) e a chamada de `test_caminho_padrao_redirecionado`, que é mudança só de chamada | CONFORME |
| Asserções removidas ou enfraquecidas | Toda asserção removida reaparece mais forte. `decisao`/`motivo` passam para `[1]`. `len` sobe e ganha fase, igualdade de id e 32 hex (`test_fluxo_cli.py:165-174`, `test_fluxo_web.py:83-93`, `test_oracle_kill.py:563-572`, 617-629). Acrescentado `fase == "RESULTADO"` em `test_oracle_kill.py:498`. As 4 mudanças só de chamada (`:192`, `:210`, `:240`, `:661`) mantêm as expectativas | CONFORME |
| T1-T14 | Todos existem e provam o que dizem: T1 `:180`, T2 `:226`, T3 `:310`, T4 `:328`, T5 `:351`, T6 `:365`, T7 `:391`, T8 `:468`, T9 `:566`, T10 `:586`, T11 `:609`, T12 `:633`, T13 nos dois `test_fluxo_*`, T14 nos dois `test_fluxo_*`. O `ALVO_DIVERGENTE` saiu do T8, conforme a seção e) | CONFORME |
| T8 `usuario_protegido_reconsulta` | A docstring (`test_item1_intencao.py:473-475`) registra o hash coincidente e que o teste não exercita hash divergente real, como no GOVERNANCA_LOG de 2026-11-18 | CONFORME |
| T8 `param_invalido_local` | Ver o §3 | DEFEITO leve (C1) |

### Segurança geral

| Pergunta | Resposta | Veredito |
|---|---|---|
| Algum caminho executa a conta KILL sem INTENCAO? | Não. O único caminho passa por 1007 ← 1553, e 1553 só é alcançado se a INTENCAO (1500) não levantou exceção. Uma `BaseException` na INTENCAO se propaga antes de 1553 | CONFORME |
| Algum `except` amplo engole uma falha e diz "executado"? | Não. `executado` só deriva de `resultado_banco in RESULTADOS_KILL_EXECUTADO` (1617). ERRO_INTERNO, INTERROMPIDO, NAO_CONCLUIDA e FALHA_LOG dão `False`, e os `except` da CLI e da Web dão `null` / "estado desconhecido". Falha da RESULTADO mantém o `executado` real e acrescenta o marcador | CONFORME |
| Segredo ou mensagem de exceção no JSONL ou no LLM? | JSONL: só aprovador, hash, parâmetros, alvo e o nome da classe no `motivo`. LLM: os caminhos novos (FALHA_LOG, ERRO_INTERNO e os `except` da CLI e da Web) não levam `str(exc)`. O `str(db_err)` na `mensagem` de `matar_sessao_oracle` (812-814) e o `instancia: dsn` são **preexistentes** e não trazem a senha | CONFORME |

---

## 3. T8 `param_invalido_local`: avaliação

- **O que o caso c2 pedia:** "PARAM_INVALIDO local (identidade da reconsulta incompleta)". Esse caso é a validação da `identidade_esperada` do v2, dentro de `matar_sessao_oracle`.
- **Esse caso existe nesta base?** **Não.**
  - Com o aa9a0a5 revertido, o único PARAM_INVALIDO de `matar_sessao_oracle` é `validar_parametros_kill` sobre inst_id, sid e serial (`oracle_dba.py:703`).
  - Por `executar_kill_verificado`, ele é **inalcançável**: `consultar_alvo_sessao_diag` aplica antes a mesma função aos mesmos valores (`oracle_dba.py:553`) e devolve `encontrado=False` com PARAM_INVALIDO (932-951).
  - A validação local de `matar_sessao_oracle` continua coberta isoladamente por `test_kill_param_invalido_sem_conexao` (`test_oracle_kill.py:60`).
  - A minha seção e) não previu isso. É lacuna da decisão, não da implementação.
- **O que o teste prova:** PARAM_INVALIDO **da reconsulta** depois da INTENCAO, com 2 linhas, mesmo id, 0 KILL e e-mail "NÃO executada". É um caso válido de "depois da INTENCAO, antes da KILL".
- **O que falta:**
  - a docstring (`:476-477`) afirma "sem nenhuma conexão", mas o teste só confere `conexoes_kill == []`;
  - o id `param_invalido_local` sugere o PARAM_INVALIDO de `matar_sessao_oracle`, que este teste não exercita.

---

## 4. Observações (não bloqueantes) e riscos residuais

- **O1 (c3):** incluir `"alvo": alvo or {}` nos registros serializados de `oracle_dba.py:1443-1453` (REJEITADO/TIMEOUT) e `:1579-1588` (INTERROMPIDO), como já é feito em 1645-1655.
- **O2 (testes):** `_importar_em_subprocesso` (`test_item1_intencao.py:972`) repassa ao filho o `os.environ` do processo de teste. Esse ambiente pode conter valores do `.env` carregados pelo `load_dotenv` do módulo. O filho não os imprime nem conecta, mas, como defesa em profundidade, convém filtrar `ORACLE_*`, `EMAIL_*`, `SMTP_*` e `GEMINI_*` do `env` do filho.
- **R1 (residual, preexistente, fora do item 1):**
  - a barra lateral da Web chama `verificar_acessibilidade_host` (`app.py:579`) a cada execução do script, inclusive no rerun do clique de aprovação;
  - o bloco começa em `app.py:551` e roda antes do handler em 754, portanto **antes** da INTENCAO;
  - é uma sonda TCP sem credencial e fora do fluxo de kill (a regra de b2 vale "no fluxo de kill"), e não toca DIAG nem KILL;
  - registrar como residual; mudar o comportamento fica fora do plano do item 1.
- **Commit por caminho:** não incluir `db/ops_kill.sqlbkp`, `../ARCANA_REALM/`, `../MAHJONG_GAME/` nem os `docs/entregas/1.11/item1/diff_*` de referência, salvo decisão explícita.
- **Autoria (fato a registrar, sem efeito técnico):**
  - `docs/plans/1.11.md:64-67` diz que o item 1 "foi reconstruído a partir do `decisao.md`" e que a primeira implementação "não foi aproveitada";
  - a comparação textual mostra que a reaplicação foi **adaptada da referência** para a base revertida;
  - `tests/conftest.py` e `.env.example` são byte a byte iguais à referência (blobs `bb4cd74` e `10caf01`, idênticos aos de `diff_testes.diff` e `diff_producao.diff`);
  - das linhas acrescentadas: `app.py` tem 80 de 80 iguais à referência, `oracle_dba.py` 420 de 447 e `main.py` 34 de 45;
  - esta conferência foi feita contra a especificação, linha a linha, e não depende da origem;
  - o registro de autoria, porém, precisa dizer o que aconteceu (C3).

---

## 5. VEREDITO GERAL

**NÃO APTO como está. APTO PARA COMMIT depois de C1, C2 e C3.** Nenhuma delas altera código de produção. O código de produção (`oracle_dba.py`, `main.py`, `app.py`, `.env.example`) está **conforme** à especificação em todos os itens conferidos.

Correções exatas:

- **C1 (teste, `tests/test_item1_intencao.py`):**
  - na linha 462, trocar `id="param_invalido_local"` por `id="param_invalido_reconsulta"`;
  - depois da linha 521, acrescentar:
    ```python
        if caso.get("direto") == "param_invalido":
            assert fake.conexoes == [], "PARAM_INVALIDO na reconsulta: nenhuma conexão DIAG nem KILL"
    ```
  - nas linhas 476-477, substituir a nota por: "param_invalido_reconsulta: com o aa9a0a5 revertido não existe a identidade da reconsulta; o PARAM_INVALIDO local de matar_sessao_oracle (oracle_dba.py:703) é inalcançável por executar_kill_verificado, porque consultar_alvo_sessao_diag (oracle_dba.py:553) aplica antes a mesma validar_parametros_kill; ele é coberto por test_kill_param_invalido_sem_conexao. O caso usa sid=0 em chamada direta: PARAM_INVALIDO na reconsulta, sem nenhuma conexão."
- **C2 (`docs/GOVERNANCA_LOG.md`):** registrar no fechamento do item 1:
  - as 8 expectativas alteradas do §d2, com a justificativa "sem a INTENCAO não há prova de que a aprovação foi registrada antes da ação";
  - as 4 mudanças só de chamada (`test_oracle_kill.py:192, 210, 240, 661`);
  - as asserções acrescentadas (`fase`, id, 32 hex);
  - a adaptação do T8 `param_invalido_reconsulta` (§3);
  - o residual R1.
- **C3 (registro de autoria):** corrigir `docs/plans/1.11.md:64-67` (ou registrar no GOVERNANCA_LOG) que a reaplicação foi adaptada da referência (stash@{0} / `diff_*.diff`) para a base `a89791a`, com os números do §4. Cabe ao responsável decidir se isso é compatível com "a primeira implementação não foi aproveitada".

Recomendações opcionais: O1 e O2.
