# C7 da R1 ampliada: conferência do diff pelo `seguranca`

- **Plano:** `docs/plans/1.11-R1-ampliada.md` §4 (C7) e §5.2. **Decisão de referência:** `r1_ampliada/decisao_c1.md`.
- **Diff:** `36746cf..e1d4ce6` (C2 `5633e3c`, C3 `d6d6a14`, C4 `e1d4ce6`), 8 arquivos, +1230/−137.
- **Autor:** subagente `seguranca`, claude-opus-5-5. Só leitura: sem pytest e sem conexão. As linhas `arquivo:linha` foram conferidas agora no `e1d4ce6` (L9).
- **Veredito:** **CONFORME**, com 3 observações não bloqueantes (§6) e 1 registro pendente do responsável (§7).

## 1. V1 a V7 (`oracle_dba.py`) contra a decisão §2

| Ponto | Decisão | No diff (fato) | Veredito |
|---|---|---|---|
| V1 | a chave `instancia` sai de todo ramo | As 14 ocorrências saíram, inclusive o ERRO_CONFIG `dsn or "NAO_CONFIGURADO"`. O comentário obsoleto do D8 foi atualizado (`:1097`). Pelo grep do diff, `"instancia"` só aparece em comentário e nas listas de teste. | CONFORME |
| V2 | sem `host:porta` e sem `detalhe_rede`, com texto fixo e log local | Usa `TEXTO_HOST_INACESSIVEL_VPN` e `TEXTO_HOST_INACESSIVEL` (pré-consulta, `:742` no diff), e `_registrar_erro_local(..., rede=check_rede)` em todos os 5 pontos. Ficam `motivo`, `tipo_erro` e `host_acessivel`. | CONFORME |
| V2, desvio declarado | `erro_rede` passa a ser só tipo e errno (`:268`) | Fica mais restritivo que a decisão §1, que gravava o texto cru no log. O host e a porta continuam no log (`:188`). O motivo é o A2, porque `str(net_err)` reprovaria. Detector: `M_R1_V2_ERRO_REDE_COM_TEXTO`. O que se perde é o texto do socket no log local. | ACEITO |
| V3 | o LLM recebe `codigo_erro` mais o texto "Erro do Oracle {c}." ou "Erro {tipo}.", e o texto cru vai ao log antes do `return` | `_codigo_erro` (`:158`) devolve o 1º `ORA/DPY/DPI/TNS-NNNN(N)` ou o tipo, e o `try` tem fallback `"Exception"`. O `_registrar_erro_local` (`:173`) nunca levanta. Na pré-consulta e na reconsulta a mudança é na origem (`consultar_alvo_sessao_diag`). O kill antes do execute devolve `{codigo}`. Depois do execute, `MENSAGEM_RESULTADO_DESCONHECIDO` mais o código, e `resultado_desconhecido` fica preservado. | CONFORME |
| V4 | recusa genérica, com o username no log | Mensagem sem o nome (`:793`). O `username=` entra no log da reconsulta (`:1251`) e no da pré-consulta (`:2115`). | CONFORME |
| V5 | sem o aprovador | `:1808`. O aprovador continua no JSONL, no log e na tela. | CONFORME |
| V6 | nenhum `OPS_OWNER`, `PKG_OPS_KILL` nem `KILL_SESSION` no texto ao LLM | Mudaram `MENSAGEM_RECUSA_PKG` (`:57`), `MENSAGEM_ALVO_DIVERGENTE`, `:1028`, o desconhecido e a descrição do schema (`:2314`). O SQL do execute e o painel (`app.py:538`) não mudaram, como decidido. | CONFORME (obs. 6.1) |
| V7 | `hash_aprovado` e `hash_atual` saem | Saíram do ALVO_ALTERADO e continuam no `logger.warning` e no JSONL. | CONFORME |
| §2.8 | a reconsulta é coberta pela origem | `executar_kill_verificado` repassa a `mensagem` já limpa. Há casos próprios de rede, ERRO_ORACLE e exceção pelo fluxo aprovado. | CONFORME |

**Desvio declarado: reconsulta protegida por chamada direta.** A ordem em `executar_kill_verificado` é `encontrado` (`:1206`), depois hash (`:1226-1227`), depois `elegivel` (`:1247`). O `username` entra no hash (`CAMPOS_IDENTIDADE_ALVO`, `:98`). Pelo fluxo, o ramo protegido da reconsulta só seria alcançado com um hash aprovado de identidade protegida, e a pré-consulta recusa esse caso antes da aprovação. A chamada direta com `calcular_hash_identidade(alvo protegido)` alcança o ramo `:1247`. **ACEITO.**

## 2. `executor.py` (C3): V1 mais a decisão 1a (V3 e caminho)

- **V1:** as 6 chaves `instancia` saíram. CONFORME.
- **V3:** ERRO_ORACLE e exceção levam `codigo_erro` mais o código na mensagem (`:908-909`, `:928-929`), e o registro local vem antes do rollback. O LOB fica só com o tipo (`:64`). CONFORME.
- **Caminho:** sem `scripts_dir` (`:615`). No PATH_INVALIDO de exceção, a mensagem leva só o tipo e o detalhe vai ao log local. Fica o `registro.arquivo` (relativo, do `registry/`), que não mostra o perfil do Windows. CONFORME.
- **Desvio declarado: `sha256_verificado` fora da varredura.** O teste remove só o valor exato devolvido, e qualquer outro hash de 64 hexadecimais reprova. É o hash do arquivo homologado (o mesmo do `registry/` versionado), e não hash de identidade de baixa entropia (a classe do V7). **ACEITO.**
- **Import `from src.tools.oracle_dba import ...` (`:25`):** é coerente com o `src.tools.registry` já usado. Sob `tools.*`, a app ganharia uma 2ª instância do módulo, com um `_LOCK_LOG_APROVACAO` próprio. O executor só usa funções sem estado, então não há efeito hoje (inferência, ver §6.3).

## 3. V8 e V9 nas interfaces (C4) contra a decisão §3 e §4

**Sinal (§3.1).** `local = coordenador_e_local(client)` é calculado sobre o mesmo objeto que envia: Web `app.py:257` e `:588`, CLI `src/main.py:320`. A função compara o `hostname` exato de `urlsplit` com `{localhost, 127.0.0.1, ::1}`. Atributo ausente ou exceção dão `False`. Não há TOCTOU entre a checagem e o envio. CONFORME.

**Catálogo (§3.2).** Web `app.py:278`; CLI `src/main.py:335`. Com a nuvem, só SO e RAG. `gemini_tools_schema` saiu dos dois catálogos. CONFORME.

**Despacho (§3.3).**
- Web `app.py:318`: depois do parse e do log de intenção, e **antes** do ramo HITL. Acrescenta a `RESULTADO_ORACLE_SO_LOCAL` e dá `continue`, sem sonda, sem DIAG e sem painel.
- CLI `src/main.py:368`: é o 1º ramo do `if/elif`, antes de `conduzir_kill_hitl`.
- `NOMES_FERRAMENTAS_ORACLE` (`:2344`) é derivado do schema e inclui o kill (§3.5).

CONFORME.

**Histórico (§3.4).** A checagem vem antes de **todo** `create` com a nuvem. Os `create` atuais são `app.py:275` e `:591`, e `src/main.py:332` e `:452`. As travas estão em `app.py:269` e `:588`, e em `src/main.py:329` e `:449`.
- A lista é de permitidos (`NOMES_FERRAMENTAS_SEM_DADO_DO_BANCO`): nome ausente ou desconhecido, entrada que não é lista e exceção dão `True`.
- No fechamento pós-HITL, a trava vem depois de o JSONL ter sido gravado, da mensagem de ferramenta acrescentada (`app.py:560`) e do `aviso_ui`, e a função devolve `True`.
- A constante fixa no lugar da união dos schemas é uma variação de forma, com um teste de igualdade com os dois schemas.

CONFORME.

**V9 (§4).** O catálogo, o despacho, as condições de auditoria (Web e CLI) e a "REGRA DE OURO" saíram dos dois prompts. **A importação fica** (`app.py:168`, `src/main.py:161`) pela opção (a) do responsável. O motivo foi conferido: `tests/test_carga_env_entrada.py:257-258` lê `sys.modules["tools.gemini_router"].GEMINI_API_KEY`, então o import é a sonda do test_d63. Nenhum nome do `gemini_router` é usado. CONFORME, com a A4 ajustada.

**V3 nas interfaces.** `{"erro_execucao": type(exc).__name__}` mais `_registrar_erro_local` (`app.py:415-417`, `src/main.py:425-427`). O ramo do kill na CLI já logava só o tipo. CONFORME.

## 4. Falha fechada (§3 da decisão)

| Ponto | Comportamento | Fecha? |
|---|---|---|
| `coordenador_e_local` sem `base_url` ou com exceção | `False`, tratado como nuvem | sim |
| `historico_tem_dado_do_banco`: exceção, não lista, nome ausente ou desconhecido | `True`, e a chamada não é feita | sim |
| `_codigo_erro` com `__str__` que levanta | o nome do tipo (há teste) | sim |
| `_registrar_erro_local` com falha | `pass`: o retorno ao LLM continua limpo, mas o detalhe local se perde | sim para o LLM; o detalhe some em silêncio (residual aceito na decisão §7) |
| Tool call inventada com a nuvem | recusa fixa, sem consulta | sim |
| Ollama cai entre turnos ou entre o painel e o clique | o `create` não é feito, e o texto fixo vai para a tela | sim |
| Kill de um HITL já pendente com a nuvem | o kill roda (é decisão humana) e o fechamento não vai à nuvem | conforme a §3.5 |
| Futuro: `executor.py` ligado ao LLM com a nuvem | a trava de histórico bloqueia o envio seguinte, mas o despacho executaria o script | **não**: residual R-e (§7) |

## 5. Testes, AST e greps

**Varredura (`tests/test_r1_saida_llm.py`).**
- Cobre os 30 casos do `passo0/sondas.txt`: diag 15; `matar` d8, encerrada, erro_config, erro_oracle_antes e depois, e rede; `preparar` 4; `fluxo` 3 mais `rejeitado`; e o schema.
- Novos: reconsulta (rede, ERRO_ORACLE, exceção, protegido), `excecao_antes`, `recusa_pkg`, `desconhecido` e o executor (5 ramos mais PATH_INVALIDO).
- Tem asserção positiva de `motivo` ou `status` e `ORA-99999` presente nos ramos Oracle.

**Peças.** O unitário de `coordenador_e_local` tem os 7 URLs da §8.3 mais as falhas fechadas. A tabela do histórico tem 11 casos.

**AST.**
- A1, A2 e A3 rodam nos 4 arquivos. A2 vale também no `executor.py`, além do que a §8.4 pedia, e isso é mais estrito.
- A4 foi ajustada: em vez de "não importa", ela proíbe `gemini_tools_schema` e `analisar_log_complexo` como nome, atributo ou `ImportFrom`, além da constante de texto, e exige o `import tools.gemini_router`.
- O desvio deliberado (`getattr` com texto montado) fica fora do alcance, como os demais residuais de evasão.

**Interfaces.**
- Web: W1 a W6 e C3.
- CLI: C1, C2 (parametrizado nas 4 ferramentas), C3 e histórico.

**Mutantes, contagem nos relatórios `.md` (L54).**
- C2 tem 16/16, C3 6/6 e C4 14/14 (app_b 8, main_b 5, dba_b 1), todos com "Resultado: todas DETECTADAS".
- Os 3 primeiros `mut_c4_*` têm m0 INVÁLIDO (§6.2).

**Mudanças em testes.**

| Teste | Classe | Enfraquece? |
|---|---|---|
| `test_oracle_kill.py:1296→:1328`, literal do N5 | Expectativa alterada, declarada (V6): o literal segue com o mesmo rigor, só com o texto novo | não |
| T7, `proibidos` | Asserção acrescentada: DSN, host, `instancia`, os 3 nomes do pacote, aprovador, erro de rede e regex de hash em todo ramo; `presentes` com `ORA-00600`; casos `alvo_alterado` e `reconsulta_rede` | não; mais estrita |
| `test_fluxo_web.py` `_montar` e `_OpenAIFalso` | Expectativa alterada, declarada: o padrão passa de Ollama offline a local, com `base_url` guardado. Os casos de nuvem foram para W1-W6 | não; nenhuma asserção removida |
| `test_fluxo_cli.py` `_LLMFalso` | Fixture: `base_url` local por padrão, e `nome` e `argumentos` parametrizáveis (declarado) | não |

Nenhuma asserção foi removida no diff.

**Greps 3.x do PROCESSO §5, sobre as linhas acrescentadas do diff.**
- 3.1 a 3.6: nenhuma linha.
- `git diff --stat` de `registry/` e `db/`: vazio.
- Nenhum `.env` entre os 8 arquivos.

**Greps extras do plano §6.** `check_rede['host']`, `str(db_err)` e `str(exc)` não aparecem em linha acrescentada. `"instancia"` e os 3 nomes do pacote só aparecem em comentário e em lista de proibidos dos testes (L50 conferida).

## 6. Observações (não bloqueiam)

1. **`oracle_dba.py:1089` (D8) mantém "Erro a partir da chamada ao PKG".**
   - Não é sentinela, e a decisão §2.3 deu o D8 por correto, então está CONFORME.
   - Fica inconsistente com o ramo Oracle, que passou a "chamada de encerramento".
   - Mudança opcional: trocar para "chamada de encerramento" e incluir `"PKG"` nos proibidos do caso `d8` do T7. O controle negativo é que o T7 `d8` falha no código atual.
2. **O m0 INVÁLIDO em `mut_c4_app`, `mut_c4_dba` e `mut_c4_main`.**
   - Fato: na teardown de `test_web_painel_fecha_apos_aprovar` apareceu "Log real alterado", com os arquivos `auditoria_oracle.log` da **cópia** passando de inexistentes a existentes (`mut_c4_app_m0.txt`).
   - Inferência: o `git archive` não tem os logs, e o FileHandler os cria. Nas rodadas `_b`, a ordem pôs `test_fluxo_cli.py` primeiro, e o import do `main.py` criou os arquivos fora do snapshot.
   - Não indica escrita no log real, porque a suíte com o snapshot passou na árvore real (1539/16, informado).
   - Registrar a causa no GOVERNANCA_LOG (espírito da L52).
3. **Linha sem prova: a trava do laudo final da CLI (`src/main.py:449-451`).**
   - Hoje ela é inalcançável, e o teste de histórico da CLI força `True` e sai na 1ª trava.
   - Teste opcional:
     - Fixture: um `_LLMFalso` com a nuvem que sempre devolve uma tool_call `ferramenta_inexistente`, e um `historico_tem_dado_do_banco` falso que dá `False` nas 6 primeiras chamadas e `True` na 7ª.
     - Asserções: `len(llm.chamadas) == 6` e o texto fixo na saída.
     - Controle negativo: sem `:449-451`, as chamadas passam a 7.

## 7. Residuais e decisões do responsável

- **Decisões 1a (V3 e caminho no executor) e opção (a) (import mantido como sonda, com a A4 ajustada).**
  - Aparecem no pedido do C7, nas mensagens de commit e na docstring da A4.
  - **Não estão no plano §5.2 nem no GOVERNANCA_LOG** (Grep sem resultado).
  - Não confirmo a autoria (L2).
  - **Registro PENDENTE:** a sessão principal registra no GOVERNANCA_LOG, no fechamento, as duas decisões com a data e o texto do responsável.
- **R-e (novo), PENDENTE APROVAÇÃO para a tarefa que ligar o `executor.py` ao LLM.**
  - O nome da ferramenta do executor tem de entrar no bloqueio de nuvem (catálogo e despacho).
  - Hoje só a trava de histórico conteria o envio, e o script já teria rodado no banco.
- **Seguem da decisão_c1 §11:** o R-a (o RAG na nuvem, pendente), o R-b (`OPS_KILL_AUDIT` no texto, aceito), o R-c e o R-d.
- **Sem mudança:** `db/ops_kill.sql`, `registry/`, a lista de protegidos e os privilégios (o diff `--stat` de `registry/` e `db/` está vazio).

## 8. Fato e inferência

- **Fato:**
  - o diff `36746cf..e1d4ce6` e as linhas citadas no `e1d4ce6`;
  - os relatórios `mut_*.md` e `mut_c4_app_m0.txt`;
  - os greps acima.
- **Informado, não reexecutado:** pytest 1539/16 e os controles negativos (44, 8 e 20 falhas).
- **Inferência:**
  - a causa do m0 inválido (§6.2);
  - a ausência de efeito da 2ª instância de `oracle_dba` sob `src.tools`.
- **Sem fato de banco.**
