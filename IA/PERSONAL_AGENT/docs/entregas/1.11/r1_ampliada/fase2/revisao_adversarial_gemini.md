# Revisão Adversarial — Branch `r1-ampliada` (`cdc8f6d..8b05c7f`)

- **Escopo:** revisão só leitura dos commits `36746cf`, `5633e3c` (C2), `d6d6a14` (C3), `e1d4ce6` (C4), `2195b48` (C7), `64eb63f` (log fase 1), `15b677c` (plano fase 2) e `8b05c7f` (fase 2, K1 / HEAD) na branch `r1-ampliada`, sem editar código ou testes do repositório, sem ler `.env`, sem `ORACLE_SANDBOX` e sem conexão ao Oracle.
- **Base de referência:** `docs/entregas/1.11/v2_refeito/revisao_adversarial_gemini.md` §A5, `docs/plans/1.11-R1-ampliada.md` (§§1–9), `docs/entregas/1.11/r1_ampliada/decisao_c1.md` e `docs/entregas/1.11/r1_ampliada/fase2/decisao_c1.md`.
- **Estado real do `HEAD` (`8b05c7f`):** a Fase 1 da R1 ampliada (`V1–V9`) está implementada e apenas o **K1** da Fase 2 (gate `OPS_KILL_PKG_VERSAO=2`) foi commitado. Os passos **K2** (lista de permissão para a nuvem + bloqueio do RAG), **K3** (sanitização de `str(exc)` em `os_tools.py`) e **K4** (`docs/OPERACAO.md` + nota do R-d no `.env.example`) **ainda não existem no código do `HEAD`**.
- **Linhas:** todas as linhas citadas foram conferidas em `8b05c7f`.

---

## 1. Achados (do mais grave para o menos grave)

### R1-A1 — `buscar_script_interno` (RAG) segue liberado no catálogo, no despacho e na trava de histórico com Gemini em nuvem (conteúdo de scripts SQL, caminho absoluto e `str(exc)` vão à nuvem)
- **Focos:** 1 (Vazamento ao Gemini), 2 (Lista de permissão / failover de histórico)
- **Arquivo:linha:** `app.py:181, 282, 322, 423-426`; `src/main.py:200, 346, 379, 417-420`; `src/tools/oracle_dba.py:151-153, 223, 270`; `src/tools/rag_search.py:57, 81-108, 117`
- **Severidade:** alta
- **Status:** COMPROVADO
- **Cenário concreto:** Como o K2 ainda não foi aplicado em `8b05c7f`:
  1. `ferramentas_do_coordenador` (`oracle_dba.py:270`) exclui apenas `NOMES_FERRAMENTAS_ORACLE` quando `not local`, oferecendo `buscar_script_interno` diretamente ao Gemini em nuvem na Web e na CLI.
  2. O despacho (`app.py:322`, `src/main.py:379`) só bloqueia `NOMES_FERRAMENTAS_ORACLE`, executando `buscar_script_interno` com o coordenador em nuvem.
  3. `NOMES_FERRAMENTAS_SEM_DADO_DO_BANCO` (`oracle_dba.py:151-153`) inclui explicitamente `"buscar_script_interno"`: mesmo que o RAG rode com o Ollama local no Turno 1 e haja failover para o Gemini no Turno 2, `historico_tem_dado_do_banco` devolve `False` e reenvia todo o histórico com os scripts internos ao Gemini.
  4. Em `src/tools/rag_search.py`, o retorno entregue ao Gemini contém: (a) **`conteudo_sql`** — até 3.000 caracteres do arquivo `.sql` inteiro de `./MeusScripts` (sincronizado de `SCRIPT STARTUP GIT/oracle`, `rag_indexer.py:25`), podendo expor SQL proprietário, nomes de tabelas/schemas e comentários internos (`:81-108`); (b) **caminho absoluto completo do perfil Windows** (`CHROMA_DB_DIR`) quando a base vetorial não existe (`:57`); e (c) **`str(exc)` cru** em qualquer exceção (`:117`).
- **Evidência offline (cópia `git archive 8b05c7f`, sem `.env`):**
  - `P1_CAT_NUVEM: ['coletar_metricas_hardware', 'verificar_espaco_disco', 'buscar_script_interno']`
  - `P1_HIST_RAG_BLOQUEIA: False`
  - `P1_RAG_SEM_DIR_TEM_PATH: True`
  - `P1_RAG_EXC_VAZA: True`
- **Correção sugerida:** Executar o K2 conforme `fase2/decisao_c1.md` §1 (`buscar_script_interno` classificado `SO_LOCAL`, fora do catálogo da nuvem, recusado no despacho da nuvem e bloqueado na trava de histórico) e sanitizar `CHROMA_DB_DIR` / `str(exc)` em `src/tools/rag_search.py:57, 117`.

---

### R1-A2 — Ausência de lista de permissão (`CLASSIFICACAO_FERRAMENTAS`) no `HEAD` (`8b05c7f`): catálogo e despacho seguem por exclusão e nenhuma ferramenta registrada tem classificação
- **Focos:** 2 (Lista de permissão), 1 (R-e)
- **Arquivo:linha:** `src/tools/oracle_dba.py:151-153, 254-273, 2486`; `app.py:181, 282, 322`; `src/main.py:200, 346, 379`; `src/tools/os_tools.py:72-107`; `src/tools/rag_search.py:124-149`; `src/tools/gemini_router.py:119-150`; `src/tools/executor.py:550`; `src/tools/oracle_tools.py:47-77`; `tests/test_r1_saida_llm.py:399-407`
- **Severidade:** alta
- **Status:** COMPROVADO
- **Cenário concreto:** Apesar de o plano da Fase 2 (`15b677c`) especificar uma lista de permissão única com teste de cobertura de classificação, em `8b05c7f` o catálogo (`oracle_dba.py:270`) e o despacho (`app.py:322`, `src/main.py:379`) ainda operam por **lista de exclusão (`NOMES_FERRAMENTAS_ORACLE`)**. Consequências concretas:
  - **Todas as 8 ferramentas com `*_tools_schema`** (`coletar_metricas_hardware`, `verificar_espaco_disco`, `coletar_sessoes_ativas`, `coletar_top_sql`, `coletar_plano_execucao`, `matar_sessao_oracle`, `buscar_script_interno`, `analisar_log_complexo`) estão **sem classificação explícita** em registro único.
  - **Residual R-e permanece aberto:** qualquer ferramenta adicionada a `TODAS_FERRAMENTAS` / `todas_ferramentas` e ao despacho (como `executor.executar_script`, que retorna linhas de `SELECT` e `DBMS_OUTPUT` do Oracle) entra **automaticamente liberada para o Gemini** tanto no catálogo quanto na execução, antes que a trava de histórico possa agir.
  - O teste existente (`test_r1_nomes_sem_dado_do_banco_iguais_aos_schemas_de_so_e_rag`, `test_r1_saida_llm.py:399-407`) não descobre `*_tools_schema` em `src/tools/*.py` e ainda trava `buscar_script_interno` como permitido na nuvem.
  - `src/tools/oracle_tools.py:47-77` (`montar_payload_health_check`, hoje não ligada ao loop) ainda serializa `"instancia": instancia` (`payloads.py:61`) e também não possui classificação nem entrada em `ARQUIVOS_AST`.
- **Correção sugerida:** Implementar o K2 integralmente (`CLASSIFICACAO_FERRAMENTAS` em `MappingProxyType`, `ferramenta_liberada_nuvem`, `ferramentas_do_coordenador` e despacho por permissão, mais os testes AST K2-T1/T2/T3).

---

### R1-A3 — Verificação de `"local"` (`coordenador_e_local`) é contornada por proxy HTTP de ambiente (`HTTP_PROXY`/`ALL_PROXY`, `trust_env=True`) e por redirecionamento (`follow_redirects=True`) no cliente `OpenAI`/`httpx2`
- **Focos:** 3 (Verificação de "local"), 1 (Vazamento de sessões, SQL e `DBMS_XPLAN` à nuvem/rede externa)
- **Arquivo:linha:** `app.py:212-217`; `src/main.py:179-183`; `src/tools/oracle_dba.py:194-206`
- **Severidade:** alta
- **Status:** COMPROVADO
- **Cenário concreto:** `obter_cliente_llm` (`app.py:214`) e `_inicializar_cliente_coordenador` (`src/main.py:181`) instanciam `OpenAI(base_url="http://localhost:11434/v1", api_key="local")` **sem** passar um `http_client` próprio. No ambiente do projeto (`openai` + `httpx2`), o cliente criado tem **`trust_env=True`** e **`follow_redirects=True`** por padrão.
  1. **Proxy (`HTTP_PROXY` / `ALL_PROXY` / proxy do sistema Windows sem `NO_PROXY=localhost,127.0.0.1`):** quando `HTTP_PROXY` está definido no ambiente, o `httpx2` roteia tanto `http://localhost:11434/v1/chat/completions` quanto `http://127.0.0.1:11434/v1/chat/completions` para um **`<HTTPProxy>`** externo em texto claro. Como `coordenador_e_local(client)` (`oracle_dba.py:203-204`) olha exclusivamente `urlsplit(str(client.base_url)).hostname` e **não** inspeciona `trust_env` nem `_mounts` (proxies) do transporte HTTP, devolve **`True`** — liberando todas as ferramentas Oracle (`coletar_sessoes_ativas`, `coletar_top_sql`, `coletar_plano_execucao`, `matar_sessao_oracle`), cujos resultados completos (sessões, `sql_text_curto`, `DBMS_XPLAN 'TYPICAL'` com literais) saem pela rede externa via proxy! *(Na `decisao_c1.md` §7 e `fase2/decisao_c1.md` §6 isso constava apenas como inferência não verificada; aqui fica comprovado empiricamente que o vazamento acontece inclusive para `127.0.0.1`.)*
  2. **Redirecionamento HTTP (`follow_redirects=True`):** caso o serviço na porta `11434` (ou um proxy/túnel mal configurado) responda `307`/`308` para uma URL externa, o cliente `httpx2` reenvia automaticamente o `POST` inteiro (incluindo `messages` com dados do Oracle) para o destino externo mesmo com `coordenador_e_local(client) == True`.
  3. Além disso, o documento operacional do R-d (`docs/OPERACAO.md`, passo K4) ainda **não existe** em `8b05c7f`.
- **Evidência offline (cópia `git archive 8b05c7f`, sem abrir rede):**
  - `P3_LOCAL_COM_PROXY: True trust_env: True follow_redirects: True pool: HTTPProxy` (tanto para `http://localhost:11434/v1/chat/completions` quanto para `http://127.0.0.1:11434/v1/chat/completions`).
- **Correção sugerida:** No cliente local (`app.py:214` e `src/main.py:181`), instanciar `http_client=httpx.Client(trust_env=False, follow_redirects=False)` (ou `openai.DefaultHttpxClient(trust_env=False, follow_redirects=False)`), fechando no código — e não apenas em documentação operacional — o vazamento por proxy de ambiente/sistema e por redirecionamento 307/308. Em `coordenador_e_local(client)`, rejeitar clientes cujo `_client` tenha `_trust_env=True`, `follow_redirects=True` ou proxies montados em `_mounts`.

---

### R1-A4 — Sonda testa `127.0.0.1:11434`, mas o cliente usa o nome DNS `localhost:11434`; `OLLAMA_BASE_URL` do `.env.example` é ignorada; `coordenador_e_local` não valida `scheme`, `port` nem `userinfo`
- **Focos:** 3 (Verificação de "local")
- **Arquivo:linha:** `app.py:201, 214`; `src/main.py:179, 181`; `src/tools/oracle_dba.py:155, 194-206`; `.env.example:26`
- **Severidade:** média
- **Status:** COMPROVADO
- **Cenário concreto:**
  1. **Sonda vs resolução de nome:** `verificar_status_ollama` (`app.py:201`) e `_inicializar_cliente_coordenador` (`src/main.py:179`) sondam o IP literal **`127.0.0.1:11434`**, mas constroem `OpenAI(base_url="http://localhost:11434/v1", ...)` (`app.py:214`, `src/main.py:181`). `coordenador_e_local` (`oracle_dba.py:203-204`) faz apenas checagem sintática da string `"localhost"`, sem resolver o nome nem fixar IP literal. Se o arquivo `hosts` (ou DNS/NSS) remapear `localhost` para um IP remoto, ou se `localhost` resolver primeiro para `::1` onde outro processo escuta enquanto o Ollama respondeu apenas em `127.0.0.1`, a sonda passa, `coordenador_e_local` retorna `True` e o tráfego com dados Oracle vai para outro destino.
  2. **Variável de host do Ollama (`OLLAMA_BASE_URL` / `OLLAMA_HOST`):** `.env.example:26` declara `OLLAMA_BASE_URL=http://localhost:11434`, mas **nenhum `.py` lê `OLLAMA_BASE_URL` nem `OLLAMA_HOST`**, e o comentário esclarecedor previsto no K4 ainda não está no `.env.example`. Um operador que altere `OLLAMA_BASE_URL` não muda o destino real (e `OPENAI_BASE_URL` no ambiente tampouco sobrescreve o `base_url=` explícito — verificado offline).
  3. **Validação frouxa de URL em `coordenador_e_local` (`oracle_dba.py:203-204`):** aceita qualquer esquema (`ftp://localhost/v1`, `//localhost:11434/v1`), qualquer porta (`http://localhost:80/v1`, `http://localhost:9999/v1`) e credenciais embutidas (`http://user:pass@localhost:11434/v1`), pois confere apenas `urlsplit(...).hostname in {"localhost", "127.0.0.1", "::1"}`.
- **Evidência offline:** Teste direto de `coordenador_e_local` devolveu `True` para `http://localhost:80/v1`, `http://localhost:9999/v1`, `https://localhost/v1`, `ftp://localhost/v1`, `http://user:pass@localhost:11434/v1` e `//localhost:11434/v1`.
- **Correção sugerida:** Trocar o `base_url` do cliente local para `"http://127.0.0.1:11434/v1"` (casando exatamente com a sonda e eliminando resolução de nome), restringir `coordenador_e_local` a `scheme == "http"`, `hostname in {"127.0.0.1", "::1"}` (ou `"localhost"` apenas se resolvido exclusivamente para loopback), `port == 11434` e ausência de `username`/`password`, e aplicar a nota do K4 no `.env.example` / `docs/OPERACAO.md`.

---

### R1-A5 — Texto cru de exceção (`str(exc)`) em `src/tools/os_tools.py` vai ao Gemini em nuvem (K3 não implementado) e `verificar_espaco_disco` aceita caminho UNC vindo do LLM
- **Focos:** 1 (Vazamento de texto de exceção / caminho), 2 (Ferramenta liberada na nuvem)
- **Arquivo:linha:** `src/tools/os_tools.py:36, 44, 62`; `app.py:411-416`; `src/main.py:390-395`; `tests/test_r1_saida_llm.py:412`
- **Severidade:** média
- **Status:** COMPROVADO *(SMB/NTLM via UNC: INFERÊNCIA)*
- **Cenário concreto:** As duas ferramentas de `os_tools.py` permanecem liberadas para o Gemini em nuvem, mas o K3 ainda não foi commitado e `src/tools/os_tools.py` está fora de `ARQUIVOS_AST` (`test_r1_saida_llm.py:412`). Em qualquer erro de `psutil`:
  - `coletar_metricas_hardware` (`os_tools.py:36`) devolve `"mensagem": str(exc)` cru ao Gemini;
  - `verificar_espaco_disco` (`os_tools.py:62`) devolve `"mensagem": str(exc)` cru e `"unidade": drive` ao Gemini, funcionando como oráculo de caminhos do sistema operacional.
  - Adicionalmente, `drive` vem sem validação dos argumentos do LLM direto para `psutil.disk_usage(drive)` (`os_tools.py:44`): no Windows, um argumento UNC (`\\host\share\`) enviado pela nuvem (ou por prompt injection) tende a disparar conexão SMB de saída com autenticação automática NTLM do usuário do Windows *(inferência já sinalizada como PENDENTE APROVAÇÃO em `fase2/decisao_c1.md` §3.4)*.
- **Evidência offline (cópia `git archive 8b05c7f`):**
  - `P2_HW_VAZA: True` (`"hw-exc-sentinela"` no JSON de retorno);
  - `P2_DISCO_VAZA: True Z:\sentinela` (`"disk-exc-sentinela"` e caminho no JSON de retorno).
- **Correção sugerida:** Aplicar o K3 (`f"Erro {type(exc).__name__}."`, log local seguro com `%r` e inclusão de `src/tools/os_tools.py` em `ARQUIVOS_AST`) e restringir `drive` em `verificar_espaco_disco` a raiz de unidade local (`^[A-Za-z]:\\?$`).

---

### R1-A6 — Gate do kill (`OPS_KILL_PKG_VERSAO`): `executar_kill_verificado` não bloqueia antes da consulta DIAG; e `OPS_KILL_PKG_VERSAO=2` vindo do `.env` habilita o kill sem descarte/aviso
- **Focos:** 4 (Gate do kill `OPS_KILL_PKG_VERSAO`)
- **Arquivo:linha:** `src/tools/oracle_dba.py:251, 986-1010, 1261, 1896`; `app.py:73, 99`; `src/main.py:58, 84`
- **Severidade:** média
- **Status:** COMPROVADO
- **Cenário concreto:** Não foi encontrado caminho que conecte à **conta KILL** (`ORACLE_USER_KILL`) com `OPS_KILL_PKG_VERSAO != "2"` — o bloqueio em `matar_sessao_oracle:1005` impede a sonda e o `oracledb.connect` da conta KILL em todas as camadas. Contudo, há três fragilidades concretas:
  1. **`executar_kill_verificado` (`oracle_dba.py:1261`) não verifica `kill_habilitado()` antes de `consultar_alvo_sessao_diag`:** se chamado diretamente com o gate desligado (ou na janela TOCTOU entre `registrar_decisao_kill:1896` e `:2023`), ele abre sonda TCP e conexão `ORACLE_USER_DIAG` na `GV$SESSION`, violando o texto de `RESULTADO_KILL_DESABILITADO` (*"Nenhuma consulta nem conexão foi feita"*), e só é parado depois dentro de `matar_sessao_oracle:1005` (no caso TOCTOU pós-`INTENCAO`, ainda dispara e-mail SMTP em `:2174` após gravar `INTENCAO` e `RESULTADO`).
  2. **Credenciais antes do gate em `matar_sessao_oracle` (`:986-1010`):** sem `OPS_KILL_PKG_VERSAO=2`, chamar `matar_sessao_oracle` sem `ORACLE_USER_KILL`/`ORACLE_PASSWORD_KILL`/`ORACLE_DSN` devolve `ERRO_CONFIG` em vez de `KILL_DESABILITADO` (oráculo de configuração, sem conexão; decisão consciente em `fase2/decisao_c1.md` §2.2).
  3. **Habilitação persistente via `.env` ou perfil do Windows sem aviso nem checagem no banco:** diferentemente de `ORACLE_SANDBOX` (que é descartada quando vem do `.env` em `app.py:99` e `src/main.py:84`), `OPS_KILL_PKG_VERSAO=2` no `.env` habilita o kill automaticamente (`test_k1_t11`), sem aviso na subida; além disso, como a carga usa `override=False`, um `OPS_KILL_PKG_VERSAO=2` esquecido nas variáveis de ambiente do Windows sobrepõe `OPS_KILL_PKG_VERSAO=` vazio no `.env` (gerando apenas o aviso genérico de sombreadas). Nota secundária: no `.env`, o `python-dotenv` remove aspas e espaços externos (ex.: `OPS_KILL_PKG_VERSAO="2"` ou `OPS_KILL_PKG_VERSAO= 2` chegam como `"2"` em `os.environ`, ao contrário da premissa informal de `fase2/decisao_c1.md` §2.1).
- **Evidência offline (cópia `git archive 8b05c7f`):**
  - `P4_EXEC_VERIF_SEM_GATE: conexoes= ['diag_teste_fake'] conexoes_kill= [] motivo= KILL_DESABILITADO`.
  - `dotenv_values(StringIO('OPS_KILL_PKG_VERSAO="2"\n'))["OPS_KILL_PKG_VERSAO"] == "2"`.
- **Correção sugerida:** Checar `if not kill_habilitado(): return RESULTADO_KILL_DESABILITADO` no início de `executar_kill_verificado` (antes de `consultar_alvo_sessao_diag`), e avaliar exibir aviso explícito na subida (ou descartar do `.env` como `ORACLE_SANDBOX`) enquanto o PKG v2 não for a única versão nos ambientes.

---

### R1-A7 — Lacunas defensivas laterais: `historico_tem_dado_do_banco` pula não-`dict` (fail-open), `executor.py:648` fora de `try`, e artefatos legados de `analisar_log_complexo`
- **Focos:** 1 (Vazamento), 2 (Lista de permissão / histórico)
- **Arquivo:linha:** `src/tools/oracle_dba.py:219`; `src/tools/executor.py:648`; `src/tools/__init__.py:17-20, 37-38`; `src/prompts/system_prompt.txt:9`; `app.py:660, 852`
- **Severidade:** baixa
- **Status:** COMPROVADO
- **Cenário concreto:**
  1. Em `historico_tem_dado_do_banco` (`oracle_dba.py:219`), `if not isinstance(mensagem, dict) or mensagem.get("role") != "tool": continue` ignora silenciosamente qualquer item não-`dict` (necessário hoje só porque `src/main.py:356` anexa o objeto `ChatCompletionMessage` de `role="assistant"`). Se uma refatoração inserir uma mensagem `role="tool"` como objeto (não `dict`), a trava falha aberta (`False`) e deixa o dado do banco ir ao Gemini.
  2. Em `src/tools/executor.py:648`, `with open(caminho_arquivo, "rb") as f:` está fora de `try/except`: uma falha `OSError`/`PermissionError` ao ler o script homologado propaga a exceção crua contendo o caminho absoluto do arquivo para chamadores diretos (embora no loop das interfaces o `except Exception` externo a reduziria a `type(exc).__name__`).
  3. Artefatos residuais de `analisar_log_complexo`: continua exportada em `src/tools/__init__.py:17-20, 37-38` (`__all__`), `src/prompts/system_prompt.txt:9` (não carregado por `app.py`/`main.py`) ainda contém a `"REGRA DE OURO"` mandando terceirizar `DBMS_XPLAN` ao Gemini, e `app.py:660, 852` ainda exibem texto/botão mencionando envio de planos ao Gemini.
- **Correção sugerida:** Em `historico_tem_dado_do_banco`, inspecionar também `getattr(mensagem, "role", None)` e tratar objeto com `role == "tool"` (ou `role` desconhecido) de forma fail-closed (`True`); envolver `executor.py:648` em `try/except OSError` com `_registrar_erro_local`; atualizar `src/prompts/system_prompt.txt` e remover `analisar_log_complexo`/`gemini_tools_schema` de `src/tools/__init__.py`.

---

### R1-A8 — 12 mutantes relevantes sobre o código da R1 e do K1 sobrevivem integralmente aos testes (`M0`: `457 passed, 14 skipped, 0 failed`)
- **Focos:** 5 (Mutantes relevantes que sobrevivem), 1, 2, 3, 4
- **Severidade:** alta (4 mutantes altos, 6 médios, 2 baixos)
- **Status:** COMPROVADO

Todos os 12 mutantes abaixo foram executados offline em cópia isolada de `git archive 8b05c7f` (fora do repositório e fora do `%TEMP%` compartilhado) e **todos passaram com `rc=0`** contra os conjuntos completos de testes que exercitam os respectivos módulos:

| # | Mutante | Arquivo:linha (`8b05c7f`) | Sev. | Suíte executada (`rc=0`) | O que quebra e por que sobrevive |
|---|---|---|---|---|---|
| **R1_M1** | `R1_M1_WEB_DESPACHO_LIBERA_SESSOES_TOP_SQL` | `app.py:322` | **alta** | `WEB_SUITE` (`132 passed`) | Troca `nome_funcao in NOMES_FERRAMENTAS_ORACLE` por `nome_funcao in ("coletar_plano_execucao", "matar_sessao_oracle")`. Com Gemini em nuvem, chamadas inventadas a **`coletar_sessoes_ativas` e `coletar_top_sql` conectam ao Oracle e enviam sessões e SQL ao Gemini**. Sobrevive porque W2 só testa `coletar_plano_execucao` e W3 só testa `matar_sessao_oracle` (diferentemente da CLI, onde C2 parametriza as 4). |
| **R1_M2** | `R1_M2_WEB_FECHAMENTO_USA_BOOL` | `app.py:611, 614` | **alta** | `WEB_SUITE` (`132 passed`) | Em `processar_decisao_hitl`, troca `not coordenador_e_local(client)` por `not _ollama_ativo` (bool retornado por `obter_cliente_llm`). Quebra a regra §3.1 (`decisao_c1.md`) no fechamento pós-HITL: se o bool divergir do `base_url` do cliente, o histórico inteiro vai ao Gemini. Sobrevive porque W6 testa apenas `executar_agente_ui` (`:261`), nunca `processar_decisao_hitl` (`:614`). |
| **R1_M3** | `R1_M3_REG_GATE_ANTES_TTL_E_APROVADOR` | `src/tools/oracle_dba.py:1799-1965` | **alta** | `DBA_WEB` (`427 passed, 6 skipped`) | Move o bloco `if decisao == "APROVADO" and not kill_habilitado():` para **antes** das validações de `aprovador_limpo` (`:1799`) e `_aprovacao_expirada` (`:1803`). Uma aprovação expirada (TIMEOUT) ou sem aprovador com o gate desligado passa a ser gravada no `kill_approval.log` como **`"decisao": "APROVADO"`**, adulterando a auditoria. Sobrevive porque K1-T6c testa só `REJEITADO` sem gate, nunca `TIMEOUT` nem aprovador vazio sem gate. |
| **R1_M4** | `R1_M4_PRE_CONSULTA_ERRO_CONFIG_VAZA_DSN` | `src/tools/oracle_dba.py:751-754` | **alta** | `DBA_FAST` (`405 passed, 6 skipped`) | No ramo `ERRO_CONFIG` de `consultar_alvo_sessao_diag`, inclui `(DSN={dsn})` na `mensagem`. Vaza o DSN completo no `resultado_tool` tanto na pré-consulta quanto na reconsulta (V1). Sobrevive porque `test_r1_varredura_pre_consulta` (`test_r1_saida_llm.py:219`) não inclui o ramo `erro_config`, e a AST A1 só procura chaves literais `"instancia"` dentro de `json.dumps({...})`. |
| **R1_M5** | `R1_M5_EXECUTOR_DDL_VAZA_DSN` | `src/tools/executor.py:889` | **média** | `EXEC_SUITE` (`121 passed, 8 skipped`) | No ramo `DDL` (`else:` de `executar_script`), interpola `dsn` em `"saida"`. Sobrevive porque `test_r1_varredura_executor` (`test_r1_saida_llm.py:571-581`) cobre `SELECT`, `DML` e `PLSQL`, mas **omite `DDL`** (e AST A1 só checa a chave `"instancia"`). |
| **R1_M6** | `R1_M6_EXECUTOR_PATH_EXC_VAZA_DIR` | `src/tools/executor.py:628` | **média** | `EXEC_SUITE` (`121 passed, 8 skipped`) | No `except Exception as e:` da validação de caminho (`:620-631`), interpola `scripts_dir` na `mensagem`, expondo o caminho absoluto do perfil Windows. Sobrevive porque `test_r1_executor_path_invalido_sem_o_diretorio_de_scripts` (`:607`) só exercita o ramo `is_relative_to` (`:606`), nunca uma exceção em `resolve()`. |
| **R1_M7** | `R1_M7_HIST_EXCEPT_FAIL_OPEN` | `src/tools/oracle_dba.py:227` | **média** | `DBA_WEB` (`427 passed, 6 skipped`) | Em `historico_tem_dado_do_banco`, troca `except Exception: return True` por `return False` (falha aberta). Sobrevive porque os casos negativos de `test_r1_historico_tem_dado_do_banco` (`"não é lista"`, `None`) retornam em `:216` sem nunca disparar `:226`. |
| **R1_M8** | `R1_M8_HIST_SUBSTRING_RECUSA` | `src/tools/oracle_dba.py:221` | **média** | `DBA_WEB` (`427 passed, 6 skipped`) | Em `historico_tem_dado_do_banco`, troca `mensagem.get("content") == RESULTADO_ORACLE_SO_LOCAL` por `"COORDENADOR_NUVEM" in str(mensagem.get("content", ""))`. Qualquer dado real do banco (ex.: query ou programa contendo o literal `COORDENADOR_NUVEM`) é ignorado pela trava e vaza ao Gemini. Nenhum teste verifica igualdade exata contra substring no conteúdo. |
| **R1_M9** | `R1_M9_GATE_ACEITA_ASPAS` | `src/tools/oracle_dba.py:251` | **média** | `DBA_WEB` (`427 passed, 6 skipped`) | Em `kill_habilitado()`, troca `== "2"` por `.strip('"\'') == "2"`, aceitando `'"2"'` e `"'2'"` em `os.environ` — contrariando `fase2/decisao_c1.md` §2.1 (*"Valor com espaço, aspas..."*). Sobrevive porque K1-T1 (`test_oracle_kill.py:2065`) não inclui `'"2"'` nem `"'2'"`. |
| **R1_M12** | `R1_M12_LOCAL_ACEITA_SUFIXO_LOCALHOST` | `src/tools/oracle_dba.py:204` | **média** | `DBA_WEB` (`427 passed, 6 skipped`) | Em `coordenador_e_local`, troca `host in _HOSTS_COORDENADOR_LOCAL` por `host in _HOSTS_COORDENADOR_LOCAL or (isinstance(host, str) and host.endswith("localhost"))`, aceitando hosts não-loopback como `evil-localhost` / `notlocalhost`. Sobrevive porque `test_r1_coordenador_e_local_pelo_hostname_exato` (`:349-354`) só testa ataques de sufixo (`localhost.evil.com`, `127.0.0.1.nip.io`), não de prefixo. |
| **R1_M10** | `R1_M10_WEB_C3_SEM_LOG_LOCAL` | `app.py:434` | **baixa** | `WEB_SUITE` (`132 passed`) | Remove `_registrar_erro_local(nome_funcao, "erro_execucao", exc=exc)` no `except Exception` do despacho Web, apagando o detalhe do erro do log local. Sobrevive porque `test_web_c3_erro_execucao_so_com_o_tipo` (`test_fluxo_web.py:712`, ao contrário de `test_cli_c3`) não confere `caplog`. |
| **R1_M11** | `R1_M11_DIAG_SEM_LOG_LOCAL` | `src/tools/oracle_dba.py:414` | **baixa** | `DBA_FAST` (`405 passed, 6 skipped`) | Remove `_registrar_erro_local("coletar_sessoes_ativas", "OracleError", exc=db_err)` (o mesmo vale para os demais call sites de `_registrar_erro_local` em `oracle_dba.py` e `executor.py` e para `username=` nos logs de usuário protegido em `:1308` e `:2257`). Os testes de varredura só verificam que a sentinela saiu do JSON ao LLM, não que foi gravada no log local. |

*(Conferido via `git grep` em `tests/`: nenhum arquivo de teste fora das suítes executadas — `WEB_SUITE`, `EXEC_SUITE`, `DBA_FAST`, `DBA_WEB` — invoca essas funções ou caminhos; `test_carga_env_entrada.py` lê apenas `os.environ.get("OPS_KILL_PKG_VERSAO")` sem chamar `kill_habilitado()`.)*

---

## 2. Resposta direta aos 5 focos do pedido

### Foco 1 — Mapa de vazamentos para Gemini/nuvem (`8b05c7f`)

| Dado | Pode chegar ao Gemini/nuvem hoje (`8b05c7f`)? | Arquivo:linha + cenário |
|---|---|---|
| **Conteúdo de script (RAG)** | **SIM (COMPROVADO — ALTA)** | `rag_search.py:81-108`, `app.py:181, 322, 423-426`, `src/main.py:200, 379, 417-420`, `oracle_dba.py:151-153, 270`: `buscar_script_interno` é oferecido, despachado e liberado no histórico com Gemini (K2 não feito). |
| **Texto de exceção** | **SIM (COMPROVADO — MÉDIA/ALTA)** | `os_tools.py:36, 62` (`str(exc)` em hardware/disco, K3 não feito) e `rag_search.py:117` (`str(exc)` no RAG, K2 não feito) vão ao Gemini. Em `oracle_dba.py`, `executor.py`, `app.py:434` e `src/main.py:443`, `str(exc)`/`str(db_err)` foi bloqueado (exceto `executor.py:648` para chamador direto fora das interfaces). |
| **SQL (interno / banco)** | **SIM via RAG; no Oracle, só se contorno de `"local"`** | SQL de `./MeusScripts` vai direto ao Gemini via `buscar_script_interno` (`rag_search.py:98`). `sql_text_curto` de `coletar_top_sql` (`oracle_dba.py:509, 532`) fica barrado na nuvem, mas sai para fora se `HTTP_PROXY` (sem `NO_PROXY`), redirect 307/308 ou `hosts` de `localhost` contornar `coordenador_e_local` (**R1-A3**, **R1-A4**). |
| **DBMS_XPLAN** | **NÃO direto ao Gemini; SIM se contorno de `"local"`** | `coletar_plano_execucao` (`oracle_dba.py:630, 650`, `'TYPICAL'` com literais) é bloqueado quando `coordenador_e_local == False`, mas vaza no cenário de proxy/redirect/`hosts` (**R1-A3**, **R1-A4**). `analisar_log_complexo` saiu do catálogo e despacho das interfaces (V9). |
| **Dado de sessão** | **NÃO direto ao Gemini; SIM se contorno de `"local"`** | `coletar_sessoes_ativas` (`oracle_dba.py:380-408`: `username`, `program`, `machine`, `sql_id`, `event`) é bloqueado quando `coordenador_e_local == False`, mas vaza no cenário de proxy/redirect/`hosts` (**R1-A3**, **R1-A4**). |
| **Usuário (Oracle / protegido)** | **NÃO no fluxo protegido; sessões só via contorno de `"local"`** | `USUARIO_PROTEGIDO` (`oracle_dba.py:837-840`) não inclui mais o nome (V4 corrigido na origem, cobrindo pré-consulta e reconsulta). Usuários de sessões comuns em `coletar_sessoes_ativas` seguem o bloqueio V8 (sujeito a **R1-A3**/**R1-A4**). *(Usuário do Windows pode aparecer no caminho `CHROMA_DB_DIR` em `rag_search.py:57`.)* |
| **DSN** | **NÃO no fluxo ativo** | Todas as chaves `"instancia": dsn` saíram de `oracle_dba.py` e `executor.py` (V1 corrigido). *(Remanescente fora do loop do LLM: `src/tools/oracle_tools.py:69` / `payloads.py:61`.)* |
| **`host:porta` / `detalhe_rede`** | **NÃO no fluxo ativo** | Removidos de todos os 5 pontos em `oracle_dba.py` (V2 corrigido); ficam só no log local (`_registrar_erro_local`). |
| **Aprovador** | **NÃO no fluxo ativo** | Removido do `resultado_tool` em `registrar_decisao_kill:1864, 1938` (V5 corrigido); mantido apenas em JSONL, log local, tela e e-mail SMTP. |

### Foco 2 — Lista de permissão e contornos
- **Ferramentas sem classificação:** **todas as 8 ferramentas registradas** estão sem tabela de classificação (`CLASSIFICACAO_FERRAMENTAS` do K2 não existe em `8b05c7f`). Catálogo (`oracle_dba.py:270`) e despacho (`app.py:322`, `src/main.py:379`) ainda são por lista de exclusão (`NOMES_FERRAMENTAS_ORACLE`), deixando `buscar_script_interno` liberado e R-e aberto para qualquer nova ferramenta (como `executor.py`).
- **Failover / retentativa / histórico:**
  - **Failover com RAG:** contorna a trava de histórico (`oracle_dba.py:151-153, 223`) — scripts SQL coletados localmente vão ao Gemini no turno seguinte (**R1-A1**).
  - **Failover com ferramentas Oracle:** contido por `historico_tem_dado_do_banco` (`app.py:273, 614`; `src/main.py:340, 467`), com a fragilidade fail-open para elementos não-`dict` (**R1-A7**) e sem teste de `coordenador_e_local` no fechamento pós-HITL (`R1_M2`).
  - **Retentativa:** `OpenAI` (`max_retries=2`) retenta no mesmo `base_url` sem trocar de provedor; não há retentativa automática com failover dentro do mesmo `create()`.

### Foco 3 — Robustez da verificação de `"local"`
- **Não é robusta no `HEAD` (`8b05c7f`):**
  - `OpenAI(base_url="http://localhost:11434/v1")` usa `httpx2.Client` com `trust_env=True` e `follow_redirects=True`: `HTTP_PROXY` (sem `NO_PROXY`) envia até `127.0.0.1` ao proxy externo com `coordenador_e_local == True` (**R1-A3**).
  - Sonda em `127.0.0.1:11434` vs cliente em `localhost:11434` deixa dependência de resolução de nome (`hosts`/IPv6); `OLLAMA_BASE_URL` no `.env.example` é ignorada; `coordenador_e_local` não valida `scheme`, `port` nem `userinfo` (**R1-A4**).

### Foco 4 — Gate do kill (`OPS_KILL_PKG_VERSAO`)
- **Conta KILL (`ORACLE_USER_KILL`):** não foi encontrado contorno para conectar na conta KILL com `OPS_KILL_PKG_VERSAO != "2"` (bloqueado no catálogo, despacho Web/CLI, `preparar_intervencao_kill`, `registrar_decisao_kill` e `matar_sessao_oracle`).
- **Lacunas encontradas (**R1-A6**):** `executar_kill_verificado:1261` conecta na conta DIAG (`GV$SESSION`) antes de ser bloqueado em `matar_sessao_oracle:1005`; `OPS_KILL_PKG_VERSAO=2` vindo do `.env` ou do perfil Windows habilita o gate sem descarte nem aviso na subida (diferente de `ORACLE_SANDBOX`); e o gate não verifica no banco a presença do PKG v2 (confiando na rejeição `PLS-00306` como desconhecido se o banco estiver na v1).

### Foco 5 — Mutantes relevantes sobreviventes
- **12 mutantes relevantes sobreviveram** (`R1_M1`–`R1_M12`), descritos em **R1-A8** acima (4 de severidade alta, 6 média e 2 baixa).

---

## 3. Execução offline isolada e declaração de limpeza

- **Isolamento:** toda a execução de sondas e mutantes ocorreu **estritamente offline**, sem `.env`, sem `ORACLE_SANDBOX`, sem conexão ao Oracle e sem chamadas externas, em cópias extraídas via `git archive 8b05c7f` **fora do repositório/OneDrive e fora do `%TEMP%` compartilhado**, sob `<scratch do revisor>`, com `TEMP`/`TMP` apontados para `priv_tmp` privado e com `ORACLE_*`, `EMAIL_*`, `GEMINI_*`, `OPS_KILL_*`, `AGENTDBA_*`, `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, `OPENAI_BASE_URL`, `OLLAMA_BASE_URL` e `OLLAMA_HOST` removidos do ambiente do subprocesso.
- **Cópias utilizadas e removidas:**
  1. `rev_adv_r1_1b2e00f0` (sondas `P1–P4`; execução de mutação descartada por `M0` inválido porque `git archive` rodado do subdiretório não aplicou `.gitattributes` da raiz em `scripts/*.sql`, gerando `HASH_DIVERGENTE`): **apagada** (`OLD_DELETED: True`).
  2. `rev_adv_r1_4f6f1f5b` (extraída via `git archive 8b05c7f -- IA/PERSONAL_AGENT` a partir da raiz do repositório, preservando `eol=lf` nos `.sql`; `ENV_EXISTE: False`; baseline `M0_ALL_7`: `rc=0 | 457 passed, 14 skipped, 13 warnings in 98.89s`; rodadas dos 12 mutantes `R1_M1`–`R1_M12`): **apagada no bloco `finally`** (`COPIA_APAGADA: True`).
  3. Cópia anterior cancelada (`rev_adv_r1_a1d4d4e8`): também **apagada**.
- **Estado do repositório:** nenhum arquivo de código, teste ou configuração foi alterado (revisão só leitura; único arquivo criado é este relatório).

---

## 4. Limites da revisão

- **Sem Oracle, sem `.env` e sem `ORACLE_SANDBOX=1`:** os 16 testes `@pytest.mark.sandbox_only` não foram executados.
- **Sem rede externa:** o roteamento por `HTTP_PROXY` e `follow_redirects=True` foi comprovado inspecionando os atributos e `_transport_for_url` do `httpx2.Client` instanciado por `OpenAI(...)`, sem enviar tráfego HTTP real; a abertura de sessão SMB/NTLM via UNC em `verificar_espaco_disco` permanece inferência técnica sem teste em rede.
- **Escopo das rodadas de mutação:** o baseline limpo (`457 passed, 14 skipped`) e os 12 mutantes foram executados sobre os 7 arquivos de teste que cobrem R1, kill, executor, CLI, Web e ambiente em execução (`test_r1_saida_llm.py`, `test_oracle_kill.py`, `test_item1_intencao.py`, `test_fluxo_cli.py`, `test_fluxo_web.py`, `test_executor.py`, `test_env_em_execucao.py`), não sobre os ~1568 testes totais; conferido por `git grep` que nenhum outro teste referencia os símbolos mutados.
