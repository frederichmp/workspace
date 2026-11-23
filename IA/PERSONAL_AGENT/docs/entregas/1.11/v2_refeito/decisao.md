# Decisão: 1.11-V2-item6, passo 3 (passo 0 do 1.11-V2)

- Quem: subagente `seguranca`, modelo `claude-opus-5-5`. Só leitura, sem Oracle, sem pytest.
- Base conferida agora: branch `item6/v2`, HEAD `6f564e3` (`git log -1`); `git status --short -- src app.py tests` vazio.
- Fontes: `docs/plans/1.11-V2-item6.md` §3, §4.1, §4.3, §4.4; `docs/plans/1.11-V2.md:28-38` (passo 0) e `:40-62`; `docs/entregas/1.11/item6/implantacao.md` §1-§2 e §6; spec e body v2 propostos em `docs/entregas/1.11/item6/ops_kill.sql:56-207`.
- **Veredito: CONFORME.** Os pontos do passo 0 ficam decididos abaixo. Nenhum deles cria PENDENTE novo para o responsável antes do passo 4. Os PENDENTES que já existem estão no §9.

## 1. Fatos verificados no código atual (v1, `6f564e3`)

| Fato | Onde |
|---|---|
| `matar_sessao_oracle(sid, serial, inst_id)`, posicional, sem identidade nem ref | `src/tools/oracle_dba.py:689` |
| Validação local só de inst/sid/serial, antes do `getenv` | `:697-712`; `getenv` em `:715-717` |
| `status_var` criado antes de `execute_iniciado = True`; bloco com 4 formais | `:767-784` (`KILL_SESSION(` em `:772`) |
| `except oracledb.Error` marca `resultado_desconhecido = execute_iniciado`; o `except Exception` **não marca** | `:804-822` e `:823-835` |
| A mensagem de sucesso é genérica ("Procedimento ... executado ... Status retornado: X") para qualquer `p_status` | `:795-799` |
| `CAMPOS_IDENTIDADE_ALVO` sem `logon_time` | `:77` |
| `_normalizar_valor_identidade`: `datetime` cai no `str(valor)` por exceção do `float()` | `:853-865` |
| Hash: SHA-256 de `json.dumps(sort_keys=True, ensure_ascii=False, default=str)` | `:874-882` |
| `executar_kill_verificado(inst_id, sid, serial, hash_aprovado, *, aprovacao_expirada)`, sem ref | `:906-913`; chamada a `matar` em `:1002` |
| SELECT DIAG sem `logon_time`; `serial#` lido por posição `row[2]` | `:592-607`, `:630` |
| `id_intervencao = uuid.uuid4().hex`, gerado uma vez por chamada | `:1408`; validado na INTENCAO em `:1133` |
| O `resultado_tool` do LLM é o JSON de `matar_sessao_oracle` mais decisao/resultado_banco/executado | `:1691-1694` |
| JSONL com `default=str` (datetime vira `"YYYY-MM-DD HH:MM:SS"`) | `:1097` |
| O LLM só fornece inst_id/sid/serial: `preparar` lê só essas 3 chaves | `:1725-1727` |
| O schema de `matar_sessao_oracle` não tem `additionalProperties: False` | `:1916-1936` |
| CLI: `conduzir_kill_hitl(argumentos)`, log de `resultado_tool` | `src/main.py:372-377`, `:427` |
| Web: pendência copiada e limpa antes da chamada; log e LLM | `app.py:423`, `:441`, `:445-455`, `:538`, `:541-548` |
| Fake: `description` fixa (ignora a lista do SELECT); `var()` sempre devolve `status_pkg` | `tests/fakes_oracle.py:48`, `:61-62` |
| Teste do §4.3: hoje confere o conjunto dos 4 binds | `tests/test_item1_intencao.py:210-212` |
| `test_inst_id_ausente...` espera `TypeError` em `matar_sessao_oracle(sid=10, serial=20)` | `tests/test_oracle_kill.py:429-430` |

Comportamento **esperado pela documentação, não verificado em banco** (L7): o PKG v2 valida (`ops_kill.sql:119-128`). Num único SELECT, ele lê o alvo e compara username/program/machine como RAW e `logon_time` por `DECODE` (`:141-152`). Com divergência, devolve `ALVO_DIVERGENTE` sem kill (`:160-168`). Grava `ref_aprovacao` em `OPS_KILL_AUDIT` numa transação autônoma (`:75-90`, `:203-205`). Devolve em `p_status` **só o código** (`:206`). O MODELO está na v1, com a parte 2 bloqueada (1.11-V2:15).

## 2. D1: validação local (camada adicional); o PKG é a autoridade

Onde: só em `matar_sessao_oracle`, antes do `getenv`. Ordem fixa:
1. inst/sid/serial: código e mensagem atuais **inalterados**. Assim `test_kill_param_invalido_sem_conexao` só muda a chamada.
2. `identidade_esperada`:
   - tem de ser `dict` com as chaves **exatamente** `{"username","program","machine","logon_time"}`; chave faltando ou sobrando dá PARAM_INVALIDO;
   - `username`: `str` com `len >= 1`;
   - `program` e `machine`: `None` ou `str`;
   - `logon_time`: `isinstance(datetime)`, `tzinfo is None` e `microsecond == 0` (D3d). `date` puro e `str` são recusados.
3. `ref_aprovacao`: `isinstance(str)` **antes** de `_REGEX_ID_INTERVENCAO.fullmatch` (`:42`). Sem o `isinstance`, `bytes` levantaria `TypeError` fora do `try`.
4. Só então vêm `getenv`, rede, `connect`.

Decisões de detalhe:
- **Nenhuma transformação** dos valores: nem `strip`, `upper`, `str()` ou `encode`. Vai ao bind o valor cru da reconsulta. O PKG compara bytes (RAW), então qualquer transformação daria ALVO_DIVERGENTE e bloquearia kill legítimo. `None` vai como `None`, nunca `"None"` nem `""`.
- **Limite de tamanho:** localmente, 128 **caracteres** (`len(s) > 128` dá PARAM_INVALIDO); 128 **bytes** só no PKG (`LENGTHB`, `:123-125`), que é a autoridade. Bytes UTF-8 no Python dariam falso positivo se o charset do banco for de 1 byte: o charset do MODELO não foi lido (L7). Um valor de até 128 bytes na `GV$SESSION` tem sempre até 128 caracteres. Por isso o limite local nunca recusa alvo legítimo e só barra defeito.
- A validação é **total**: nunca levanta exceção, para qualquer tipo de entrada. Entrada inválida dá sempre PARAM_INVALIDO.
- Em `executar_kill_verificado`, a identidade é montada **depois** do hash, da elegibilidade e do TTL, a partir de `reconsulta["alvo"]`, com indexação só das chaves presentes, sem `.get` com default. A falta de chave fica para a checagem de chaves do passo 2. Constante nova `CAMPOS_IDENTIDADE_ESPERADA = ("username","program","machine","logon_time")`. `CAMPOS_IDENTIDADE_ALVO` passa a ser `("inst_id","sid","serial#") + CAMPOS_IDENTIDADE_ESPERADA`, para que todo campo enviado ao PKG esteja no hash. Pela L23, essa invariante vira teste.
- Fonte dos esperados: a **reconsulta cujo hash bateu** (1.11-V2:45), mantida. Alternativa considerada e não adotada: enviar o `alvo` aprovado. Ela só difere se a normalização do hash não for injetiva, e o D3 a torna injetiva no domínio validado, com os testes T4 e T8 como controle.

Autoridade: a validação local só evita conexão KILL inútil. O PKG v2 revalida tudo (`:119-128`) e compara com a `GV$SESSION` viva. Contra o PKG v1, a chamada não compila (PLS-00306); ver D6.

## 3. D2: `logon_time` comparado no servidor; tipo do bind

- **Bind:** `var_logon = cursor.var(oracledb.DB_TYPE_DATE)` e `var_logon.setvalue(0, logon_time)`, passados como `p_logon_time_esperado=var_logon`. Foi escolhido no lugar de `setinputsizes`, que associa o tipo por nome. Pela L17, um nome errado poderia ser ignorado em silêncio, e com a `var` o tipo está no próprio objeto do bind. Também não depende do tipo-padrão do driver para `datetime`, que não foi conferido. Nunca há `str` nem `TO_DATE`, para não depender de `NLS_DATE_FORMAT`.
- As duas `var` (status e logon) e o `setvalue` ficam **antes** de `execute_iniciado = True`. Erro ali prova que o PKG não rodou.
- **TOCTOU:**
  - a reconsulta DIAG (t1) é pré-checagem;
  - a comparação com valor de autoridade acontece **no servidor**, no mesmo SELECT que lê o alvo e na mesma chamada PL/SQL do `ALTER SYSTEM` (t2, `ops_kill.sql:141-188`);
  - o Python não faz "compara e depois mata" em duas idas ao banco;
  - resta a micro-janela SELECT → ALTER SYSTEM dentro do PKG, já aceita (`implantacao.md:33-36`). O comando é endereçado por sid+serial#, e um SID reutilizado dá ORA-00030;
  - o `logon_time` de uma sessão (sid,serial#) não muda; ele só discrimina a reutilização de serial# (inferência).
- **Hoje, no MODELO (v1), não existe comparação no servidor.** A garantia acima só vale depois da parte 2 e do ensaio 4.1.

## 4. D3: hash (composição, formato, quem confere)

- **Composição:** SHA-256 de `json.dumps(identidade, sort_keys=True, ensure_ascii=False, default=str)` sobre `inst_id, sid, serial#, username, program, machine, logon_time`. Ficam de fora `status`, `sql_id`, `event`, `type`, o timestamp, o `ref_aprovacao` e o aprovador.
- **Formato canônico de `logon_time`:** ramo explícito em `_normalizar_valor_identidade`, antes da tentativa com `float`: `isinstance(valor, datetime)` devolve `valor.isoformat(sep=" ")`. É idêntico a `str(dt)` e ao que `_codificar_linha` grava no JSONL (`:1097`). Assim o hash pode ser **recalculado a partir da linha INTENCAO** (auditoria offline). O formato com `T` quebraria isso e é usado como mutação.
- **Quem confere:**
  - (a) o Python, só em `executar_kill_verificado`, na reconsulta (`:948-949`): divergência dá ALVO_ALTERADO com 0 conexões KILL;
  - (b) o PKG **não** recebe o hash. Ele confere os 4 valores contra a `GV$SESSION` (ALVO_DIVERGENTE);
  - (c) o auditor liga a linha de `OPS_KILL_AUDIT` à linha do JSONL pelo `ref_aprovacao`, e a linha do JSONL traz `hash_payload` e `alvo`;
  - (d) o aprovador confere os campos exibidos. O `logon_time` passa a aparecer na CLI (`main.py:216-222`) e no painel Web (`app.py:~824`).
- **Efeito:** aprovações pendentes do deploy anterior dão ALVO_ALTERADO, e a falha é fechada (1.11-V2:87).

## 5. D4: `ref_aprovacao` keyword-only, obrigatório, sem default

- `matar_sessao_oracle(sid, serial, inst_id, *, identidade_esperada, ref_aprovacao)`.
- `executar_kill_verificado(inst_id, sid, serial, hash_aprovado, *, aprovacao_expirada, ref_aprovacao)`.
- Nenhum default nos dois.
- `registrar_decisao_kill` passa `ref_aprovacao=id_intervencao`, a mesma variável de `:1408` já gravada na INTENCAO (`:1503-1515`). Nenhum outro chamador existe em `src/` ou `app.py`; conferido por Grep.
- O LLM não fornece nem vê o ref. `preparar` ignora chaves extras (`:1725-1727`), inclusive `ref_aprovacao`, `logon_time` ou `username` vindos do LLM. O schema continua inalterado.
- **Ajuste obrigatório em `test_oracle_kill.py:430`:** a chamada `matar_sessao_oracle(sid=10, serial=20)` precisa passar `identidade_esperada` e `ref_aprovacao` válidos. Sem isso, o `TypeError` esperado passa a vir dos keyword-only e não da falta de `inst_id`, e a asserção fica vazia. É mudança só de chamada.

## 6. D5: mensagens sem SQL, credenciais nem detalhe desnecessário

- **PARAM_INVALIDO local (identidade/ref):** texto fixo que só **nomeia** os campos ("campos inválidos: logon_time"). Nunca ecoa valor nem ref. Status `recusado`, `status_banco` `PARAM_INVALIDO`.
- **ALVO_DIVERGENTE:**
  - o Python só recebe o código, então não tem o que vazar. O `matar_sessao_oracle` não pode usar o texto genérico "executado" (`:795-799`) para esse status;
  - texto: "A identidade da sessão no banco diverge da aprovada (verificação do PKG_OPS_KILL). Encerramento NÃO executado. Campos e valores só em OPS_KILL_AUDIT";
  - fica fora de `RESULTADOS_KILL_EXECUTADO` (`:74`);
  - CLI e Web caem no ramo "NÃO executada" existente (`main.py:267-271`, `app.py:523-528`), e o e-mail cai no ramo "NÃO executada" (`:1317-1327`), sem os valores de identidade;
  - a tela **pode** mostrar `id_intervencao`, que não é exigido. O `resultado_tool` não.
- **`resultado_tool` e `auditoria_oracle.log`** (`main.py:427`, `app.py:538`): o JSON de `matar_sessao_oracle` nunca leva `ref_aprovacao`, `identidade_esperada`, o texto do bloco nem usuário ou senha.
- **ERRO_ORACLE:** continua com `str(db_err)`, o texto do Oracle. Pela documentação, o PLS-00306 não traz o SQL nem os binds (inferência).

## 7. D6: testes só com mock enquanto a parte 2 estiver bloqueada

- Os testes novos usam `_OracleFake` e `monkeypatch(oracledb.connect)`, nunca `ORACLE_SANDBOX`. Os sandbox migrados ficam em skip com gate `OPS_KILL_PKG_VERSAO`, e o skipped esperado continua 16 se a migração for no lugar. Teste sandbox **novo** muda o esperado e tem de ser declarado antes da rodada.
- Não é preciso mudar `tests/conftest.py`.
- Ajustes do fake (passo 5a):
  - `LOGON_TIME` **no fim** de `COLUNAS_ALVO`, para preservar `row[2]` = serial#;
  - `_linha_alvo(logon_time=datetime(2026,11,23,10,0,0))`;
  - `var(tipo, ...)` devolve uma var que guarda o tipo e aceita `setvalue(pos, v)`, e só a var VARCHAR devolve `status_pkg`;
  - opção para `getvalue` do status levantar exceção (T9).
- **O mock prova:** os binds, os formais, a ordem, os valores e o tipo enviados, e o tratamento de cada `p_status`.
- **O mock não prova:** a comparação no servidor, o PLS-00306 real e o NLS `BINARY_CI`. Isso fica para o ensaio 4.1 (`implantacao.md:107`).
- **Lacuna do fake:** a `description` fixa esconde a remoção de `logon_time` do SELECT DIAG. O T8 cobre isso.

## 8. D7: teste de `test_item1_intencao.py:210-212` (classe seguranca, sessão principal)

Mantém o §4.3: `ORDEM_V2`, `list(binds) == ORDEM_V2`, `re.findall(r"\b(p_\w+)\s*=>", sql) == ORDEM_V2` e `binds["p_ref_aprovacao"] == intencao["id_intervencao"]`. O comentário da v1 é trocado por uma referência ao item 6 v2. Acrescenta:
- `binds["p_ref_aprovacao"] == resultado["id_intervencao"]`;
- `binds["p_logon_time_esperado"]` com tipo `oracledb.DB_TYPE_DATE` e `getvalue() == ` o `logon_time` da linha DIAG.

Controle negativo: o teste falha em `6f564e3`, que tem 4 binds. Mutações: m1-m3 do §4.3, mais m4 (`p_ref_aprovacao=uuid.uuid4().hex`) e m5 (datetime cru, sem `var DATE`).

## 9. Testes do passo 5a (cada um falha em `6f564e3`, salvo onde se indica o controle por mutação)

| # | Teste | Prova | Controle |
|---|---|---|---|
| T1 | assinatura (`inspect`): `identidade_esperada` e `ref_aprovacao` KEYWORD_ONLY, `default is Parameter.empty`, nas duas funções | D4 | falha hoje; m6 = `ref_aprovacao=None` |
| T2 | `test_identidade_obrigatoria_param_invalido` parametrizado. Casos: identidade `None`/lista/chave faltando/chave extra; username `""`/`None`/int; program int; logon `None`/str/`date`/tz-aware/`microsecond=1`; ref `None`/bytes/31 hex/MAIÚSCULO/33/`hex+"\n"`; texto de 129 caracteres. Cada caso dá PARAM_INVALIDO, `connect` não chamado e **credenciais KILL ausentes** (resultado tem de ser PARAM_INVALIDO, não ERRO_CONFIG, o que prova a ordem antes do `getenv`). O valor-sentinela não aparece na mensagem | D1, D5 | falha hoje; m7 = validação depois do `getenv` |
| T3 | 9 binds com valores exatos: `program=None` vai como `None`; username e machine com maiúsculas e espaço final idênticos | D1 | falha hoje; m8 = `.strip()` ou `str()` |
| T4 | `logon_time` diferente na reconsulta dá ALVO_ALTERADO, `fake.conexoes_kill == []`, e RESULTADO gravado | D3 | falha hoje; m9 = tirar `logon_time` de `CAMPOS_IDENTIDADE_ALVO` |
| T5 | `p_status="ALVO_DIVERGENTE"` dá `executado False`, e-mail "NÃO executada", tela "NÃO EXECUTADA" e mensagem sem "executado para" | D5 | hoje o comportamento coincide; o controle é m10 = `ALVO_DIVERGENTE` em `RESULTADOS_KILL_EXECUTADO` |
| T6 | PLS-00306 no `execute` dá ERRO_ORACLE, `resultado_desconhecido True`, **exatamente 1** execute KILL (sem fallback) e RESULTADO gravado | D6 | m11 = retentar v1 no `except` |
| T7 | o valor de `id_intervencao`, a senha-sentinela, os valores de identidade e `BEGIN`/`=>` ausentes de `resultado_tool` (ENCERRADA, ALVO_DIVERGENTE, PARAM_INVALIDO, ERRO_ORACLE) | D5 | m12 = ecoar o ref no JSON |
| T8 | o SQL DIAG gravado em `sql_executado` contém `\blogon_time\b`; o hash muda com +1 s; o hash recalculado de `json.loads(linha INTENCAO)["alvo"]` é igual a `hash_payload`; `CAMPOS_IDENTIDADE_ESPERADA ⊂ CAMPOS_IDENTIDADE_ALVO` | D3 | falha hoje; m13 = tirar do SELECT; m14 = `isoformat()` com `T` |
| T9 | o `getvalue` do status levanta `RuntimeError` depois do execute e dá `resultado_desconhecido True` | D8 | falha hoje |
| T10 | argumentos do LLM com `ref_aprovacao`, `logon_time` e `username` extras são ignorados: binds vindos da DIAG e do `id_intervencao` | D4 | falha hoje (não há `p_ref`) |

As mutações m1-m14 têm de dar DETECTADA no passo 6.

**D8 (achado adjacente; entra porque a função é reescrita do zero).** Em `matar_sessao_oracle`, o `except Exception` passa a usar `resultado_desconhecido = execute_iniciado`, com `MENSAGEM_RESULTADO_DESCONHECIDO`. Hoje (`:823-835`), uma exceção que não é do Oracle depois do execute vira e-mail "NÃO executada", mesmo com o kill possivelmente feito. O ajuste só reduz risco e não altera expectativa existente.

## 10. Recusas e registros (v2)

| Caso | Conecta KILL? | JSONL | OPS_KILL_AUDIT | E-mail |
|---|---|---|---|---|
| PARAM_INVALIDO de inst/sid/serial ou alvo não elegível na pré-consulta (`:1729`, `:1751`) | não | nada | não | não |
| REJEITADO / SEM_IDENTIFICACAO / TIMEOUT | não | só RESULTADO | não | não |
| FALHA_LOG_APROVACAO | não | nada | não | não |
| Reconsulta falha / ALVO_ALTERADO / não elegível / APROVACAO_EXPIRADA | não | INTENCAO + RESULTADO | não | "NÃO executada" |
| PARAM_INVALIDO local (identidade/ref), ERRO_CONFIG, HostInacessivelVPN | não | INTENCAO + RESULTADO | não | "NÃO executada" |
| Erro antes do execute (connect/var) | tenta | INTENCAO + RESULTADO | não | "NÃO executada" |
| PLS-00306 (v2 × PKG v1) | sim | INTENCAO + RESULTADO ERRO_ORACLE | não; a compilação falha (doc) | "resultado desconhecido" |
| PKG v2: PARAM_INVALIDO, PROPRIA_SESSAO, ALVO_NAO_ENCONTRADO, ALVO_DIVERGENTE, NAO_USUARIO, USUARIO_PROTEGIDO | sim | INTENCAO + RESULTADO | sim, com ref (doc) | "NÃO executada" |
| ENCERRADA / MARCADA_PARA_KILL | sim | INTENCAO + RESULTADO | sim (doc) | "Aprovada" |

O `auditoria_oracle.log` recebe os argumentos do LLM e o `resultado_tool`, sem o ref (`main.py:349`, `:427`; `app.py:300`, `:538`), e as linhas `AUDITORIA HITL`, que já trazem `id_intervencao` (`:1668`). A conta KILL só executa o bloco constante, com 9 binds e sem interpolação. Ela não lê a `GV$SESSION` nem o JSONL, e o ref não é autorização (`implantacao.md:46`).

Falha fechada em todos os ramos acima. Pontos que **não** fecham:
- a micro-janela dentro do PKG (aceita);
- MARCADA_PARA_KILL contado como executado numa 2ª aprovação concorrente do mesmo alvo (CLI × Web × abas; existente, ligado ao R-F2-1);
- o PLS-00306 é relatado como "desconhecido" embora nada execute. É conservador, conforme decisão de 2026-11-17.

## 11. Ataques considerados

- **TOCTOU:** coberto pelo D2.
- **Ambiente:** a validação vem antes do `getenv`, então nenhum ramo novo lê credencial. O item não toca na carga do `.env` nem no `os.environ`. R-F2-2 (`python.envFile`) e R-F2-1 continuam abertos e não mudam.
- **Rerun e abas:**
  - o ref é gerado dentro de `registrar_decisao_kill` a cada chamada, e a pendência é limpa antes (`app.py:441`), então não há reuso de ref;
  - o rerun do Streamlit só age numa chamada `st.*`, e não há nenhuma dentro de `registrar_decisao_kill` (inferência sobre o Streamlit).
- **Interrupção:** o caminho de `BaseException` (`:1582-1616`) não muda. Agora o ref em `OPS_KILL_AUDIT` permite reconciliar um INTERROMPIDO e um "desconhecido" com o banco.

## 12. Residuais e decisões do responsável

- **PENDENTE APROVAÇÃO (existentes, não decididos aqui):**
  - texto do SQL v2, migração e rollback, depois do ensaio 4.1 (`implantacao.md` §6, pend. 1);
  - mínimo privilégio do executor (pend. 7.1).
- **Residual (existente, fora do item):** `"instancia": dsn` vai ao `resultado_tool` do LLM nos ramos ERRO_CONFIG, rede e ERRO_ORACLE (`:724`, `:740`, `:815`). O DSN não é credencial, mas é detalhe de infraestrutura. Tirá-lo seria tarefa própria, e por isso o T7 confere só usuário e senha.
- **Residual:** `hash_aprovado` e `hash_atual` no `resultado_tool` de ALVO_ALTERADO (`:959-960`), existente.
- **Operacional:** não subir a CLI nem a Web desta branch antes da parte 2 (1.11-V2:86).
