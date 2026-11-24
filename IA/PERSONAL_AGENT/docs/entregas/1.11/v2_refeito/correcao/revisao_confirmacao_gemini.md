# Revisão de Confirmação — Correção do Item 6 v2 (`921e6ef..1d2c752`, branch `item6/v2`)

- **Escopo:** revisão só leitura dos commits `f9482c4`, `482feb4` (K1), `a7cd549` (K2), `76232b2` (K3), `240fb00` (K4), `bb9f74b` (K5), `946846d` e `1d2c752` (K6 / HEAD) na branch `item6/v2`, sem editar código, sem ler `.env`, sem `ORACLE_SANDBOX=1` e sem conexão ao Oracle.
- **Base:** `docs/entregas/1.11/v2_refeito/revisao_adversarial_gemini.md` e `docs/plans/1.11-V2-item6.md` §8 (incluindo o diff local não commitado da nota §8.10.8 sobre O1).
- **Linhas:** todas as linhas citadas foram conferidas em `1d2c752`.

---

## 1. Status dos achados A1–A10

| Id | Status | Arquivo:linha (`1d2c752`) | Evidência / ressalva |
|---|---|---|---|
| **A1** | **CORRIGIDO** | `src/tools/oracle_dba.py:55-57`, `:84-90`, `:913-950`, `:1823-1840`; `src/main.py:258-263`; `app.py:511-517`; `tests/test_oracle_kill.py:1330-1399`; `tests/test_fluxo_cli.py:362-378`; `tests/test_fluxo_web.py:495-516` | `RECUSAS_PKG_SEM_KILL` fecha os 6 códigos pré-kill; `"executado para"` fica restrito a `RESULTADOS_KILL_EXECUTADO`; `ERRO_ORACLE` como `p_status`, `""`, `None` e códigos desconhecidos viram `resultado_desconhecido=True`, `executado=False` e texto sem `"NÃO executada"`. Ressalvas já registradas: `P2` aceito para `ORA-00030 → ALVO_NAO_ENCONTRADO` (§8.10.7) e `R-a` no JSONL (ver §2). |
| **A2** | **CORRIGIDO** | `tests/test_item1_intencao.py:62-64`, `:226`, `:607`, `:653`; `tests/test_oracle_kill.py:854`; `tests/fakes_oracle.py:111-113`, `:126-128` | Pares `(formal, placeholder)` verificados em todos os pontos (`REGEX_PAR_FORMAL_PLACEHOLDER`) e `_CursorFake.execute` compara `_placeholders_sql(sql) == set(binds)`. Ressalva: comentários de bloco `/* ... */` não são removidos (ver mutante `N7` no §4). |
| **A3** | **CORRIGIDO** | `src/tools/oracle_dba.py:719-728`, `:952-994`, `:1771-1784`, `:1823-1840`; `tests/test_oracle_kill.py:1437-1554`; `tests/test_item1_intencao.py:678-698` | `_descrever_erro` total evita escape de exceção nos `except` de `matar_sessao_oracle`; `ERRO_INTERNO` marca `"resultado_desconhecido": True` (P1); retorno ilegível/não-dict não ecoa texto e só `is False` literal retira `resultado_desconhecido`. |
| **A4** | **CORRIGIDO** | `tests/fakes_oracle.py:25-28`, `:45-166`; `tests/test_item1_intencao.py:611-631`; `tests/test_oracle_kill.py:882-901`, `:1384-1399` | Fake valida `size` (`ORA-06502`), grava `p_status` apenas no `execute`, valida `pos == 0` e `datetime` em `setvalue`, deriva `description` e linha do `SELECT` (sem `--`), confere placeholders e simula `LENGTHB > 128` (`PREMISSA_CHARSET_MODELO = "AL32UTF8"`, declarada não verificada L7). `ORDEM_BINDS_KILL_V2` e literais `v_status` ficam vinculados à spec/body de `docs/entregas/1.11/item6/ops_kill.sql`. |
| **A5** | **PARCIAL** | **Corrigido:** `src/tools/oracle_dba.py:987` (ex-`:935`), `tests/test_oracle_kill.py:1058-1064`. **Aberto (adiado em §8.2 / §8.8):** `src/tools/oracle_dba.py:163, 179, 183, 186, 239, 253, 256, 265, 268, 300, 316, 320, 323, 344, 366, 378, 379, 427, 443, 447, 450, 487, 499, 595, 669, 838, 855, 856, 859, 920, 958, 961, 967, 981, 1671`; `src/tools/executor.py:810-927`; `app.py:395`; `src/main.py:418` | Por decisão explícita do §8.2, apenas `"instancia": dsn` do ramo D8 (`:987`) entrou no item 6 (corrigido e coberto em T7). Todos os demais vazamentos de DSN, `host:porta`, usuário protegido, aprovador, SQL/XPLAN e exceções cruas ao LLM seguem abertos na tarefa **R1 ampliada** (§8.8, pré-requisito para religar CLI/Web e rodar o ensaio sandbox). |
| **A6** | **CORRIGIDO** *(com pendência O1/O2 para o ensaio 4.1)* | `tests/test_oracle_kill.py:1629-1696`, `:1694-1840` | Os 4 `@pytest.mark.sandbox_only` foram migrados para a assinatura v2 (`identidade_esperada`, `ref_aprovacao`), protegidos por `_exigir_pkg_kill_v2()` como 1º comando e com `try/finally` fechando conexões, acompanhados de 3 testes AST. **Ressalvas:** (1) `_exigir_pkg_kill_v2()` em si não tem teste unitário (`N4` no §4); (2) `test_sandbox_kill_propria_sessao_ou_usuario_protegido` (`:1825-1838`) ainda fecha `conn` antes do kill (O1 aceito em §8.10.8 para o preparo do ensaio 4.1) e `test_sandbox_kill_param_invalido` (`:1788-1812`) abre conexão DIAG desnecessária antes do `sid=-1` (O2). |
| **A7** | **CORRIGIDO** *(novos mutantes encontrados no §4)* | `tests/fakes_oracle.py:45-166`; `tests/test_item1_intencao.py:226, 577-653`; `tests/test_oracle_kill.py:795, 854, 882-1002` | Os 8 mutantes originais de A7, mais `X_REGEX_ID_0_9A_Z` e `X_SELECT_SID_SERIAL_TROCADOS`, passaram a ser detectados. Novos mutantes sobre o código introduzido em K1–K5 sobrevivem (ver §4). |
| **A8** | **CORRIGIDO** *(no escopo aceito P3)* | `src/tools/__init__.py:3-9`, `:28-31`; `tests/test_oracle_kill.py:1229-1240` | `matar_sessao_oracle` foi removida de `src.tools` e de `__all__`. Continua importável por `src.tools.oracle_dba` (residual aceito pelo responsável em §8.10.7 P3). |
| **A9** | **CORRIGIDO** | `src/tools/oracle_dba.py:55`, `:1474-1505`; `src/main.py:258-263`; `app.py:511-517`; `tests/test_oracle_kill.py:1556-1586` | `montar_notificacao_kill` usa `MENSAGEM_DESFECHO_NAO_CONFIRMADO` (sem `"erro do Oracle"`) e tornou `resultado_desconhecido` keyword-only sem default. |
| **A10** | **CORRIGIDO** *(com lacuna de teste `N2`/`N3` no §4)* | `src/tools/oracle_dba.py:44`, `:731-760`, `:1331-1346`, `:1420-1430`, `:1929-2034`, `:2072`; `tests/test_oracle_kill.py:800-802`, `:1052-1226` | `""` em `program`/`machine` é recusado (`len(valor) < 1`); `preparar_intervencao_kill` valida `campos_invalidos_identidade` antes do prompt e grava evento `RECUSA_PRE_HITL` no JSONL sem `INTENCAO`. Ver §3 e mutantes `N2`/`N3` no §4. |

---

## 2. Código novo dos K1–K5: algum caminho informa um kill possivelmente executado como `"NÃO executado"`?

Análise de todos os canais após `execute_iniciado = True` (`src/tools/oracle_dba.py:887`):

- **E-mail (`montar_notificacao_kill`, `oracle_dba.py:1474-1525`):** **nenhum caminho** informa `"NÃO executada"` para desfecho desconhecido. `resultado_desconhecido` é keyword-only sem default (`:1482`), checado antes de `RESULTADOS_KILL_EXECUTADO` e antes do `else` (`:1493`). Só entra no `else` (`"NÃO executada"`) quando `registrar_decisao_kill:1839` recebeu explicitamente `parse_ok and dados_exec.get("resultado_desconhecido") is False`, o que em `matar_sessao_oracle` só ocorre antes do `execute` ou para os 6 códigos de `RECUSAS_PKG_SEM_KILL`.
- **CLI (`src/main.py:240-273`, `:404-416`) e Web (`app.py:456-489`, `:492-529`):** **nenhum caminho** informa `"NÃO EXECUTADA"` / `"NÃO executada"` para desfecho desconhecido. Em ambos, `elif desfecho.get("resultado_desconhecido"):` vem antes de `executado` e do `else`, exibindo `MENSAGEM_RESULTADO_DESCONHECIDO` + `MENSAGEM_DESFECHO_NAO_CONFIRMADO`; exceções que escapem de `registrar_decisao_kill` caem nos blocos `except Exception` (`main.py:404`, `app.py:456`), que informam `"estado desconhecido"`.
- **`resultado_tool` (JSON ao LLM, `oracle_dba.py:913-994`, `:1771-1840`, `:1907-1911`):** **nenhum caminho** afirma `"NÃO executado"` quando `resultado_desconhecido=True`. O valor efetivo `dados_exec["resultado_desconhecido"] = resultado_desconhecido` (`:1910`) e `executado = resultado_banco in RESULTADOS_KILL_EXECUTADO and not resultado_desconhecido` (`:1840`) são sempre gravados no JSON final.
- **JSONL (`kill_approval.log`, `oracle_dba.py:1317-1328`, `:1845-1856`):** **não grava o texto `"NÃO executado"`**, porém mantém a lacuna residual `R-a` (já apontada em `conferencia_c7.md` §5):
  - a linha `RESULTADO` **não possui o campo `resultado_desconhecido`**;
  - assim, um `ERRO_ORACLE` antes do `execute` (`resultado_desconhecido=False`) e um `ERRO_ORACLE` depois do `execute` (`resultado_desconhecido=True`) geram linhas `RESULTADO` com o mesmo esquema (`"decisao": "APROVADO", "resultado_banco": "ERRO_ORACLE", "motivo": null`);
  - além disso, se um retorno interno trouxer `"status_banco": "ENCERRADA"` sem `"resultado_desconhecido": False` (`test_oracle_kill.py:1495`), e-mail/CLI/Web/tool reportam `resultado_desconhecido=True` e `executado=False`, mas o JSONL registra `"resultado_banco": "ENCERRADA"` sem flag de desconhecido.
- **Ressalva já aceita (`P2`, §8.10.7):** `ALVO_NAO_ENCONTRADO` está em `RECUSAS_PKG_SEM_KILL` (`oracle_dba.py:88`), embora também possa vir do `ORA-00030` durante o comando de encerramento (`ops_kill.sql:193-194`); assumido que `ORA-00030` implica sessão inexistente, com separação de código encaminhada como insumo da PENDENTE APROVAÇÃO 1.

---

## 3. Recusa antes do HITL (A10): grava evento próprio no JSONL, sem `INTENCAO`?

**Sim — confirmado no código (`1d2c752`), com uma lacuna de cobertura de teste relevante (`N3`):**

1. **Onde valida e recusa:** em `preparar_intervencao_kill` (`src/tools/oracle_dba.py:1995-2033`), logo após `check_alvo.get("elegivel")` (`:1968`) e antes de `gerar_payload_e_hash_aprovacao` (`:2036`). Se `campos_invalidos_identidade(identidade)` retornar lista não vazia, retorna `requer_aprovacao=False`, `motivo="PARAM_INVALIDO"`, sem exibir prompt, sem chamar `registrar_decisao_kill`, sem `INTENCAO`, sem `RESULTADO`, sem conexão KILL e sem e-mail.
2. **Evento próprio no JSONL:** `_montar_registro_recusa_pre_hitl` (`:1331-1346`) grava via `_gravar_linha_jsonl_duravel` (`:2005`, sob os dois locks e `fsync`) uma linha com **exatamente 6 chaves**: `timestamp`, `fase="RECUSA_PRE_HITL"`, `id_intervencao` (32 hex próprios do evento), `motivo="PARAM_INVALIDO"`, `campos_invalidos` (somente nomes de campo, nunca valores) e `parametros` (`inst_id`, `sid`, `serial`). Falha de E/S na gravação vai para `logger.error` (`:2007-2011`) e a recusa se mantém.
3. **Isolamento da fase e do reconciliador:** `FASE_RECUSA_PRE_HITL = "RECUSA_PRE_HITL"` (`:44`) fica **fora** de `FASES_REGISTRO_KILL` (`:41`), então `registrar_log_aprovacao_kill(..., fase="RECUSA_PRE_HITL")` levanta `ValueError` (`:1311-1312`). Em `reconciliar_intencoes_orfas` (`:1420-1430`), o `id_intervencao` de 32 hex evita contagem em `linhas_invalidas`, e a fase `"RECUSA_PRE_HITL"` não entra em `intencoes` nem em `com_resultado` — o reconciliador a ignora intacta.
4. **Lacuna encontrada na cobertura de testes (`N3` no §4):** na produção, tanto a Web (`app.py:313`) quanto a CLI (`src/main.py:374`) chamam `preparar_intervencao_kill` / `conduzir_kill_hitl` com **`caminho_log=None`**, dependendo de `_caminho_log_efetivo(caminho_log)` em `oracle_dba.py:2005`. Todos os testes K4 (`tests/test_oracle_kill.py:1133-1226`) passam `caminho_log=log` explicitamente — nenhum testa `RECUSA_PRE_HITL` com `caminho_log=None` (via `CAMINHO_LOG_APROVACAO_PADRAO` ou `AGENTDBA_LOG_DIR`).

---

## 4. Novos mutantes relevantes sobreviventes (execução offline isolada)

### Ambiente de execução e limpeza (declarados)
- **Cópia isolada criada fora do repositório/OneDrive e fora do `%TEMP%` compartilhado:** `~/.gemini/...` (extraída via `git archive 1d2c752`, verificada sem `.env`, com `TEMP`/`TMP` apontados para subdiretório privado `priv_tmp` dentro da própria cópia e sem `ORACLE_*`/`EMAIL_*`/`GEMINI_*`/`OPS_KILL_*`).
- **Suíte executada em cada rodada:** `python -m pytest -q -rs -p no:cacheprovider tests/test_item1_intencao.py tests/test_oracle_kill.py tests/test_fluxo_cli.py tests/test_fluxo_web.py`.
- **Baseline (`M0_BASELINE`):** `rc=0 | 237 passed, 6 skipped, 13 warnings in 52.21s`.
- **Exclusão ao final:** `shutil.rmtree(copia_dir, ignore_errors=False)` executado no `finally`, confirmado com `COPIA_APAGADA: True`.

### Resultado: **8 novos mutantes relevantes sobreviveram** (`237 passed, 6 skipped` em todos)

| # | Mutante | Arquivo:linha (`1d2c752`) | Severidade | O que quebra em produção / teste e por que sobrevive |
|---|---|---|---|---|
| **N3** | `N3_PRE_HITL_IGNORA_CAMINHO_EFETIVO` | `src/tools/oracle_dba.py:2005` | **alta** | Troca `_gravar_linha_jsonl_duravel(_caminho_log_efetivo(caminho_log), registro)` por `_gravar_linha_jsonl_duravel(Path(caminho_log), registro)`. Em produção na CLI (`src/main.py:374`) e na Web (`app.py:313`), `caminho_log` é `None`: `Path(None)` lança `TypeError`, engolido pelo `except Exception` (`:2006`), fazendo o evento `RECUSA_PRE_HITL` **nunca ser gravado no JSONL real**. Sobrevive (`237 passed`) porque todos os testes K4 passam `caminho_log=log`. |
| **N4** | `N4_GATE_SANDBOX_DESLIGADO` | `tests/test_oracle_kill.py:1694-1697` | **média** | Substitui o corpo de `_exigir_pkg_kill_v2()` por `pass`, desligando completamente o gate `OPS_KILL_PKG_VERSAO=2` (A6). Os testes AST do K5 só conferem que a função é chamada, mas **nenhum teste unitário exercita `_exigir_pkg_kill_v2()`** (ausente/`"1"` → skip, `"2"` → prossegue). Sobrevive (`237 passed`). |
| **N1** | `N1_D8_VAZA_STR_EXC` | `src/tools/oracle_dba.py:979` | **média** | No `except Exception` pós-execute (D8), troca `type(exc).__name__` por `_descrever_erro(exc)`, voltando a vazar `str(exc)` cru de exceções Python internas no `resultado_tool` enviado ao LLM (contrariando D5 / `conferencia.md` §1). Sobrevive (`237 passed`) porque T7 (`id="d8"`) e T9 usam `RuntimeError("falha simulada")` sem colocar `"falha simulada"` em `proibidos`. |
| **N2** | `N2_PREP_GET_DEFAULT` | `src/tools/oracle_dba.py:1998` | **média** | Em `preparar_intervencao_kill` (A10 parte 2), troca `{c: fonte[c] for c in CAMPOS_IDENTIDADE_ESPERADA if c in fonte}` por `{c: fonte.get(c) for c in CAMPOS_IDENTIDADE_ESPERADA}`. Se `program` ou `machine` faltar no dict da pré-consulta DIAG, `.get` transforma em `None`, deixa passar ao prompt HITL e grava `INTENCAO` em vez de recusar com `RECUSA_PRE_HITL`. Sobrevive (`237 passed`) porque `CASOS_RECUSA_PRE_HITL` (`test_oracle_kill.py:1110-1118`) não inclui chave ausente. |
| **N7** | `N7_BLOCO_COMENTARIO_PLSQL_V1` | `src/tools/oracle_dba.py:895-899` | **média** | Envolve os 5 parâmetros extras da v2 em comentário de bloco SQL `/* ... */`. `_sem_comentarios_sql` (`tests/fakes_oracle.py:89-91`) só remove `--[^\n]*`, e `REGEX_PAR_FORMAL_PLACEHOLDER` (`tests/test_item1_intencao.py:64`, `tests/test_oracle_kill.py:854`) não remove comentários (`/* ... */` nem `--`), deixando o bloco mutilado passar em todos os testes (`237 passed`). |
| **N8** | `N8_SANDBOX_PASSA_NONE` | `tests/test_oracle_kill.py:1750` | **baixa** | Em `test_sandbox_kill_sessao_valida_encerrada`, passa `identidade_esperada=None, ref_aprovacao=None`. O teste AST `test_k5_sandbox_kill_chamadas_trazem_identidade_e_ref` (`:1648-1659`) só checa os nomes das keywords, não que os argumentos não sejam constantes `None`/vazias (`237 passed`). |
| **N5** | `N5_SEM_STATUS_PKG_VAZIO_EM_MATAR` | `src/tools/oracle_dba.py:932` | **baixa** | Remove `status_banco = status_banco or STATUS_PKG_VAZIO` em `matar_sessao_oracle`: a função passa a devolver `"status_banco": ""` e `"Status retornado pelo PKG_OPS_KILL: ;"`, mascarado nos testes de fluxo pelo fallback secundário de `registrar_decisao_kill:1838` (`237 passed`). |
| **N6** | `N6_PARAM_INST_DESCONHECIDO_TRUE` | `src/tools/oracle_dba.py:800` | **baixa** | Troca `"resultado_desconhecido": False` por `True` no retorno `PARAM_INVALIDO` de `validar_parametros_kill` em `matar_sessao_oracle`. O teste AST (`:1545`) só verifica presença da chave e `test_kill_param_invalido_sem_conexao` (`:90`) não valida `res["resultado_desconhecido"] is False` (`237 passed`). |

---

## 5. Recomendações objetivas de fechamento (sem editar o repositório)

1. **Prioritário (antes do aceite de K4/K5):**
   - Cobrir `RECUSA_PRE_HITL` com `caminho_log=None` (usando `isolar_log_aprovacao` / `CAMINHO_LOG_APROVACAO_PADRAO` ou via CLI/Web) para matar `N3`, e adicionar caso de chave `program`/`machine` ausente em `preparar_intervencao_kill` para matar `N2`.
   - Adicionar teste unitário direto de `_exigir_pkg_kill_v2()` (com `monkeypatch` de `OPS_KILL_PKG_VERSAO` ausente, `"1"` e `"2"`) para matar `N4`.
   - Incluir o texto da exceção (`"falha simulada"`) em `proibidos` do caso `d8` em T7 (`tests/test_oracle_kill.py:1060`) para matar `N1`.
2. **Secundário (endurecimento de K1/K2/K5):**
   - Estender `_sem_comentarios_sql` (`tests/fakes_oracle.py:89-91`) para remover também `/* ... */` e aplicar a limpeza antes de `REGEX_PAR_FORMAL_PLACEHOLDER` (`N7`).
   - Testar `matar_sessao_oracle` diretamente com `status_pkg=""` (`res["status_banco"] == "DESCONHECIDO"`, `N5`) e validar `res["resultado_desconhecido"] is False` em `test_kill_param_invalido_sem_conexao` (`N6`).
   - Manter no backlog obrigatório antes de religar CLI/Web e do ensaio 4.1: **R1 ampliada** (A5 restante), **O1** (`test_sandbox_kill_propria_sessao_ou_usuario_protegido` com sessão dedicada aberta) e **R-a** (incluir `resultado_desconhecido` na linha `RESULTADO` do JSONL).
