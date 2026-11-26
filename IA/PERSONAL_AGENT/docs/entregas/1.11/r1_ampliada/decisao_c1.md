# C1 da R1 ampliada: decisão do `seguranca`

- **Plano:** `docs/plans/1.11-R1-ampliada.md` §1, §4 (C1) e §5.2 (decisões 1a, 2a, 3, 4 e 5).
- **Base:** branch `r1-ampliada`, HEAD `36746cf`. Fontes: `passo0.md` e `passo0/sondas.txt` (30 casos).
- **Autor:** subagente `seguranca`, claude-opus-5-5. Só leitura do código. Nenhum teste rodado, sem conexão.
- **Linhas:** todas conferidas agora no `36746cf` (L9).

## 0. Resumo

1. **V1 a V7:** a regra é uma por ponto (§2) e corrige na origem.
   - Assim a correção cobre também o caminho da **reconsulta** (`oracle_dba.py:1110` e `:1149`), que repassa a `mensagem` de `consultar_alvo_sessao_diag` ao LLM. O P0 não sondou esse caminho (achado novo, §2.8).
2. **V8 (5.2.1):** a falha fechada tem **três travas**:
   - o catálogo, que não oferece as ferramentas Oracle à nuvem;
   - o despacho, que recusa com texto fixo e sem consultar;
   - o histórico, que não vai à nuvem se já tiver dado do banco.

   O sinal é o **destino do próprio `client`** (`base_url`), e não um bool nem uma nova sonda da porta 11434.
   - Sem a terceira trava, a Web vaza: o histórico da sessão (`st.session_state.llm_messages`) vai inteiro ao Gemini quando o Ollama cai entre um turno e outro, ou entre o painel HITL e o clique (`app.py:567-571`).
3. **V9 (5.2.2):** saem o schema, o ramo de despacho, a importação e a "REGRA DE OURO", nas duas interfaces. O `gemini_router.py` não muda.
4. **`os_tools_schema`:** não entra na R1 (§5).
5. **`executor.py`:** o V1 entra (5.2.3). O V3 e o caminho absoluto no PATH_INVALIDO são do mesmo tipo, mas estão fora do que foi aprovado: PENDENTE APROVAÇÃO (§6).

## 1. Peças comuns (C2, em `oracle_dba.py`)

| Peça | Regra |
|---|---|
| `_codigo_erro(exc) -> str` | Só para `oracledb.Error`: o primeiro `\b(?:ORA\|DPY\|DPI\|TNS)-\d{4,5}\b` em `_descrever_erro(exc)`. Sem casamento, ou para qualquer outra exceção: `type(exc).__name__`. Nunca levanta (A3): tudo fica em `try`, com o fallback `"Exception"`. A saída se limita ao formato do código e não ecoa texto. |
| `_registrar_erro_local(ferramenta, motivo, exc=None, rede=None)` | `logger.warning` com o texto cru: `_descrever_erro(exc)`, que nunca levanta, e `host:porta` mais `erro_rede` quando há `rede`. Fica só no `auditoria_oracle.log` (FileHandler da raiz, `app.py:120-128` e `src/main.py:106-114`). O DSN não é gravado: é configuração. |
| `NOMES_FERRAMENTAS_ORACLE` | `frozenset` com os nomes de `oracle_tools_schema` (os 4 de `:2140-2228`). |
| `RESULTADO_ORACLE_SO_LOCAL` | JSON fixo: `{"status":"recusado","motivo":"COORDENADOR_NUVEM","mensagem":"Dados do banco só com o coordenador local. Nenhuma consulta foi feita."}` |
| `coordenador_e_local(client) -> bool` | `urlsplit(str(client.base_url)).hostname` em `{"localhost","127.0.0.1","::1"}`. Atributo ausente, exceção ou outro host devolvem `False` (falha fechada). Não usa substring. |
| `historico_tem_dado_do_banco(mensagens) -> bool` | É `True` quando existe uma mensagem `dict` com `role == "tool"` e `content != RESULTADO_ORACLE_SO_LOCAL` cujo `name` **não** está na lista de permitidos `{nomes de os_tools_schema} ∪ {nomes de rag_tools_schema}`. A lista é de permitidos, então nome ausente ou desconhecido conta como dado do banco. |

## 2. V1 a V7: a regra por ponto

O LLM perde o dado, e o log local ganha o detalhe quando há valor de auditoria.

### 2.1 V1 (DSN)
- **Sai a chave `instancia` em todo ramo, sem substituto:**
  - `oracle_dba.py:179, 195, 255, 269, 281`;
  - `:316, 332, 382, 394`;
  - `:443, 459`;
  - `:838, 855, 967`.
- **O ERRO_CONFIG também vaza:** é `dsn or "NAO_CONFIGURADO"`, e vaza quando o DSN existe mas falta o usuário ou a senha.
- **Log local:** nada novo.
- **Comentário obsoleto:** o de `:987` deve ser atualizado.

### 2.2 V2 (rede)
- **Saem:**
  - `{check_rede['host']}:{check_rede['porta']}`, em `:199`, `:336`, `:463`, `:611` e `:858`;
  - a chave `detalhe_rede`, em `:202`, `:339`, `:466` e `:861`.
- **Texto substituto:** "Host do banco inacessível. Verifique se a VPN está conectada ou se há bloqueio de firewall." Na pré-consulta (`:611`), só "Host do banco inacessível."
- **Ficam** `motivo`, `tipo_erro` e `host_acessivel`.
- **Log local:** `_registrar_erro_local(..., rede=check_rede)`.

### 2.3 V3 (texto de exceção)
- **Sai `str(db_err)`/`str(exc)`:**
  - nas ferramentas de diagnóstico: `:272`, `:284`, `:395`, `:515`;
  - na pré-consulta: `:698`, `:704`;
  - no kill: `_descrever_erro` em `:957`, `:960` e `:981`.
- **Texto substituto:**
  - nova chave `"codigo_erro": _codigo_erro(exc)`;
  - `mensagem` "Erro do Oracle {codigo}." nas ferramentas de diagnóstico e na pré-consulta (que também vale para a reconsulta);
  - `mensagem` "Erro {tipo}." para exceção que não é do Oracle;
  - no kill antes do execute: `{codigo}`;
  - no kill depois do execute: `"{MENSAGEM_RESULTADO_DESCONHECIDO}. Erro do Oracle a partir da chamada de encerramento: {codigo}"`.
- **O D8 (`:979`) já está correto.**
- **Log local:** `_registrar_erro_local(..., exc=...)` **antes** do `return`.
- **Interfaces:** `app.py:394-396` e `src/main.py:418-420` passam a `{"erro_execucao": type(exc).__name__}`, com `logging.error` do nome da ferramenta e de `_descrever_erro(exc)`.

### 2.4 V4 (usuário protegido)
- **Sai** `({username or 'NULO'})` de `:683-686`.
- **Texto substituto:** "Sessão inst_id=…, sid=…, serial=… pertence a usuário protegido. Encerramento não permitido."
- **O `motivo`** continua `USUARIO_PROTEGIDO`.
- **Log local:** o `logger.warning` da pré-consulta (`:2001-2004`) e o da reconsulta (`:1140-1142`) passam a levar `username=`.
- **Corrigir na origem** cobre a pré-consulta (`:2015`) e a reconsulta (`:1149`).

### 2.5 V5 (aprovador)
- **Sai** `por '{aprovador_registro}'` de `:1697`.
- **Texto substituto:** "Intervenção não aprovada ({decisao}/{motivo}). Nenhuma chamada à conta KILL foi feita."
- **O aprovador continua** no JSONL (`:1650-1662`), no log (`:1684-1687`) e na tela (`app.py:499-503`), que não vai ao LLM.

### 2.6 V6 (nome do PKG)
- **Nenhum texto que vai ao LLM tem `OPS_OWNER`, `PKG_OPS_KILL` nem `KILL_SESSION`.** Isso inclui a forma curta.
- **Onde muda:**
  - `:921`: "Encerramento executado para inst_id=…, sid=…, serial=…. Status retornado pelo banco: {status}.";
  - `MENSAGEM_RECUSA_PKG` (`:56`): "recusado pelo procedimento de encerramento";
  - `MENSAGEM_ALVO_DIVERGENTE` (`:104`): "(verificação do procedimento de encerramento)";
  - `:934`: "Status retornado pelo procedimento de encerramento";
  - a descrição da ferramenta (`:2202-2203`): "através do procedimento homologado de encerramento".
- **Fica como está:** o SQL do execute (`:891`) e o painel HITL (`app.py:824`), que é tela e não vai ao LLM.

### 2.7 V7 (hashes)
- **Saem** as chaves `hash_aprovado` e `hash_atual` de `:1128-1129`, sem substituto. O `motivo` ALVO_ALTERADO basta.
- **Ficam** no `logger.warning` (`:1118-1121`) e no `hash_payload` do JSONL.
- **Motivo:** o hash cobre campos de identidade de baixa entropia e dá para confirmar um palpite offline.

### 2.8 Achado novo (fato)
- **A reconsulta repassa o texto da pré-consulta:** `executar_kill_verificado` copia `reconsulta['mensagem']` para o `resultado_tool` em `:1110` (falha) e `:1149` (não elegível). Isso leva o V2, o V3 e o V4 pelo fluxo aprovado.
- **A correção na origem (§2.2-2.4) cobre esse caminho.** O teste precisa de casos próprios (§8.1).

### 2.9 Fica no texto ao LLM (decidido; não é vazamento)
- **Eco de parâmetro que o próprio LLM mandou:** PARAM_INVALIDO (`:584`, `:802`, `:1989`) e SQL_ID_INVALIDO (`:427`).
- **Códigos** de status e motivo.
- **`OPS_KILL_AUDIT` como instrução ao humano.** É residual R-b (§11).

## 3. V8: a forma da falha fechada (5.2.1)

### 3.1 Sinal
- **O que é:** `coordenador_e_local(client)`, calculado sobre **o mesmo objeto** passado a `chat.completions.create`.
- **Não serve o bool `ollama_ativo`** (`app.py:207/216`) nem uma nova sonda.
- **Por quê:**
  - o destino é fixado pelo `base_url` do objeto (`app.py:205`, `:212`; `src/main.py:171`, `:178`), então não há janela entre a checagem e o envio;
  - uma refatoração que separe o bool do cliente não abre vazamento.

### 3.2 Catálogo
- **Local:** `os_tools_schema + oracle_tools_schema + rag_tools_schema`.
- **Nuvem:** `os_tools_schema + rag_tools_schema`.
- **Interfaces:**
  - Web: escolhe com o `client` de `app.py:250` e usa no `tools=` de `:265`;
  - CLI: escolhe com o `client` do módulo (`src/main.py:185`) e usa em `:323`.

### 3.3 Despacho
- **Regra:** com `not local` e `nome_funcao in NOMES_FERRAMENTAS_ORACLE`, o resultado é `RESULTADO_ORACLE_SO_LOCAL`, sem chamar a função. Ficam de fora `getenv`, a sonda TCP, `oracledb.connect`, o `preparar_intervencao_kill` e o painel HITL.
- **Posição na Web:** logo depois do parse dos argumentos (`app.py:289-293`) e **antes** do ramo HITL (`:306`).
- **Posição na CLI:** antes do `if` de `src/main.py:356`.
- **Por que é necessário:** o LLM pode chamar uma ferramenta que não foi oferecida, e o despacho de hoje não confere o catálogo.

### 3.4 Histórico
- **Regra:** antes de **todo** `create` com `not local` (Web `:262` e `:568`; CLI `:320` e `:442`), se `historico_tem_dado_do_banco(mensagens)`, a chamada não é feita.
- **Web:**
  - aparece um texto fixo na tela: "O histórico desta conversa tem dados do banco e o coordenador ativo é em nuvem. Use 'Limpar Chat' (`app.py:701-705`) ou religue o Ollama.";
  - o loop termina;
  - em `processar_decisao_hitl`, o fechamento é pulado **depois** de o desfecho já estar gravado e o `aviso_ui` já exibido (`:539-564`), e a função devolve `True`.
- **CLI:** a mesma checagem. Hoje ela nunca dispara, porque `messages` é por chamada (`src/main.py:309`) e o cliente é por processo.
- **A paráfrase do LLM local também é contida:** a resposta do assistente (`app.py:272`) vem sempre depois de uma mensagem de ferramenta, e por isso fica bloqueada junto.

### 3.5 O kill entra na trava
- **A decisão diz "as ferramentas Oracle", e o `oracle_tools_schema` tem 4 ferramentas.** Fica na leitura literal.
- **Motivo:** mesmo depois do C2, a pré-consulta é um oráculo de existência de sessões para a nuvem (ALVO_NAO_ENCONTRADO × NAO_USUARIO × USUARIO_PROTEGIDO × painel).
- **Não vale para a execução de um HITL já pendente:** `processar_decisao_hitl` não consulta o LLM antes do kill.
- **Exceção:** deixar o kill disponível com a nuvem exige uma decisão explícita do responsável. Não é pedida.

## 4. V9: `analisar_log_complexo` e a "REGRA DE OURO" (5.2.2)

Nas duas interfaces saem:
- a importação de `tools.gemini_router` (`app.py:159-162`; `src/main.py:152-155`);
- o `gemini_tools_schema` do catálogo (`app.py:170`; `src/main.py:189`);
- o ramo de despacho (`app.py:377-384`; `src/main.py:383-390`);
- as menções em condição de auditoria (`app.py:298`, `:402`; `src/main.py:347`, `:425`);
- a linha "REGRA DE OURO" (`app.py:181`; `src/main.py:201`), sem substituto.

Detalhes:
- **Chamada inventada:** se o LLM ainda chamar `analisar_log_complexo`, ela cai no ramo "desconhecida" (`app.py:389-393`; `src/main.py:398-402`).
- **`gemini_router.py` não muda:** a função continua para o uso explícito futuro, e `tests/test_env_em_execucao.py:225` a chama direto.
- **Textos de tela, opcionais e fora do critério:** `app.py:611` ("escalar … para o Gemini") e `:803` ("(Gemini)").

## 5. `os_tools_schema`: não entra

- **O que devolve:** só números de CPU, RAM e disco, mais o eco do `drive` que veio do LLM (`src/tools/os_tools.py:15-64`). Não tem dado do banco nem metadado da classe V1-V7. Fica nos dois catálogos.
- **Residual R-c:** `verificar_espaco_disco` aceita qualquer caminho, o que funciona como oráculo de existência no disco local, e `str(exc)` (`:62`) ecoa esse caminho.

## 6. `executor.py` (C3)

- **Aprovado (V1):** sai a chave `instancia` de `executor.py:810, 848, 867, 886, 908, 927`, sem substituto.
- **PENDENTE APROVAÇÃO (fora do 5.2.3, que é só o V1).** São do mesmo tipo:
  - V3 em `:909` (`str(db_err)`) e `:928` (`str(exc)`): passaria a `_codigo_erro`;
  - o caminho absoluto `scripts_dir` em `:612-613` e `str(e)` em `:625` (PATH_INVALIDO): mostra o perfil do Windows;
  - `str(e)` do LOB em `:62`.
- **Recomendação:** incluir. O custo é baixo, e o `tests/test_executor.py:378` (`"ORA-20001" in mensagem`) continua passando com o código.

## 7. Ataque à proposta

| Vetor | Resultado |
|---|---|
| TOCTOU sonda × cliente | Eliminado: o sinal é o `base_url` do objeto que envia (§3.1). |
| Ollama cai entre turnos ou entre o HITL e o clique | Coberto pela trava de histórico (§3.4). Sem ela, vaza (fato: `app.py:567-571` usa um cliente novo com o histórico inteiro). |
| `GEMINI_API_KEY` ausente | Não protege: `app.py:209` usa `"local"`, e o corpo da requisição chega ao endpoint do Google do mesmo jeito (inferência sobre o HTTP: a rejeição da chave vem depois de o corpo ser recebido). |
| Abas e CLI × Web | O sinal não depende de `os.environ`. O histórico é por sessão (`st.session_state`), e a CLI usa `messages` por chamada. |
| Rerun do Streamlit (L8) | Só há `create` em `app.py:262` e `:568`. A barra lateral (`:657`) cria o cliente sem chamada. |
| Exceção no meio | `_codigo_erro` e `_registrar_erro_local` nunca levantam. Se o log falhar, `logging` não propaga a falha do handler (inferência sobre a stdlib: `Handler.handleError`). O registro do kill vem antes do fechamento. |
| Resultado desconhecido | Mantém `MENSAGEM_RESULTADO_DESCONHECIDO` e `resultado_desconhecido` (`:955-958`). Só o texto cru sai. |
| Porta 11434 encaminhada para fora (`ssh -L`) | Fora do alcance do código. Residual R-d. |
| `HTTP_PROXY` sem `NO_PROXY` para localhost | Não verificado se o httpx manda localhost ao proxy. Residual R-d. |

## 8. Testes (C5, pela sessão principal; 5.2.4)

### 8.1 Varredura (arquivo novo, por exemplo `tests/test_r1_saida_llm.py`)

**Sentinelas:**
- `host-sentinela-r1`, `1599`, `SVC_SENTINELA`;
- `rede-sentinela`, como `erro_rede`;
- `texto-sentinela`, em `oracledb.DatabaseError("ORA-99999 texto-sentinela")`;
- `exc-sentinela`, em `RuntimeError`;
- `STARTUPADMIN`;
- `aprovador-sentinela`;
- `PKG_OPS_KILL`, `OPS_OWNER`, `KILL_SESSION`;
- a regex `[0-9a-f]{64}`;
- as chaves `"instancia"` e `"detalhe_rede"`.

**Asserções positivas por caso** (para o teste não passar no vazio):
- o `motivo` ou `status` esperado;
- `"ORA-99999"` **presente** no ramo do Oracle;
- o fake de conexão chamado ou não chamado, conforme o ramo.

**Matriz de casos:**
- os 30 de `sondas.txt`;
- novos no fluxo HITL aprovado: reconsulta com rede, com ERRO_ORACLE, com exceção e com protegido;
- novos no kill: ERRO_ORACLE antes do execute e exceção antes do execute;
- novos no executor: sucesso SELECT, PLSQL, DML e DDL, mais ERRO_ORACLE e exceção (só a chave do V1 enquanto o §6 estiver pendente).

**Controle negativo:** em `cdc8f6d`, 29 dos 30 casos de `sondas.txt` já trazem sentinela (o D8 é o único limpo), e os novos também falham.

### 8.2 T7 (`tests/test_oracle_kill.py:1054-1108`)
- **Passam de `:1074` para a lista base (`:1102-1105`), em todo ramo (§8.8 do item 6):** `"host-teste:1521/TESTE"`, `"host-teste"` e `"instancia"`.
- **Também entram na lista base:** `"PKG_OPS_KILL"`, `"OPS_OWNER"`, o aprovador usado por `_fluxo_aprovado` e a regex de 64 hexadecimais.
- **No caso `erro_oracle` (`:1064-1067`):**
  - `"erro interno"` entra nos proibidos;
  - uma asserção positiva confere `"ORA-00600" in tool`.
- **Casos novos:** `alvo_alterado` e `reconsulta_rede`.
- **Controle negativo:** o `encerrada` falha em `:921`, e o `erro_oracle` falha em `:957`.

### 8.3 Interfaces (coordenador fake que registra `messages` e `tools`)

**Web** (`AppTest`):
- **W1, nuvem:** com o Ollama fora, `tools` não tem nenhum nome Oracle nem `analisar_log_complexo`.
- **W2, nuvem:** uma chamada inventada a `coletar_sessoes_ativas` devolve `RESULTADO_ORACLE_SO_LOCAL`. Também confere:
  - `oracledb.connect` não chamado;
  - nenhuma sonda;
  - `destinos_inesperados == []`.
- **W3, nuvem:** uma chamada inventada a `matar_sessao_oracle` não gera prep, DIAG nem `hitl_pendente`.
- **W4, histórico:**
  - no turno 1, local, `coletar_sessoes_ativas` devolve uma sentinela;
  - no turno 2, nuvem, o `create` não é chamado e o texto fixo aparece na tela.
- **W5, troca entre o HITL e o clique:**
  - o Ollama está ativo no painel e cai antes do clique;
  - o JSONL fica com INTENCAO e RESULTADO;
  - o `create` de fechamento não é chamado.
- **W6, sinal:** `obter_cliente_llm` falso devolve um cliente com `base_url` do Gemini e `ollama_ativo=True`, e o caso recusa. Mata o mutante que usa o bool.

**CLI:**
- **C1, nuvem:** `client` falso com `base_url` do Gemini; `tools` sem Oracle.
- **C2, nuvem:** uma chamada inventada a uma ferramenta Oracle devolve a recusa, sem `connect`.
- **C3:** `erro_execucao` só com o nome do tipo (com o `exc-sentinela`). Vale para as duas interfaces.

**Unitário de `coordenador_e_local`:**
- `True` para `http://localhost:11434/v1` e para `http://127.0.0.1:11434/v1`;
- `False` para o URL do Gemini, `http://localhost.evil.com/v1`, `http://127.0.0.1.nip.io/v1`, objeto sem `base_url` e `base_url` que levanta.

**Prompt:** os dois `SYSTEM_PROMPT` não têm `analisar_log_complexo` nem `REGRA DE OURO`.

### 8.4 AST
Arquivos: `oracle_dba.py`, `app.py` e `src/main.py`; em `executor.py`, só a regra A1.
- **A1:** nenhum `json.dumps` com `Dict` literal tem as chaves `instancia`, `hash_aprovado`, `hash_atual` ou `detalhe_rede`.
- **A2:** dentro de um `except ... as X`, o nome `X` só aparece:
  - em `type(X)`, `getattr(X, ...)` ou `isinstance`;
  - como argumento de `_codigo_erro` ou `_registrar_erro_local`;
  - dentro de uma chamada `logger.*`/`logging.*`.
- **A3:** `_descrever_erro` só é chamado dentro de `_codigo_erro`, de `_registrar_erro_local` ou de uma chamada de log.
- **A4:** `app.py` e `src/main.py` não importam `tools.gemini_router` e não têm a constante `"analisar_log_complexo"`.

### 8.5 Expectativas alteradas (declarar no commit e no GOVERNANCA_LOG)
- **`tests/test_oracle_kill.py:1296`:** o literal "Status retornado pelo PKG_OPS_KILL" muda por causa do V6.
- **`tests/test_fluxo_web.py:166-173`:**
  - o Ollama deixa de estar fora: a porta 11434 devolve um gerenciador de contexto falso, sem socket real;
  - em `:206-208`, o `_OpenAIFalso` guarda `base_url`;
  - motivo: com a decisão 5.2.1, o kill com a nuvem é recusado. O caso de nuvem ganha W1-W6.
- **`tests/test_fluxo_cli.py:33-50`:** o `_LLMFalso` ganha `base_url="http://localhost:11434/v1"`.
- **Outras que a suíte apontar:** declarar uma a uma. Nenhuma asserção fica mais fraca.

## 9. Mutantes (C6): um por ponto, todos com detector

| Mutante | Detector |
|---|---|
| V1: `"instancia": dsn` volta no sucesso de sessões; no executor, no SELECT | varredura e A1 |
| V2: `host:porta` volta em `:611`; `detalhe_rede` volta em `:861` | varredura (`preparar:rede`, `matar:rede`) e A1 |
| V3: `str(db_err)` volta em `:698`; `_codigo_erro` devolve `str(exc)`; interface com `str(exc)` | varredura (reconsulta e prep), C3, A2 |
| V4: o `username` volta em `:685` | varredura (`preparar:protegido`, reconsulta protegido) |
| V5: o aprovador volta em `:1697` | varredura (`registrar:rejeitado`) |
| V6: o nome do PKG volta em `:921`; volta em `:2203` | T7 `encerrada` e varredura do schema |
| V7: a chave `hash_atual` volta | T7 `alvo_alterado` e A1 |
| V8a: o catálogo da nuvem inclui o Oracle | W1, C1 |
| V8b: o despacho sem a checagem | W2, W3, C2 |
| V8c: sem a trava de histórico | W4, W5 |
| V8d: o sinal vem do bool ou de uma nova sonda | W6 |
| V8e: o sinal usa a substring `"localhost" in url` | unitário (`localhost.evil.com`) |
| V9a: `gemini_tools_schema` volta ao catálogo; V9b: o ramo de despacho volta; V9c: a "REGRA DE OURO" volta | W1 e A4; A4; prompt |

## 10. Fato e inferência

**Fato:**
- tudo com `arquivo:linha` acima, lido agora;
- a reprodução do P0 (`sondas.txt`).

**Inferência, não verificada:**
- o comportamento do endpoint do Google com chave inválida (§7);
- o httpx com proxy e localhost;
- o `Handler.handleError`;
- o formato dos códigos de erro `DPY` e `TNS` no driver real;
- que só os testes listados em §8.5 quebram.

**Sem fato de banco:** o banco não foi consultado.

## 11. Residuais e decisões do responsável

- **PENDENTE APROVAÇÃO:** o §6 (V3 e caminho no `executor.py`, fora do 5.2.3).
- **PENDENTE APROVAÇÃO (fora do escopo; decidir se abre tarefa):** R-a. Com a nuvem, `buscar_script_interno` manda o conteúdo dos scripts internos (`src/tools/rag_search.py:96-98`) e `str(exc)` (`:117`).
- **R-b, residual aceito por esta decisão:** `OPS_KILL_AUDIT` aparece no texto ao LLM como instrução ao humano (`oracle_dba.py:105, 935, 1805, 1862`; `app.py:473`; `src/main.py:413`).
- **R-c:** o oráculo de caminho em `verificar_espaco_disco` (§5).
- **R-d:** "local" quer dizer o endpoint localhost; um encaminhamento de porta ou um proxy ficam fora do código.
- **Sem mudança:** `db/ops_kill.sql`, `registry/`, a lista de protegidos e os privilégios.
