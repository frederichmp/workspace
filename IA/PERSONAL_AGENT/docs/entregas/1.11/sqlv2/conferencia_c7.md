# C7 da parte A do SQL v2 (`1.11-sqlv2-parte2`, passo 4): conferência do `seguranca`

- **Modelo:** claude-opus-5-5 (subagente `seguranca`). Só leitura, sem Oracle e sem pytest. A única gravação é este arquivo.
- **Base:** `main` em `871ae13`; diff = working tree nos 7 arquivos de `git diff --stat` (367+, 202-). Todo `arquivo:linha` foi conferido nesta sessão (L9).
- **Contra:** `sqlv2/decisao_c1.md` e as 4 decisões aprovadas (texto do PKG; ERRO_PRE_KILL e ALVO_AUSENTE_NO_KILL como "NÃO executado"; A1; rollback sem `git revert`).

## Veredito: CONFORME

O único `ALTER SYSTEM` do PKG fica inalcançável depois de exceção nas etapas 1 a 6, nos dois arquivos (prova no §1). Ficam 4 observações que não bloqueiam (§6).

## 1. Critério de aceite: `ALTER SYSTEM` inalcançável depois de exceção nas etapas 1 a 6

Estrutura de `kill_session`, conferida no texto (`docs/entregas/1.11/item6/ops_kill.sql`; a parte 2 é idêntica, ver §2):

| Ponto | Onde |
|---|---|
| `v_pode_encerrar BOOLEAN := FALSE` | `ops_kill.sql:115` |
| Bloco das etapas 1 a 6: `BEGIN` ... `EXCEPTION WHEN OTHERS` ... `END;` | `:120`, `:193-200` |
| Único `v_pode_encerrar := TRUE`, última instrução do bloco, só com `v_status IS NULL` | `:189-191` |
| O handler grava `v_status := 'ERRO_PRE_KILL'` (1ª instrução) e `v_pode_encerrar := FALSE`, e anula `v_user/v_prog/v_mach/v_logon/v_div` | `:194-199` |
| Guarda do kill: `IF v_pode_encerrar AND v_status IS NULL THEN` | `:205` |
| Único `EXECUTE IMMEDIATE 'ALTER SYSTEM KILL SESSION ...'` | `:207-209` |
| Handler do comando: -31 dá MARCADA, -30 dá `ALVO_AUSENTE_NO_KILL`, o resto dá ERRO_ORACLE | `:211-220` |
| `registra` fora dos dois handlers; `p_status := v_status` | `:224-227` |

Caminhos de exceção (a semântica de handler em PL/SQL é o esperado pela documentação Oracle, não verificado no banco, L7):
- **Exceção nas etapas 1 a 6** (SELECT com TOO_MANY_ROWS, `UTL_RAW`, `SUBSTRB` da divergência, `SYS_CONTEXT` da etapa 2): cai no handler de `:193`. As duas condições da guarda ficam falsas (`v_status` não nulo e flag FALSE). Basta uma delas para não haver kill.
- **Exceção dentro do próprio handler** (ex.: o `SUBSTRB(SQLERRM)`): sobe para fora da procedure, que não tem handler externo. Não há kill nem `registra`. O Python dá `resultado_desconhecido True`, porque `execute_iniciado` já é True (`oracle_dba.py:1161`, `:1233-1245`). É um falso desconhecido conservador.
- **Exceção na declaração** (`SYS_CONTEXT` de `v_solicitante`): sai da procedure antes do `BEGIN`. Não há kill.
- **Interrupção (ORA-01013) depois do bloco e antes da guarda:** sobe sem handler. Não há kill, e o resultado é desconhecido.
- **`registra` falha depois de ERRO_PRE_KILL ou de um kill:** sobe sem handler, e o resultado é desconhecido. O caso "kill feito, sem auditoria" é o residual já aceito do v1/v2.

Prova automatizada: `test_c1_pkg_estrutura_do_kill_session` (`tests/test_oracle_kill.py:2388`), parametrizado nos dois arquivos. Os mutantes M1-M6, M8 e M14 foram DETECTADOS (`mut_sqlv2_ops.md`), e M7 também (`mut_sqlv2_parte2.md`).

**Limite do teste, verificado por sonda nesta sessão** (`python -I -c`, em memória, sem gravar):
- No handler, a troca por `v_pode_encerrar := NOT FALSE; SELECT NULL INTO v_status FROM dual;` **passa** em todas as asserções atuais do §4b. Ela tornaria o kill alcançável depois de exceção.
- É uma edição deliberada de duas partes. Não está no texto atual, e por isso não bloqueia. O reforço proposto está no §5.

## 2. As 4 decisões aprovadas

| Decisão | Veredito | Onde |
|---|---|---|
| 1. Texto do PKG igual ao de `decisao_c1.md` §1 | conforme. Só o body e a linha de cabeçalho mudaram. Spec, `c_protegidos`, grants e tabela ficaram iguais (hunks `@@ -11` e `@@ -109`) | `ops_kill.sql:14`, `:112-221`; `parte2.sql:85-194` |
| Parte 2 é cópia literal | conforme | `test_c1_parte2_e_copia_literal` (`test_oracle_kill.py:2412`); M7 DETECTADO |
| 2. ERRO_PRE_KILL e ALVO_AUSENTE_NO_KILL dão "NÃO executado" | conforme. Estão em `RECUSAS_PKG_SEM_KILL`. O ramo próprio do ERRO_PRE_KILL leva `MENSAGEM_ERRO_PRE_KILL` (texto fixo, sem `SQLERRM`, sem nome do pacote). O ALVO_AUSENTE_NO_KILL leva a mensagem genérica. Os dois dão `desconhecido False` | `oracle_dba.py:92-96`, `:115-118`, `:1202-1206`; `registrar_decisao_kill` `:2232-2233` |
| ERRO_ORACLE do PKG continua desconhecido | conforme | `oracle_dba.py:1207-1213`; `DESCONHECIDOS_DECLARADOS_PKG` (`test_oracle_kill.py:1491`) |
| 3. A1: `v_type` nulo é recusado | conforme. `IF v_type IS NULL OR v_type <> 'USER'` dá NAO_USUARIO | `ops_kill.sql:181`; M14 DETECTADO |
| 4. Rollback sem `git revert` | conforme. A ordem é gate desligado, depois `rollback_ops_kill_v1.sql`. O Python v2 sem gate não chama o PKG (`oracle_dba.py:361`, `:1096-1101`) | `implantacao.md` §4; `roteiro_janela.md:30-36` |

**Lado Python e fake:**
- K2 roda nos dois arquivos e exige `literais == RECUSAS ∪ EXECUTADO ∪ DESCONHECIDOS` (`test_oracle_kill.py:1532-1550`). A regex não captura a consulta `DBA_SOURCE` (`''(`), o que foi conferido no texto.
- O fake lê o contrato do SQL (`fakes_oracle.py:203-207`) e recusa código fora dele (`:217-221`), com kwarg explícito e sem `**kwargs`. M12 e M13 DETECTADOS.
- Nenhum outro consumidor de `ALVO_NAO_ENCONTRADO` depende do ORA-00030. Os usos em `oracle_dba.py:913`, `:1389` e `:2378` são da reconsulta DIAG (Grep em `src/` e `app.py`).

## 3. Entradas, registros e conta KILL

- **Entradas:** LLM, CLI, Web e o rerun do Streamlit continuam convergindo no único `execute` de `matar_sessao_oracle` (`oracle_dba.py:1162`). O diff não lê ambiente novo, não cria estado compartilhado e não mexe no gate. Concorrência e TOCTOU ficam como em `decisao_c1.md` §8.
- **Registros por desfecho:** iguais a `decisao_c1.md` §9.
  - ERRO_PRE_KILL: linha em `OPS_KILL_AUDIT` com `SQLERRM` (400 B) e `alvo_*` nulos; JSONL com `desconhecido False`; e-mail "NÃO executada"; ao LLM, o texto fixo.
  - `auditoria_oracle.log`: WARNING com `executado=False`, sem mudança de código.
- **Conta KILL:** continua só com EXECUTE no PKG (`ops_kill.sql:236`). Não há privilégio novo.
- **Versões cruzadas, falhando fechado:**
  - Python atual com PKG novo: os códigos novos dão desconhecido.
  - Python novo com PKG v1 e gate ligado por engano: PLS-00306 e desconhecido (T6, `test_item1_intencao.py:637`).

## 4. Evidências conferidas

| Evidência | Conferido |
|---|---|
| Mutantes M1-M14 | 14/14 DETECTADOS, 0 inválidos, com coleta igual entre projeto e cópia (35/35) (`mut_sqlv2_{ops,parte2,od,fake}.md`). As trocas de M1-M8 e M14 foram lidas em `mut_sqlv2_ops.json` |
| Controle negativo | `controle_negativo.txt:289-298`: 9 failed e 26 passed. Os 3 testes que passam no controle (cópia literal, fake recusa e invariantes antigas) são guardas cobertos por M7, M12 e M13 |
| Regressão | `regressao/resumo.txt`: 49 conjuntos, todos com rc=0. A soma dá **235 DETECTADAS**, 0 PASSOU, 0 INVÁLIDAS e 0 ERRO (calculada nesta sessão). Re-ancoragem `m17_..._sqlv2` (`j_r_k2_dba_sqlv2.json`): mesma semântica (ERRO_ORACLE nas recusas), âncora na tupla nova |
| pytest | `parteA_verificacao_b.md`: 1769 passed e 16 skipped. Bate com 1755 (GOVERNANCA_LOG, merge) mais 14 IDs novos (§4b ×2, §4c, §4d 6+1, K2 +2, R1 +2) |
| Greps | 3.2 OK na rodada b. Na rodada a, a falha era a docstring `test_oracle_kill.py:2389` com "ALTER SYSTEM", corrigida. O 3.6 (`medir_subagentes.py:58`) é o mesmo aceito antes (L48) |
| Roteiros | o ensaio 4.1 e a janela têm `DBA_SOURCE`, gate e rollback na ordem certa |

## 5. Mudança mínima proposta (opcional, reforço do teste; não bloqueia)

No `test_c1_pkg_estrutura_do_kill_session`, acrescentar:
```python
assert len(re.findall(r"\bv_pode_encerrar\s*:=", p)) == len(re.findall(r"\bv_pode_encerrar\s*:=\s*(?:TRUE|FALSE)\s*;", p))
assert not re.search(r"\bINTO\b[^;]*\bv_status\b", p, re.S)
```

Resultado da sonda desta sessão, com cada linha (a, b):

| Variante | (a, b) |
|---|---|
| m0 | (True, True) |
| `NOT FALSE` + `SELECT NULL INTO v_status` | (False, False) |
| só `SELECT INTO` | (True, False) |
| só `NOT FALSE` | (False, True) |

Controle negativo: rodar como mutantes M15 (`NOT FALSE` + `SELECT INTO` no handler) e M16 (`SELECT NULL INTO v_status` sozinho). Os dois passam no teste atual (sonda) e precisam ser DETECTADOS com o reforço. É só teste, sem mudar o SQL.

## 6. Observações (não bloqueiam)

- **O1:** o reforço do §5.
- **O2: a conferência `DBA_SOURCE` só prova a presença dos dois códigos, não a estrutura.**
  - Hoje, um body instalado com os códigos e sem a flag passaria.
  - Opção: uma linha a mais na parte 2, `COUNT(*)` das linhas com `v_pode_encerrar` = 4 (declaração, TRUE, FALSE no handler, guarda).
  - É texto de migração: **PENDENTE APROVAÇÃO**.
- **O3: `roteiro_janela.md:22` diz que, se o gate estivesse ligado por engano antes da janela, ele "encerraria a sessão".**
  - Com o PKG v1 instalado, o Python v2 recebe PLS-00306 e dá resultado desconhecido, sem kill (T6).
  - O aviso é conservador, mas impreciso.
  - Além disso, o comentário final de `parte2.sql` ("depois de implantar o Python do item 6") ficou desatualizado com o gate.
- **O4: depois da parte C, o v2 vai para `db/ops_kill.sql`.**
  - Nesse commit, o `test_c1_parte2_e_copia_literal`, o K2 e o `STATUS_CONTRATO_PKG` devem passar a ler também (ou só) `db/ops_kill.sql`.
  - Sem isso, `db/` e a parte 2 podem divergir sem teste.
- **O5:** `tests/test_oracle_kill.py` (17:44) foi alterado depois dos mutantes (17:38) e do controle negativo (17:37). Pelo grep 3.2, a mudança foi a docstring da linha 2389 (inferência: só ela). A regressão (17:52) e a rodada b (17:49) são posteriores. Declarar no commit.

## 7. Residuais e decisões do responsável (PENDENTE APROVAÇÃO)

1. **Texto do pacote**, incluída a conferência `DBA_SOURCE` (e a O2, se for adotada). Commit "PENDENTE APROVAÇÃO".
2. **ERRO_PRE_KILL e ALVO_AUSENTE_NO_KILL sem evidência em sandbox.**
   - A prova do primeiro está só no texto, mais o teste estático.
   - A do segundo está na documentação do ORA-00030 (risco P2).
   - Já aprovado como aceite de risco: só registrar.
3. **Privilégios, grants, `c_protegidos` e hash do `registry/`:** o diff não os toca.
4. **Residuais aceitos, sem mudança:**
   - micro-janela SELECT → ALTER SYSTEM;
   - kill sem auditoria se o `registra` falhar depois do kill;
   - atribuição imprecisa com ORA-00031 em aprovações concorrentes.

## 8. Fato × inferência

- **Fato:** as linhas citadas, as somas do `resumo.txt`, os mtimes e a sonda do §1 e do §5, todos desta sessão.
- **Esperado pela documentação Oracle, não verificado:**
  - escopo do handler PL/SQL;
  - ORA-00030 e ORA-00031;
  - variáveis do INTO depois de TOO_MANY_ROWS.
- **Inferência:** a O5 ter sido só docstring.
