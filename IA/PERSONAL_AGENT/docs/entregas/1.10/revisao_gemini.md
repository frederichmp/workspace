# Revisão Adversarial — Entrega 1.10

- **Escopo:** agente de encerramento de sessões Oracle via `OPS_OWNER.PKG_OPS_KILL` com aprovação humana (HITL).
- **Base:** `e2c0696`
- **Alterações analisadas:** `62a7d1a..0551ab2` (e diff em `docs/entregas/1.10/diff_revisao_gemini.diff`), mais contexto completo de produção e testes.
- **Data da revisão:** 2026-11-17

---

## 1. Algum caminho chama a conta KILL sem aprovação humana registrada?

* **[Alto]** Execução da conta `KILL` ocorre **antes** de registrar a aprovação humana — `src/tools/oracle_dba.py:1139-1165` (e mensagem invertida em `app.py:671`).
  * **Cenário:** Em `registrar_decisao_kill`, `executar_kill_verificado` (linha 1139 -> `matar_sessao_oracle` -> `ORACLE_USER_KILL`) executa **antes** de `registrar_log_aprovacao_kill` (linha 1149) e de `logger.log` (linha 1160). Se houver falha ao abrir/gravar `data/logs/kill_approval.log` (`OSError`, permissão, disco cheio) ou queda do processo após o retorno do Oracle, a sessão terá sido encerrada pela conta `KILL` (com registro em `OPS_KILL_AUDIT`), mas **sem nenhum registro de aprovação humana** em `kill_approval.log` ou `auditoria_oracle.log`. Na Web, `app.py:411` só limpa `hitl_pendente` depois, deixando o painel ativo para clique repetido em caso de exceção na escrita do log.
* **[Médio]** APIs públicas de baixo nível acionam `ORACLE_USER_KILL` sem gate HITL nem log de aprovação — `src/tools/oracle_dba.py:655`, `src/tools/oracle_dba.py:862` e reexportação em `src/tools/__init__.py:6,30`.
  * **Cenário:** `matar_sessao_oracle` (exportada em `src.tools.__all__`) e `executar_kill_verificado` chamam `ORACLE_USER_KILL` sem exigir ou registrar aprovação humana. Nos fluxos atuais de `app.py:221` e `src/main.py:237`, elas não são invocadas diretamente; o risco é de uso futuro indevido via pacote público `src.tools`.

---

## 2. Algum caminho registra `APROVADO` sem resultado de banco coerente?

* **[Médio]** `resultado_banco` recebe `"DESCONHECIDO"`, erros locais ou nomes de exceção Python sob `decisao="APROVADO"` — `src/tools/oracle_dba.py:1142-1158`, `src/tools/oracle_dba.py:746-752`, `src/tools/oracle_dba.py:779-791` e `src/tools/oracle_dba.py:636-641`.
  * **Cenário:** Na linha 1146, `resultado_banco = str(dados_exec.get("status_banco") or dados_exec.get("motivo") or "DESCONHECIDO")`:
    1. Se `p_status` vier `NULL`/vazio da procedure (linha 746), grava `decisao="APROVADO"`, `resultado_banco="DESCONHECIDO"`.
    2. Se ocorrer exceção Python genérica (ex.: `RuntimeError`, `TypeError`) ou falha local (`ERRO_CONFIG`, `HostInacessivelVPN`), grava `decisao="APROVADO"` com o nome da exceção Python/erro local no campo `resultado_banco`, sem que o banco tenha produzido status. (`executado` permanece `False`, evitando falso positivo de encerramento, mas o registro de auditoria perde coerência de domínio em `resultado_banco`.)
* **[Baixo]** `registrar_log_aprovacao_kill` não valida coerência entre `decisao`, `aprovador` e `resultado_banco` — `src/tools/oracle_dba.py:931-973`.
  * **Cenário:** Chamada direta com `decisao="APROVADO"`, `aprovador=""` e `resultado_banco=None` passa pela checagem da linha 951 e grava `APROVADO` sem resultado de banco nem aprovador.

---

## 3. O hash de identidade cobre os campos certos e é reconferido antes do kill? Há janela não coberta?

* **[Alto]** Janela TOCTOU não coberta entre a reconsulta `DIAG` e `PKG_OPS_KILL.KILL_SESSION` — `src/tools/oracle_dba.py:871-928`, `src/tools/oracle_dba.py:700-745` e `db/ops_kill.sql:54-103`.
  * **Cenário:** O hash é reconferido na aplicação via conexão `DIAG` (linhas 871-911), que é então fechada (linhas 648-652). Em seguida, `matar_sessao_oracle` ainda faz pré-check TCP (até 3 s, linha 700), abre **nova** conexão `ORACLE_USER_KILL` (linha 721) e invoca `KILL_SESSION(p_inst_id, p_sid, p_serial, p_status)` — que **não recebe** `username`, `program`, `machine` nem hash (`db/ops_kill.sql:54-59`). Há ainda micro-janela dentro da própria procedure entre o `SELECT` (`db/ops_kill.sql:78-83`) e o `EXECUTE IMMEDIATE` (`db/ops_kill.sql:100-102`). Se o alvo mudar ou `(inst_id, sid, serial#)` for reciclado para outro usuário não protegido nesse intervalo, o banco executará o kill sem detectar divergência.
* **[Médio]** Campos relevantes fora do hash de identidade — `src/tools/oracle_dba.py:43` e `src/tools/oracle_dba.py:830-859`.
  * **Cenário:** `CAMPOS_IDENTIDADE_ALVO = ("inst_id", "sid", "serial#", "username", "program", "machine")` exclui `logon_time` (ou `audsid`) e `ORACLE_DSN`. Após reinício de instância ou wrap de `serial#`, uma nova sessão de um pool de aplicação (`username`/`program`/`machine` idênticos) que receba o mesmo `(inst_id, sid, serial#)` produz **exatamente o mesmo hash SHA-256** e passa na reconferência.

---

## 4. `inst_id` tem algum default em código ou schema exposto ao LLM?

* **Sem achado em código do fluxo de kill nem no schema exposto ao LLM.**
* **Verificações feitas:**
  * Assinaturas sem default em `src/tools/oracle_dba.py`: linhas `487`, `500`, `655`, `862`, `978` e `1039`.
  * Schema OpenAI em `src/tools/oracle_dba.py:1390-1419`: `inst_id` é obrigatório (`"required": ["inst_id", "sid", "serial"]`) e sem chave `"default"`.
  * Chamadores `app.py:218,336`, `src/main.py:237` e procedure `db/ops_kill.sql:55,68-70`: sem default.
  * Fora do fluxo de kill, `src/tools/executor.py:793` tem `else "1"` apenas como fallback de metadado da sessão conectada (não exposto ao LLM nem usado em kill).
  * Observação **[Baixo]**: os prompts em `app.py:90`, `app.py:626` (botão de teste HITL) e `src/main.py:106` citam apenas `SID` e `SERIAL` sem `inst_id`, o que pode induzir o LLM a chutar `inst_id` ou cair em `PARAM_INVALIDO`.

---

## 5. A expiração (TTL) pode ser contornada, ou é aplicada no momento certo nas duas interfaces (CLI e Web)?

A verificação passiva ocorre no ponto correto nas duas interfaces: logo após o retorno de `solicitar_aprovacao` na CLI (`src/tools/oracle_dba.py:1311-1325`) e no clique do botão na Web (`app.py:349-359`). Achados:

* **[Médio]** TTL medido apenas antes de conexões sem timeout de chamada/handshake — `src/tools/oracle_dba.py:1069,1077,555,721`.
  * **Cenário:** `oracledb.connect` em `consultar_alvo_sessao_diag` e `matar_sessao_oracle` não configura `tcp_connect_timeout` nem `connection.call_timeout` (ao contrário de `src/tools/executor.py:788`). Se o aprovador confirmar em `t = 299 s` e a reconsulta `DIAG` ou o login `KILL` travar por minutos, o kill prossegue após o vencimento do TTL sem nova checagem antes de acionar `ORACLE_USER_KILL`.
* **[Baixo]** Relógio de parede (`datetime.now(timezone.utc)`) em vez de relógio monotônico — `src/tools/oracle_dba.py:1016-1033,1260`.
  * **Cenário:** Um retrocesso parcial do relógio do sistema (ex.: NTP recua 200 s quando já passaram 280 s) faz `decorrido = 80 s` (`0 <= 80 < 300`), estendendo o TTL efetivo para 500 s. Além disso, `preparado_em` não integra `hash_identidade`.
* **[Baixo]** Descarte silencioso de pendência HITL na Web — `app.py:521-525`.
  * **Cenário:** Clicar em `"🗑️ Limpar Chat"` com pendência HITL aberta (vencida ou não) zera `st.session_state.hitl_pendente` sem gravar `TIMEOUT` ou `REJEITADO` no log de aprovação.

---

## 6. Algum teste pode passar sem exercitar o que diz provar?

* **[Alto]** Teste tautológico que nunca exercita a barreira HITL — `tests/test_oracle_kill.py:167-212` (`test_aprovacao_negada_ou_sem_identificacao_sem_chamada_kill`).
  * **Cenário:** O teste afirma provar que sem aprovação ou sem identificação não há chamada à conta `KILL`, mas chama **apenas `registrar_log_aprovacao_kill`** (função pura de log em arquivo), nunca chamando `registrar_decisao_kill` ou `conduzir_kill_hitl`. Mesmo que `registrar_decisao_kill` chamasse `matar_sessao_oracle` em `REJEITADO`, este teste passaria. Ademais, a linha 173 compara com `os.getenv("ORACLE_USER_KILL")`, dependendo do `.env` externo.
* **[Alto]** Teste de não-escrita em `auditoria_oracle.log` tira o snapshot **depois** do `import main` — `tests/test_fluxo_cli.py:76-111,236-242` (`test_cli_nao_grava_auditoria_real`).
  * **Cenário:** `main_cli` (`scope="module"`) importa `main` antes de `test_cli_nao_grava_auditoria_real` capturar `antes = [_snapshot(p) for p in LOGS_REAIS]` (linha 237). Em checkout limpo sem `auditoria_oracle.log`, o `import main` cria os dois arquivos reais no disco (ver item 7.1) e o teste ainda **passa** porque `antes` já vê os arquivos criados.
* **[Médio]** `_CursorFake` não valida SQL nem binds na conta `KILL`, e testes de fluxo não conferem binds — `tests/fakes_oracle.py:51-60`, `tests/test_fluxo_cli.py:167-193`, `tests/test_fluxo_web.py:230-280` e `tests/test_oracle_kill.py:533-558`.
  * **Cenário:** Para `conta == "KILL"`, `_CursorFake.execute` aceita qualquer SQL/binds e `_CursorFake.var` sempre retorna `status_pkg`. Os testes de CLI (`test_cli_aprovado_encerrada`, `test_cli_aprovado_nao_usuario`), de TTL (`test_aprovacao_dentro_do_ttl_executa`) e `test_web_aprovado_nao_usuario` não verificam sequer que `PKG_OPS_KILL.KILL_SESSION` foi chamado; nenhum teste de CLI ou Web verifica os binds (`p_inst_id`, `p_sid`, `p_serial`, `p_status`). Se `matar_sessao_oracle` invertesse `sid`/`serial` ou executasse outro SQL na conta `KILL`, os testes passariam.
* **[Médio]** Ramos de expiração (`TIMEOUT`) em CLI e Web não têm cobertura nos smoke tests — `src/main.py:147-151`, `app.py:362-367`, `tests/test_fluxo_cli.py:167-242` e `tests/test_fluxo_web.py:218-341`.
  * **Cenário:** Nenhum dos 6 testes de CLI nem dos 6 testes de Web simula expiração de TTL; quebras nas mensagens ou no fechamento do painel Web em caso de `TIMEOUT` passariam despercebidas.
* **[Médio]** Teste `sandbox_only` desconecta a sessão alvo antes de tentar matá-la (não roda na suíte padrão) — `tests/test_oracle_kill.py:697-720`.
  * **Cenário:** Os 16 testes `sandbox_only` são pulados sem `ORACLE_SANDBOX=1` (`tests/conftest.py:68-71`). Em `test_sandbox_kill_propria_sessao_ou_usuario_protegido`, as linhas 714-715 fecham `cur.close(); conn.close()` **antes** de `matar_sessao_oracle` na linha 718; contra um banco real, a sessão `STARTUPADMIN` já terá saído da `GV$SESSION`, retornando `ALVO_NAO_ENCONTRADO` em vez de exercitar `USUARIO_PROTEGIDO`.

---

## 7. Algum arquivo de log real pode ser gravado durante a suíte?

**Sim.**

* **[Alto]** `logging.FileHandler` abre/cria os dois arquivos reais `auditoria_oracle.log` mesmo com `basicConfig` em no-op — `src/main.py:23-33`, `app.py:37-47`, `tests/test_fluxo_cli.py:99-105` e `tests/test_fluxo_web.py:117-120`.
  * **Cenário:** Em Python, a lista `handlers=[logging.FileHandler(LOG_FILE_ROOT, ...), logging.FileHandler(LOG_FILE_DATA, ...)]` é avaliada **antes** da chamada a `logging.basicConfig(...)`. Como `FileHandler.__init__` usa `delay=False` por padrão (confirmado no Python 3.15 do ambiente), ambos os handlers executam imediatamente `open(..., 'a')`. Em um checkout limpo/CI sem `auditoria_oracle.log`, rodar `test_fluxo_cli.py` ou `test_fluxo_web.py` **cria ambos os arquivos reais no disco** (0 bytes) e o `pytest_sessionfinish` (`tests/conftest.py:58-65`) vigia apenas `kill_approval.log`. Além disso, `tests/test_fluxo_cli.py:105` checa apenas handlers anexados aos loggers, não arquivos abertos/criados; e `app.py:528-530` lê o conteúdo real de `auditoria_oracle.log` durante `test_fluxo_web.py`.
* **[Alto]** Fixture `isolar_log_aprovacao` não isola `tools.oracle_dba` se o módulo for importado após o setup da fixture — `tests/conftest.py:46-55`.
  * **Cenário:** `isolar_log_aprovacao` só aplica `monkeypatch.setattr` em `tools.oracle_dba` se ele já estiver em `sys.modules` no setup (`if modulo is not None`). Se um teste rodar isoladamente (ex.: `pytest tests/test_fluxo_web.py` sem o patch manual da linha 138, ou qualquer novo teste que importe `tools.oracle_dba` / `main` / `app` no corpo do teste), `tools.oracle_dba.CAMINHO_LOG_APROVACAO_PADRAO` permanece apontando para o **arquivo real** `data/logs/kill_approval.log` e o teste gravará nele (sendo apenas detectado depois no `pytest_sessionfinish`, com o log já contaminado).

---

## 8. Há uso de `ORACLE_USER`, `ALTER SYSTEM` ou leitura de `.env` fora dos testes?

* **`ORACLE_USER` (não segregado):** **Sem achado.** Verificado por busca em `app.py`, `src/`, `db/`, `tools/`, `.env.example` e `tests/`: existem apenas `ORACLE_USER_DIAG`, `ORACLE_USER_KILL`, `ORACLE_USER_READ` e `ORACLE_USER_MUT`.
* **`ALTER SYSTEM`:** **Sem achado em Python.** Verificado por busca por `ALTER SYSTEM` e `ALTER` isolado em `app.py`, `src/` e `tools/`. A única ocorrência operacional está na procedure do banco `db/ops_kill.sql:100` (e strings concatenadas em testes negativos `sandbox_only` `tests/test_oracle_kill.py:732,751`).
* **Leitura de `.env` fora dos testes (e vazamento para a suíte):**
  * **[Médio]** Releitura destrutiva de `.env` em runtime (`override=True`) fora dos testes — `src/tools/notificador.py:17` e `src/tools/gemini_router.py:37` (além dos `load_dotenv` no import de `app.py:33`, `src/main.py:18`, `src/tools/oracle_dba.py:25`, `src/tools/executor.py:35-38` e `src/config/settings.py:6`).
    * **Cenário:** Chamar `enviar_alerta_email` ou `analisar_log_complexo` executa `load_dotenv(override=True)`, sobrescrevendo todas as variáveis do processo (`ORACLE_DSN`, `ORACLE_USER_*`, `ORACLE_SANDBOX`, overrides de container/CI ou `monkeypatch.setenv` em testes não mockados) com valores do `.env` em disco.
  * **[Médio]** Neutralização tardia de `.env` na suíte sem conexão — `tests/conftest.py:50`, `tests/test_executor.py:23`, `tests/test_privilegio_read.py:17`, `tests/test_privilegio_write_sandbox.py:16`, `tests/test_fluxo_cli.py:79-88` e `tests/test_fluxo_web.py:113-115`.
    * **Cenário:** Durante a coleta/setup do pytest, `tests/test_executor.py:23` (`override=True`) e `tests/conftest.py:50` (`import src.tools.oracle_dba` -> `src/tools/oracle_dba.py:25`) já carregaram o `.env` real em `os.environ` antes de `test_fluxo_cli.py` e `test_fluxo_web.py` neutralizarem `dotenv.load_dotenv`. Como `test_fluxo_cli.py` não sobrescreve `GEMINI_API_KEY`, `src/main.py:79-86` e `src/tools/gemini_router.py:22-24` recebem a chave real do `.env` durante o teste.

---

## 9. Mensagens de tela dizem "executado" quando o banco não encerrou a sessão?

As mensagens diretas de sistema para `REJEITADO`, `TIMEOUT`, `ALVO_ALTERADO`, `NAO_USUARIO`, `USUARIO_PROTEGIDO`, `ALVO_NAO_ENCONTRADO` e `ERRO_ORACLE` diferenciam corretamente (`"Nenhuma execução no banco"` / `"mas NÃO executada"`) em `src/main.py:145-163` e `app.py:362-385`. Achados:

* **[Médio]** Mensagem de retorno de `matar_sessao_oracle` (devolvida ao LLM para gerar o texto final na tela) sempre afirma `"executado"` — `src/tools/oracle_dba.py:756-760`, exibido via LLM em `src/main.py:193` e `app.py:420-429`.
  * **Cenário:** Quando `PKG_OPS_KILL.KILL_SESSION` recusa o alvo (`NAO_USUARIO`, `USUARIO_PROTEGIDO`, `ALVO_NAO_ENCONTRADO`, `PROPRIA_SESSAO`, `ERRO_ORACLE`), a chave `"mensagem"` do JSON retornado ao LLM diz literalmente `"Procedimento OPS_OWNER.PKG_OPS_KILL.KILL_SESSION executado para inst_id=..., sid=..., serial=.... Status retornado pelo banco: NAO_USUARIO."`. Embora `"executado": false` seja adicionado em `src/tools/oracle_dba.py:1181`, o texto `"executado"` na mensagem da tool pode induzir o modelo (especialmente `qwen2.5:7b`) a afirmar no laudo final na tela que a sessão foi encerrada.
* **[Baixo]** `MARCADA_PARA_KILL` (`ORA-00031`) é exibida como `"EXECUTADA COM SUCESSO"` / `"executada com sucesso"` — `src/tools/oracle_dba.py:40`, `src/main.py:154-158` e `app.py:374-379`.
  * **Cenário:** Em `ORA-00031` (`db/ops_kill.sql:106-107`), o Oracle apenas marcou a sessão para encerramento assíncrono (ainda viva/em rollback), mas a tela reporta `"EXECUTADA COM SUCESSO"` (com `resultado do banco: MARCADA_PARA_KILL` entre parênteses).
* **[Baixo]** Exceção dentro de `conduzir_kill_hitl` na CLI suprime `_exibir_desfecho_kill_cli` — `src/main.py:237-244,267-270`.
  * **Cenário:** Em erro de escrita de log pós-kill ou `EOFError` no `input()`, o `except Exception` devolve `{"erro_execucao": ...}` ao LLM sem imprimir nenhum aviso determinístico `[Sistema]` na tela.

---

## Escopo não verificado nesta revisão

* **Execução em banco real (`ORACLE_SANDBOX=1`):** nenhum dos 16 testes `sandbox_only`, nem os grants reais de `STARTUP_DIAG` / `STARTUP_KILL` nem a execução de `OPS_OWNER.PKG_OPS_KILL` em instância Oracle viva foram testados; a análise de `db/ops_kill.sql` foi estática.
* **Execução do `pytest`:** a suíte não foi rodada durante a revisão para manter a árvore intocada e evitar efeitos colaterais em disco (como os `FileHandler` apontados no item 7.1); o relatório de execução consultado foi `docs/entregas/1.10/pytest_v_rs_commit6.txt`.
* **Conteúdo de `.env` e dos arquivos de log reais:** não foi lido (apenas verificação de existência de `auditoria_oracle.log` e `data/logs/`).
* **Saída textual real de LLM** (`qwen2.5:7b` / Gemini) ao interpretar o campo `"mensagem"` do item 9.1.
