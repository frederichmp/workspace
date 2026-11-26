# Revisão Adversarial — Branch `item6/v2` (`b7bdecb` e `2210b31`)

- **Escopo:** revisão só leitura dos commits `b7bdecb` (código/testes) e `2210b31` (documentação/evidências) na branch `item6/v2`, sem alterar o repositório, sem ler `.env`, sem definir `ORACLE_SANDBOX=1` e sem conexão ao Oracle.
- **Base de referência:** `docs/entregas/1.11/v2_refeito/decisao.md` (em `2210b31`), `docs/plans/1.11-V2-item6.md` §7 (em `2210b31`) e `docs/entregas/1.11/item6/ops_kill.sql` (spec/body v2 propostos).
- **Validação empírica offline:** executada em cópias isoladas de `git archive 2210b31` em `%TEMP%` (sem `.env`, sem `ORACLE_*`/`EMAIL_*`/`GEMINI_*`, só com `_OracleFake`).

---

## 1. Achados (do mais grave para o menos grave)

### A1 — Retorno `p_status = 'ERRO_ORACLE'` do PKG v2 real (após `ALTER SYSTEM KILL SESSION`) é tratado como "NÃO executada" (`resultado_desconhecido=False`) e com texto "executado para" no `resultado_tool`
- **Focos:** 3 (D8), 6 (Fake tautológico), 7 (Mensagens)
- **Arquivo:linha:** `src/tools/oracle_dba.py:870-902`, `src/tools/oracle_dba.py:1746-1748`, `src/tools/oracle_dba.py:1440-1450` (confrontado com `docs/entregas/1.11/item6/ops_kill.sql:187-206`)
- **Severidade:** alta
- **Status:** COMPROVADO
- **Cenário concreto:** No PKG v2 proposto (`ops_kill.sql:187-199`), quando `EXECUTE IMMEDIATE 'ALTER SYSTEM KILL SESSION ... IMMEDIATE'` falha com qualquer erro Oracle diferente de `-30` ou `-31`, o bloco `EXCEPTION WHEN OTHERS` captura o erro dentro do PL/SQL, atribui `v_status := 'ERRO_ORACLE'` e devolve `p_status := 'ERRO_ORACLE'` sem levantar exceção ao `oracledb`. Em `matar_sessao_oracle` (`oracle_dba.py:870-902`), `cursor.execute` termina normalmente; `status_banco` vale `"ERRO_ORACLE"`, não entra em `if status_banco == "ALVO_DIVERGENTE":` (`:872`) e cai no `return` genérico (`:887-902`), **sem `"resultado_desconhecido": True`** e com `mensagem: "Procedimento OPS_OWNER.PKG_OPS_KILL.KILL_SESSION executado para ... Status retornado pelo banco: ERRO_ORACLE."`. Em `registrar_decisao_kill:1746-1748`, `executado` vira `False` e `resultado_desconhecido` vira `False`. Consequentemente, e-mail (`:1441-1449`), CLI (`src/main.py:268`) e Web (`app.py:525`) afirmam **"Intervenção NÃO executada (status ERRO_ORACLE)"**, mesmo após o `ALTER SYSTEM KILL SESSION` ter sido iniciado no banco, enquanto o `resultado_tool` devolvido ao LLM diz `"executado para"`. O mesmo ocorre se `p_status` voltar vazio/nulo (`status_banco == ""` → `resultado_banco = "DESCONHECIDO"`, `resultado_desconhecido = False`, e-mail `"NÃO executada"`).
- **Evidência (sem Oracle):** Em cópia de `git archive 2210b31`, `conduzir_kill_hitl` com `_OracleFake([_linha_alvo(), _linha_alvo()], status_pkg="ERRO_ORACLE")` produziu:
  `resultado_banco="ERRO_ORACLE"`, `executado=False`, `resultado_desconhecido=False`, `email_assunto="[AGENTE DBA] Intervenção NÃO executada: Kill Session 101,202 (status ERRO_ORACLE)"`, `tool_msg="Procedimento OPS_OWNER.PKG_OPS_KILL.KILL_SESSION executado para inst_id=1, sid=101, serial=202. Status retornado pelo banco: ERRO_ORACLE."`.
- **Correção sugerida:** Tratar `status_banco in ("", "ERRO_ORACLE")` (ou qualquer código fora do conjunto conhecido de recusas determinísticas pré-`ALTER SYSTEM`) com `"resultado_desconhecido": True` e mensagem `MENSAGEM_RESULTADO_DESCONHECIDO`, nunca usando o texto genérico `"executado para"` quando `status_banco not in RESULTADOS_KILL_EXECUTADO`.

---

### A2 — Os testes dos 9 binds (`test_item1_intencao.py:218-224` e demais) só validam o lado esquerdo de `=>` e não pegam troca dos placeholders `:bind` no bloco PL/SQL
- **Focos:** 5 (9 binds), 6 (Fake tautológico), 8 (Mutações)
- **Arquivo:linha:** `tests/test_item1_intencao.py:219-220`, `:591-592`, `:612-613`; `tests/test_oracle_kill.py:847-848`; `src/tools/oracle_dba.py:848-856`
- **Severidade:** alta
- **Status:** COMPROVADO
- **Cenário concreto:** Todos os testes que verificam os 9 formais usam apenas `list(binds) == ORDEM_BINDS_KILL_V2` e `re.findall(r"\b(p_\w+)\s*=>", sql) == ORDEM_BINDS_KILL_V2`. A regex captura apenas o parâmetro formal **à esquerda** de `=>`, ignorando completamente o placeholder `:nome` **à direita**. Como `_CursorFake.execute` (`tests/fakes_oracle.py:68-73`) não interpreta o bloco PL/SQL nem associa cada formal ao seu `:bind`, trocar os placeholders no lado direito — como `p_program_esperado => :p_machine_esperado` / `p_machine_esperado => :p_program_esperado`, ou até **`p_sid => :p_serial` / `p_serial => :p_sid`** (invertendo SID e SERIAL# na chamada ao banco!) — compila no Oracle real e **passa sem erro em toda a suíte**.
- **Evidência (sem Oracle):** Em cópia de `git archive 2210b31`, rodando `pytest -q tests/test_item1_intencao.py tests/test_oracle_kill.py`:
  - `M_RHS_SWAP_PROG_MACH` (`p_program_esperado => :p_machine_esperado`, `p_machine_esperado => :p_program_esperado`): `rc=0 | 126 passed, 6 skipped`.
  - `M_RHS_SWAP_SID_SERIAL` (`p_sid => :p_serial`, `p_serial => :p_sid`): `rc=0 | 126 passed, 6 skipped`.
- **Correção sugerida:** Validar pares `(formal, placeholder)` exatos no bloco PL/SQL: `re.findall(r"\b(p_\w+)\s*=>\s*:(p_\w+)\b", sql) == [(n, n) for n in ORDEM_BINDS_KILL_V2]`, e validar no `_CursorFake.execute` que o conjunto de `:binds` no SQL coincide com `set(binds)`.

---

### A3 — Exceção que escapa de `matar_sessao_oracle` após `execute_iniciado=True` cai em `ERRO_INTERNO` com `resultado_desconhecido=False` e dispara e-mail/tela dizendo "NÃO executada"
- **Focos:** 3 (D8)
- **Arquivo:linha:** `src/tools/oracle_dba.py:904-942`, `src/tools/oracle_dba.py:1688-1705`, `src/tools/oracle_dba.py:1742-1748`, `src/tools/oracle_dba.py:1440-1450`
- **Severidade:** alta
- **Status:** COMPROVADO
- **Cenário concreto:** Dentro de `matar_sessao_oracle`, os blocos `except oracledb.Error` (`:904-922`) e `except Exception` (`:923-942`) executam `str(db_err)` e `json.dumps(...)` sem proteção adicional. Qualquer exceção levantada ali (por exemplo, `db_err.__str__()` falhando após `cursor.execute` ter sido iniciado, ou falha de serialização) escapa de `matar_sessao_oracle` e é capturada por `registrar_decisao_kill:1688` (`except Exception`). O JSON construído em `:1694-1705` escreve `"estado no banco não confirmado. Consulte OPS_KILL_AUDIT"`, mas **omite `"resultado_desconhecido": True`**. Na linha `:1748`, `resultado_desconhecido` vira `False`; em seguida, `montar_notificacao_kill` (`:1440-1450`), `src/main.py:268` e `app.py:525` notificam o operador com **"Intervenção NÃO executada (status ERRO_INTERNO)"**, apesar de o `execute` já ter sido enviado à conta KILL (`execs_kill=1`). O mesmo ocorre se `json.loads(resultado_exec)` cair em `:1744-1748` (`resultado_banco="DESCONHECIDO"`, `resultado_desconhecido=False`).
- **Evidência (sem Oracle):** Em cópia de `git archive 2210b31`, `_OracleFake` levantando subclasse de `oracledb.DatabaseError` cujo `__str__` lança `RuntimeError` produziu:
  `execs_kill=1`, `resultado_banco="ERRO_INTERNO"`, `resultado_desconhecido=False`, `email_assunto="[AGENTE DBA] Intervenção NÃO executada: Kill Session 101,202 (status ERRO_INTERNO)"`.
- **Correção sugerida:** Em `registrar_decisao_kill:1694-1705` (e `:1744-1745`), marcar `"resultado_desconhecido": True` sempre que o erro interno não puder garantir ausência de `execute` (ou rastrear explicitamente se `matar_sessao_oracle` chegou a `execute_iniciado`), e proteger `str(db_err)` dentro do `except oracledb.Error` de `matar_sessao_oracle:906`.

---

### A4 — Fake do PKG v2 (`tests/fakes_oracle.py`) é tautológico e permissivo em múltiplos contratos críticos do driver `oracledb` e da spec SQL v2
- **Focos:** 6 (Fake tautológico), 8 (Mutações)
- **Arquivo:linha:** `tests/fakes_oracle.py:16-18`, `:41-54`, `:65-86`; `tests/test_oracle_kill.py:384`, `:953-957`; `tests/test_item1_intencao.py:58-61`
- **Severidade:** alta
- **Status:** COMPROVADO
- **Cenário concreto:** Os testes mock continuam 100% verdes diante de divergências concretas entre Python e Oracle/PKG v2 real:
  1. **`status_var` ignora `size=` e nasce pré-populada (`fakes_oracle.py:79-85`):** `_CursorFake.var()` descarta `*args, **kwargs` e já preenche `status_pkg` na criação da `var` (antes do `execute`). Reduzir `size=128` para `size=8` em `oracle_dba.py:840` — que no Oracle real causaria `ORA-06502` ao gravar `"ALVO_DIVERGENTE"` (15 bytes) ou `"ALVO_NAO_ENCONTRADO"` (19 bytes) — passa em todos os testes (`M_STATUS_VAR_SIZE_8`).
  2. **`_VarFake.setvalue(pos, valor)` ignora `pos` e não valida o tipo (`fakes_oracle.py:47-48`):** aceita `str`, `pos != 0` ou `datetime` tz-aware em `DB_TYPE_DATE`, que falhariam no driver real (`IndexError`/`TypeError`/`DPY-3002`).
  3. **`_CursorFake.description` é fixa (`COLUNAS_ALVO`, `fakes_oracle.py:65`) e T8 só checa `\blogon_time\b` no texto (`test_oracle_kill.py:956`):** remover `logon_time` da lista de colunas do `SELECT` mantendo `-- logon_time` em comentário SQL (`M_LOGON_COMENTARIO_NO_SELECT`), ou mover `serial#` fora do índice `row[2]` (`oracle_dba.py:644`), passa em T8 e nos 126 testes.
  4. **Cópia manual da assinatura v2 sem vínculo com o SQL:** `ORDEM_BINDS_KILL_V2` repete a premissa manual do `decisao.md` (`db/ops_kill.sql` ainda está na v1; `test_oracle_kill.py:384` confere `USUARIOS_PROTEGIDOS` só contra a v1). Qualquer divergência real de nome/tipo no PKG v2 ou de `LENGTHB > 128` (bytes UTF-8 vs `len()` em caracteres no Python, `oracle_dba.py:85, 709`) não é detectada.
  5. **Ausência de simulação de `status_pkg="ERRO_ORACLE"`** (`ops_kill.sql:196`), ocultando o defeito A1.
- **Evidência (sem Oracle):** Em cópia de `git archive 2210b31`:
  - `M_STATUS_VAR_SIZE_8`: `rc=0 | 126 passed, 6 skipped`.
  - `M_LOGON_COMENTARIO_NO_SELECT`: `rc=0 | 126 passed, 6 skipped`.
- **Correção sugerida:** No fake, armazenar `size` em `_VarFake` (validando `len(status_pkg) <= size` e populando `p_status` somente dentro de `execute()`), validar `pos == 0` e `isinstance(valor, datetime)` para `DB_TYPE_DATE`, derivar `cursor.description` das colunas reais do `SELECT` (ou checar `SELECT ... logon_time ... FROM`), e adicionar cenário com `status_pkg="ERRO_ORACLE"`.

---

### A5 — Residual 1 (`docs/plans/1.11-V2-item6.md` §7.2) subdimensiona os vazamentos de `ORACLE_DSN`, `host:porta`, usuários protegidos e SQL ao LLM (Gemini em failover)
- **Focos:** 7 (Vazamento ao LLM)
- **Arquivo:linha:**
  - Fluxo de kill: `src/tools/oracle_dba.py:935` (ramo D8, tocado em `b7bdecb` e **ausente do R1**), `:814`, `:817`, `:595`, `:669` (propagado via `:1891` e `:1094`), `:896`, `:906`, `:908`, `:929`, `:1596`.
  - Ferramentas DIAG no mesmo módulo (enviadas como `role: "tool"` em `app.py:407` e `src/main.py:433`): `coletar_sessoes_ativas` (`oracle_dba.py:163, 179, 183, 186, 239, 253, 256, 265, 268`), `coletar_top_sql` (`:300, 316, 320, 323, 344, 366, 378, 379`), `coletar_plano_execucao` (`:427, 443, 447, 450, 487, 499`).
  - Exceções genéricas de ferramentas: `app.py:395`, `src/main.py:418`.
  - Teste T7: `tests/test_oracle_kill.py:905-937`.
- **Severidade:** média
- **Status:** COMPROVADO
- **Cenário concreto:** O plano §7.2 comprovou que, com o Ollama (11434) offline, `role: "tool"` vai ao Gemini em nuvem, e classificou o **Residual 1** como pré-requisito do ensaio sandbox — porém R1 listou apenas `"instancia": dsn` em 3 ramos de `matar_sessao_oracle` (`:795`, `:811`, `:915` na numeração v2). Mesmo que esses 3 pontos sejam corrigidos:
  1. `matar_sessao_oracle:935` (`except Exception`, D8) continua enviando `"instancia": dsn` no `resultado_tool` (e T7 não cobre o ramo D8 nem inclui o DSN em `proibidos`);
  2. `matar_sessao_oracle:814, 817` e `consultar_alvo_sessao_diag:595` continuam enviando `host:porta` (extraídos do DSN) e `erro_rede` no texto de `mensagem`/`detalhe_rede`;
  3. `consultar_alvo_sessao_diag:669` (via `preparar_intervencao_kill:1891` e `executar_kill_verificado:1094`) envia o `username` protegido (`STARTUPADMIN`, `OPS_OWNER`, etc.) ao LLM; `registrar_decisao_kill:1596` envia o identificador do aprovador humano; `:906/:908/:929` enviam `str(db_err)`/`str(exc)` crus; `:896` envia `OPS_OWNER.PKG_OPS_KILL.KILL_SESSION`;
  4. `coletar_sessoes_ativas:239` e `coletar_top_sql:366` enviam `"instancia": dsn` **em toda chamada bem-sucedida**, além de `sql_text_curto` (`:344`) e `DBMS_XPLAN` formato `'TYPICAL'` (`:487`, que traz *Predicate Information* com literais de queries reais). *(Adicionalmente, `src/tools/executor.py:810, 848, 867, 886, 908, 927` também retorna `"instancia": dsn`, embora ainda não esteja conectado ao loop do LLM.)*
- **Evidência (sem Oracle):** `PROBE3_D8_EMAIL_AND_DSN` em cópia de `git archive 2210b31` confirmou `tool_tem_dsn=True`, `instancia_em_tool="host-teste:1521/TESTE"` no cenário T9 (D8); `git grep` confirmou todas as 15 ocorrências de `"instancia": dsn` e 5 de `check_rede['host']:{porta}` em `src/tools/oracle_dba.py`.
- **Correção sugerida:** Ampliar o escopo da tarefa de saneamento do Residual 1 (pré-requisito do sandbox) para cobrir `:935`, `host:porta` (`:183, :320, :447, :595, :814`), todas as ocorrências de `"instancia": dsn` em `coletar_*` e `executor.py`, sanitizar `str(exc)`/`str(db_err)` e remover `username` protegido/`aprovador` do `resultado_tool`; incluir o DSN fictício na lista `proibidos` de T7 e adicionar caso D8 a T7.

---

### A6 — Quatro testes `@pytest.mark.sandbox_only` não foram migrados para a assinatura v2 nem receberam o gate `OPS_KILL_PKG_VERSAO`
- **Focos:** 2 (Fallback / assinatura v1), 4 (`ref_aprovacao`), 6 (Fake tautológico)
- **Arquivo:linha:** `tests/test_oracle_kill.py:1038`, `:1052`, `:1060`, `:1086`
- **Severidade:** média
- **Status:** COMPROVADO
- **Cenário concreto:** `decisao.md` §7 (linha 107) e `docs/plans/1.11-V2-item6.md` §4.4 declaram: *"Os sandbox migrados ficam em skip com gate `OPS_KILL_PKG_VERSAO`"*. Na branch `item6/v2`, porém, não existe qualquer referência a `OPS_KILL_PKG_VERSAO` em `tests/` (`git grep` vazio), e os 4 testes `sandbox_only` (`test_sandbox_kill_sessao_valida_encerrada`, `test_sandbox_kill_alvo_nao_encontrado`, `test_sandbox_kill_param_invalido`, `test_sandbox_kill_propria_sessao_ou_usuario_protegido`) continuam chamando `matar_sessao_oracle(sid=..., serial=..., inst_id=...)` sem `identidade_esperada` nem `ref_aprovacao`. Como ficaram em skip (`ORACLE_SANDBOX` ausente), a quebra passou despercebida: no momento em que o ensaio sandbox rodar, todos os 4 falharão com `TypeError` (e `:1038` vazará a conexão aberta `conn_alvo` antes do `conn_alvo.close()` em `:1044`).
- **Evidência (sem Oracle):** `PROBE5_SANDBOX_CALL` reproduzindo `:1052` lançou `TypeError: matar_sessao_oracle() missing 2 required keyword-only arguments: 'identidade_esperada' and 'ref_aprovacao'`; `git grep OPS_KILL_PKG_VERSAO 2210b31 -- tests/` retornou vazio.
- **Correção sugerida:** Migrar os 4 testes `sandbox_only` (incluindo leitura de `username, program, machine, logon_time` da `GV$SESSION`, `ref_aprovacao` válido e `try/finally` para fechar `conn_alvo`) com o gate `OPS_KILL_PKG_VERSAO` antes do ensaio sandbox 4.1.

---

### A7 — Oito mutantes relevantes fora de `m1–m16` sobrevivem integralmente à suíte de testes do kill (`126 passed, 6 skipped`)
- **Focos:** 8 (Mutações), 2 (Fallback), 3 (D8), 5 (9 binds), 6 (Fake)
- **Arquivo:linha:** `src/tools/oracle_dba.py:616`, `:709`, `:840-843`, `:849-853`, `:872`, `:1118`
- **Severidade:** média
- **Status:** COMPROVADO
- **Cenário concreto:** Além das duas trocas de placeholder no lado direito de `=>` (já detalhadas em **A2**) e das duas ligadas ao fake (`M_STATUS_VAR_SIZE_8` e `M_LOGON_COMENTARIO_NO_SELECT`, em **A4**), outras **4 mutantes relevantes** violam contratos explícitos de `decisao.md` e passam nos 126 testes de `tests/test_item1_intencao.py` + `tests/test_oracle_kill.py`:
  1. **`M_EXEC_INICIADO_ANTES_VAR` (`oracle_dba.py:840-843`):** mover `execute_iniciado = True` para antes da criação de `status_var`/`logon_var` e de `logon_var.setvalue(...)` — viola `decisao.md` §3 ("As duas `var` e o `setvalue` ficam antes de `execute_iniciado = True`. Erro ali prova que o PKG não rodou"). Nenhum teste injeta exceção em `cursor.var()` ou `setvalue()`.
  2. **`M_EXEC_KILL_GET_DEFAULT` (`oracle_dba.py:1118`):** trocar `{c: alvo_reconsulta[c] for c in CAMPOS_IDENTIDADE_ESPERADA if c in alvo_reconsulta}` por `{c: alvo_reconsulta.get(c) for c in CAMPOS_IDENTIDADE_ESPERADA}` — viola `decisao.md` §2 ("com indexação só das chaves presentes, sem `.get` com default"). Se `program` ou `machine` faltar no dict da reconsulta, `.get` converte em `None` e **conecta na conta KILL** em vez de recusar localmente com `PARAM_INVALIDO`.
  3. **`M_FALLBACK_V1_NO_NAO_ENCONTRADO` (`oracle_dba.py:872`):** adicionar `cursor.execute` com o bloco v1 de 4 binds quando `status_banco == "ALVO_NAO_ENCONTRADO"` (mesmo padrão da `m16`, porém `test_kill_ponto_unico_de_chamada` só cobre `ENCERRADA`, `ALVO_DIVERGENTE` e `erro_no_execute`, e `test_item1_intencao.py:440-552` só conta `conexoes_kill`, não `execute`s no mesmo cursor).
  4. **`M_LIMITE_GE_128` (`oracle_dba.py:709`):** trocar `len(valor) > LIMITE_TEXTO_IDENTIDADE` por `>=`, rejeitando indevidamente valores legítimos de 128 caracteres (não há teste de fronteira com `len == 128` nem `len == 1`).
  - *(Adicional — **HIPÓTESE** não executada: relaxar `_REGEX_ID_INTERVENCAO` em `oracle_dba.py:42` para `[0-9a-z]{32}`; T2 em `test_oracle_kill.py:788-793` não testa caractere minúsculo fora de `a-f`, como `"g"*32`.)*
- **Evidência (sem Oracle):** Todas as 8 mutantes executadas em cópia de `git archive 2210b31` contra `pytest -q -p no:cacheprovider tests/test_item1_intencao.py tests/test_oracle_kill.py` terminaram com `rc=0 | 126 passed, 6 skipped`.
- **Correção sugerida:** Adicionar testes para: (a) erro em `cursor.var()` / `setvalue()` retornando `resultado_desconhecido=False`; (b) chave `program`/`machine` ausente na reconsulta retornando `PARAM_INVALIDO` sem conexão KILL; (c) contagem `len(execucoes_kill) == 1` nos demais status de recusa do PKG em `test_item1_intencao.py:539`; (d) casos válidos de fronteira `len == 128` / `len == 1` e `ref="g"*32` inválido em T2.

---

### A8 — `matar_sessao_oracle` permanece exportada publicamente em `src/tools/__init__.py` e aceita `ref_aprovacao` sintático sem vínculo com `INTENCAO`
- **Focos:** 1 (TOCTOU / fronteira de decisão), 4 (`ref_aprovacao`)
- **Arquivo:linha:** `src/tools/__init__.py:6`, `:30`; `src/tools/oracle_dba.py:735-742`, `:770`
- **Severidade:** média
- **Status:** COMPROVADO
- **Cenário concreto:** Embora `identidade_esperada` e `ref_aprovacao` sejam keyword-only obrigatórios sem default, `matar_sessao_oracle` continua exportada na API pública do pacote `src.tools` (`__all__`). Qualquer chamador interno ou script futuro que importe `from src.tools import matar_sessao_oracle` pode invocar a conta KILL diretamente fornecendo `identidade_esperada` arbitrária e um `ref_aprovacao` fabricado (ex.: `"0"*32`), sem passar por HITL, sem gravar `INTENCAO` no JSONL e sem verificação prévia de aprovação (conhecido conceitualmente em `decisao.md` §10 — "o ref não é autorização" —, mas mantido exposto em `__all__`).
- **Evidência (sem Oracle):** `git grep -n matar_sessao_oracle 2210b31 -- src/tools/__init__.py` confirma exportação nas linhas 6 e 30; `test_t3_nove_binds_valores_exatos` (`tests/test_oracle_kill.py:839`) invoca `matar_sessao_oracle` diretamente com `REF_VALIDO` fixo sem `INTENCAO`.
- **Correção sugerida:** Remover `matar_sessao_oracle` de `src/tools/__init__.py` (ou renomeá-la como interna `_matar_sessao_oracle`), expondo apenas `preparar_intervencao_kill`, `registrar_decisao_kill` e `conduzir_kill_hitl`.

---

### A9 — E-mail do ramo D8 (`montar_notificacao_kill`) ainda afirma "retornou erro do Oracle" para exceções não-Oracle
- **Focos:** 3 (D8)
- **Arquivo:linha:** `src/tools/oracle_dba.py:1423`
- **Severidade:** baixa
- **Status:** COMPROVADO
- **Cenário concreto:** Em `b7bdecb` (`conferencia_b.md` §3), o texto `"erro do Oracle a partir da chamada ao PKG"` foi corrigido para `"erro a partir da chamada ao PKG"` em `app.py:513` e `src/main.py:260` para refletir corretamente exceções não-Oracle do D8. Entretanto, `montar_notificacao_kill` (`oracle_dba.py:1423`) manteve o literal `"a chamada ao PKG_OPS_KILL retornou erro do Oracle."`. No cenário T9 (`RuntimeError` em `status_var.getvalue()`), o assunto e a tela dizem erro genérico/desconhecido, mas o corpo do e-mail afirma falsamente erro do Oracle.
- **Evidência (sem Oracle):** `PROBE3_D8_EMAIL_AND_DSN` confirmou `email_corpo_tem_erro_do_oracle=True` com `erro_getvalue_status=RuntimeError("boom")`.
- **Correção sugerida:** Trocar `"retornou erro do Oracle"` por `"falhou a partir da execução"` (ou `"teve erro após o início da execução"`) em `src/tools/oracle_dba.py:1423`.

---

### A10 — String vazia `""` em `program`/`machine` passa na validação local mas diverge entre hash Python (`"" != None`) e semântica Oracle (`'' IS NULL`)
- **Focos:** 1 (TOCTOU / injetividade do hash), 6 (Fake tautológico)
- **Arquivo:linha:** `src/tools/oracle_dba.py:703-709`, `:724-725`, `:982`
- **Severidade:** baixa
- **Status:** COMPROVADO
- **Cenário concreto:** `_texto_identidade_invalido("", aceita_none=True)` (`:709`) retorna `False` (aceito), pois só rejeita `len < 1` quando `not aceita_none`. No Oracle, porém, um bind `VARCHAR2` com string vazia `""` equivale a `NULL` (`UTL_RAW.CAST_TO_RAW('') IS NULL`), empatando com `program IS NULL` na `GV$SESSION`, enquanto no Python `calcular_hash_identidade` produz hashes distintos para `""` e `None`. Além disso, `preparar_intervencao_kill` (`:1898-1916`) não valida `identidade_esperada` (ex.: `logon_time=None`) antes de exibir o prompt HITL, gravando `INTENCAO` na aprovação para só recusar depois com `PARAM_INVALIDO` em `matar_sessao_oracle:770`.
- **Evidência (sem Oracle):** `PROBE4_EMPTY_STR` confirmou `campos_invalidos_identidade_e_ref(..., program="", machine="") == []` e `hash("") != hash(None)`.
- **Correção sugerida:** Em `_texto_identidade_invalido`, recusar `len(valor) < 1` também quando `aceita_none=True` (no Oracle `GV$SESSION`, ausência sempre chega como `None`, nunca `""`), alinhando validação local, hash e comparação no PKG.

---

## 2. Resumo por foco (1 a 8)

| Foco | Situação | Achados / observação |
|---|---|---|
| **1. TOCTOU** | Parcial (com ressalvas) | No fluxo HITL, a identidade vai da reconsulta (após hash com `logon_time` injetivo em naive/0µs) ao PKG v2; achados **A8** (`matar_sessao_oracle` pública em `src/tools/__init__.py`) e **A10** (`""` vs `None`). No MODELO atual (PKG v1), ainda não há checagem no servidor. |
| **2. Fallback** | Produção OK; testes com lacunas | Produção tem ponto único de 9 binds (`oracle_dba.py:844-869`), sem fallback v1. Achados **A6** (4 testes sandbox ainda na assinatura v1 sem gate) e **A7** (`M_FALLBACK_V1_NO_NAO_ENCONTRADO` sobrevive). |
| **3. D8** | Falhas graves pós-`execute` | Sem retentativa automática em produção, mas **A1** (`p_status='ERRO_ORACLE'` do PKG v2 real vira `resultado_desconhecido=False` + `"NÃO executada"`), **A3** (exceção escapando para `ERRO_INTERNO` pós-`execute` vira `resultado_desconhecido=False` + `"NÃO executada"`) e **A9** (corpo do e-mail ainda diz `"erro do Oracle"`). |
| **4. `ref_aprovacao`** | Assinatura OK; lacunas laterais | Keyword-only sem default em `matar_sessao_oracle` e `executar_kill_verificado`; `app.py`/`src/main.py` sempre passam por `registrar_decisao_kill` (`id_intervencao`). Lacunas em **A6** (testes sandbox) e **A8** (exportação pública aceita ref fabricado). |
| **5. 9 binds** | Nomes/ordem OK; teste cego no RHS | Os 9 nomes e a ordem em `oracle_dba.py:848-868` batem com `decisao.md` e `ops_kill.sql`. Achado **A2**: `test_item1_intencao.py:218-224` não detecta placeholders `:bind` trocados à direita de `=>` (`M_RHS_SWAP_SID_SERIAL` e `M_RHS_SWAP_PROG_MACH` passam). |
| **6. Fake tautológico** | Falhas relevantes | **A4** (ignora `size=`, pré-popula `p_status` antes do `execute`, `setvalue` sem validação de tipo/pos, `description` fixa, não valida `:binds` nem SQL v2) e **A1** (não testa `status_pkg='ERRO_ORACLE'` como no `ops_kill.sql:196`). |
| **7. Vazamento ao LLM** | Escopo R1 insuficiente | **A5**: R1 omitiu `oracle_dba.py:935` (D8), `host:porta` (`:595, :814`), `username` protegido (`:669`), `aprovador` (`:1596`), `str(db_err)`/`str(exc)` e todas as ocorrências de `"instancia": dsn` / `host:porta` / SQL / `DBMS_XPLAN` em `coletar_*` que vão ao Gemini via `role: "tool"`. |
| **8. Mutações** | 8 mutantes relevantes não cobertas | **A7** (junto com **A2** e **A4**): 8 mutantes comprovadamente sobrevivem aos 126 testes (`M_RHS_SWAP_PROG_MACH`, `M_RHS_SWAP_SID_SERIAL`, `M_STATUS_VAR_SIZE_8`, `M_EXEC_INICIADO_ANTES_VAR`, `M_EXEC_KILL_GET_DEFAULT`, `M_FALLBACK_V1_NO_NAO_ENCONTRADO`, `M_LOGON_COMENTARIO_NO_SELECT`, `M_LIMITE_GE_128`), além da hipótese de regex `ref="g"*32`. |

---

## 3. Limites da revisão

- **Sem execução contra Oracle:** comportamento real do `python-oracledb` em modo Thin (incluindo `DB_TYPE_DATE`, `ORA-06502`, `PLS-00306` real, `UTL_RAW.CAST_TO_RAW` com charset do MODELO e `NLS_COMP=BINARY_CI`) foi avaliado por análise estática contra `docs/entregas/1.11/item6/ops_kill.sql` e `decisao.md`, não em banco.
- **`.env` real e `ORACLE_SANDBOX=1` não usados:** os 16 testes `sandbox_only` não foram executados; a quebra dos 4 testes em `tests/test_oracle_kill.py:1038-1086` foi comprovada pela chamada direta com a mesma assinatura em Python.
- **Escopo das mutações executadas:** as 8 mutantes foram medidas sobre `tests/test_item1_intencao.py` e `tests/test_oracle_kill.py` (mesmo conjunto de `mut_item6_a2.md`/`b2.md`/`m16_depois.md`), não sobre os 1290 testes completos; `test_fluxo_cli.py` e `test_fluxo_web.py` não validam `sql_executado` nem os 9 binds, portanto não alterariam a sobrevivência dessas mutantes.
