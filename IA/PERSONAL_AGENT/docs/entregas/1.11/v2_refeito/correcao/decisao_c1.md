# Decisão C1: 1.11-V2-item6, correção depois da revisão do Gemini (plano §8.3, com o §8.10)

- Quem: `seguranca`, claude-opus-5-5. 2026-11-24. Só leitura: sem Oracle, sem pytest, sem `.env`.
- Base: `item6/v2`, HEAD `f9482c4` (`git rev-parse HEAD` conferido). `src/`, `app.py` e `tests/` sem diff no working tree (`git status --short` vazio para eles).
- Fontes: `revisao_adversarial_gemini.md`, `correcao/passo0.md`, `v2_refeito/decisao.md`, `docs/entregas/1.11/item6/ops_kill.sql` e o código. Todas as linhas abaixo foram conferidas agora (L9). As linhas do plano (de `2210b31`) continuam iguais.

## Veredito: PENDENTE

Os 8 pontos estão decididos e podem ser implementados. Um deles depende do responsável antes do C3/C4 (P1, §9): o regime aprovado ("todo o resto é desconhecido", 8.3.2) inclui o ERRO_INTERNO, mas **um teste existente afirma o contrário**. É o `tests/test_item1_intencao.py:651`: com ERRO_INTERNO antes da conta KILL, o teste espera o e-mail "NÃO executada". O plano não declara essa mudança de expectativa.

## 1. Fatos verificados

| Fato | Onde |
|---|---|
| Status que o PKG v2 grava em `v_status`: PARAM_INVALIDO, PROPRIA_SESSAO, ALVO_NAO_ENCONTRADO (NO_DATA_FOUND), ALVO_DIVERGENTE, NAO_USUARIO e USUARIO_PROTEGIDO antes do `EXECUTE IMMEDIATE`; ENCERRADA, MARCADA_PARA_KILL (-31), ALVO_NAO_ENCONTRADO (-30) e ERRO_ORACLE (outros) no bloco do `ALTER SYSTEM` | `ops_kill.sql:128`, `:133`, `:155`, `:161`, `:173`, `:176`; `:188`, `:192`, `:194`, `:196` |
| O PKG não tem `EXCEPTION` externo. Se o SELECT der um erro que não é NO_DATA_FOUND, ou se o `registra` falhar (inclusive depois do ENCERRADA), a exceção sobe ao driver | `ops_kill.sql:140-156`, `:203-206` |
| Todo ramo do PKG define `v_status`, então `p_status` vazio ou nulo só vem de anomalia do driver ou de outra versão do PKG | `ops_kill.sql:119-200` |
| O status lido cai no `return` genérico, com "executado para" e sem `resultado_desconhecido` | `oracle_dba.py:870`, `:887-902` |
| `except oracledb.Error` formata `{db_err}` e `str(db_err)` sem proteção; `except Exception` usa `str(exc)` antes do execute; `"instancia": dsn` em `:915` e `:935` | `oracle_dba.py:904-942` |
| Validação, `getenv` e sonda de rede ficam **fora** do `try` (a sonda pode levantar) | `oracle_dba.py:753-820`, `:805` |
| Em `registrar_decisao_kill`, o ERRO_INTERNO sai sem `resultado_desconhecido`, o parse falho ecoa `str(resultado_exec)`, um JSON que não é dict levanta `AttributeError` em `.get`, e o `bool(.get(...))` dá False por omissão | `oracle_dba.py:1688-1705`, `:1742-1748` |
| `montar_notificacao_kill(..., resultado_desconhecido: bool = False)`: o default abre a falha. O corpo diz "retornou erro do Oracle" (A9). Nenhum teste chama a função diretamente (grep `montar_notificacao_kill\(` em `tests/` vazio) | `oracle_dba.py:1399-1451`, `:1407`, `:1423` |
| `preparar_intervencao_kill` não valida a identidade e não grava nada no JSONL nas recusas. Ela não recebe `caminho_log` | `oracle_dba.py:1836-1916` |
| A sonda chamada dentro de `consultar_alvo_sessao_diag` fica fora do `try` (`:590`). O teste `test_erro_interno_grava_resultado` usa esse ponto (2ª sonda levanta, ERRO_INTERNO sem KILL) e afirma "NÃO executada" | `oracle_dba.py:590`; `test_item1_intencao.py:638-655`, `:651` |
| O reconciliador só trata `fase` INTENCAO ou RESULTADO. Linha com `fase` e sem `id_intervencao` de 32 hex conta como `linhas_invalidas` (aviso a cada subida) | `oracle_dba.py:1345-1354` |
| `_montar_registro_aprovacao_kill` recusa fase fora de `FASES_REGISTRO_KILL` e decisão fora de `DECISOES_KILL` | `oracle_dba.py:1252-1257` |
| `matar_sessao_oracle` não é importada de `src.tools` por ninguém (grep): `main.py:139` e `app.py:146` importam de `tools.oracle_dba` e roteiam pelo nome em texto | `src/tools/__init__.py:6`, `:30`; `oracle_dba.py:2035` |
| Gate de sandbox: `pytest_runtest_setup` pula `sandbox_only` sem `ORACLE_SANDBOX=1` | `tests/conftest.py:185-188` |
| CLI e Web conferem `resultado_desconhecido` antes de `executado`. Textos atuais | `src/main.py:257-262`; `app.py:510-516` |
| O fake tem `status_pkg=None` por padrão. Nenhum teste atual chega ao `getvalue` com `None` esperando "NÃO executada": os casos com KILL e sem `status_pkg` usam `erro_kill` ou `erro_connect_kill` | `tests/fakes_oracle.py:108`; `test_item1_intencao.py:437-446`, `:497` |

## 2. Ponto 1: conjunto fechado "NÃO executada"

Constante nova em `oracle_dba.py`, logo depois de `RESULTADOS_KILL_EXECUTADO` (`:74`):

```python
# p_status do PKG_OPS_KILL v2 que provam que nenhuma sessão foi encerrada (ops_kill.sql:128-176; o
# ALVO_NAO_ENCONTRADO também vem do ORA-00030 no ALTER SYSTEM, :193-194). Lista FECHADA: qualquer outro
# p_status (ERRO_ORACLE, vazio, nulo, código novo) é resultado desconhecido (decisao_c1.md, ponto 1).
RECUSAS_PKG_SEM_KILL: Tuple[str, ...] = (
    "PARAM_INVALIDO", "PROPRIA_SESSAO", "ALVO_NAO_ENCONTRADO",
    "ALVO_DIVERGENTE", "NAO_USUARIO", "USUARIO_PROTEGIDO",
)
```

- **ALVO_NAO_ENCONTRADO por ORA-00030: fica no conjunto.** O ORA-00030 diz que não existe sessão com esse `sid,serial#` na instância, então esta chamada não encerrou nada. "NÃO executada" descreve o efeito (nenhuma sessão encerrada), mas não diz que o PKG parou antes do `ALTER SYSTEM`. O código próprio fica como insumo da PENDENTE APROVAÇÃO 1 (8.8), como o plano prevê. O aceite do risco vai ao responsável (P2).
- **Invariantes (L23), cada uma com teste:**
  - `RECUSAS_PKG_SEM_KILL` e `RESULTADOS_KILL_EXECUTADO` são disjuntos;
  - nenhum dos quatro valores `"ERRO_ORACLE"`, `""`, `"DESCONHECIDO"` e `"ERRO_INTERNO"` está em algum dos dois conjuntos;
  - o conjunto dos literais `v_status := '([A-Z_]+)'` em `docs/entregas/1.11/item6/ops_kill.sql` é igual à união `RECUSAS ∪ EXECUTADO ∪ {"ERRO_ORACLE"}`. Assim, um status novo no SQL obriga a classificá-lo.

## 3. Ponto 2: todo o resto é `resultado_desconhecido=True`. O mecanismo que falha fechado

O canal é **só o bool explícito**, nunca o nome do status: PARAM_INVALIDO, ALVO_NAO_ENCONTRADO e USUARIO_PROTEGIDO também saem da DIAG e da validação local.

**a) `matar_sessao_oracle`.** Todo `json.dumps` traz `"resultado_desconhecido"` bool literal:
- `False` nos retornos antes do `try`: `:755`, `:772`, `:791` e `:807`;
- `execute_iniciado` nos dois `except`.

Depois do `execute`, a classificação fica nesta ordem exata:

```python
status_banco = str(status_var.getvalue() or "").strip()
if status_banco in RESULTADOS_KILL_EXECUTADO:   # desconhecido False; mensagem "Procedimento ... executado para ..." (texto atual, :896-898)
elif status_banco == "ALVO_DIVERGENTE":          # desconhecido False; MENSAGEM_ALVO_DIVERGENTE (texto atual)
elif status_banco in RECUSAS_PKG_SEM_KILL:       # desconhecido False; MENSAGEM_RECUSA_PKG.format(status=status_banco)
else:                                            # desconhecido True; status_banco = status_banco or STATUS_PKG_VAZIO
```

As chaves `status`, `motivo`, `status_banco`, `inst_id`, `sid` e `serial` continuam como hoje (`:876-881`).

**b) Constantes e textos literais** (`oracle_dba.py`, junto de `MENSAGEM_RESULTADO_DESCONHECIDO`, `:49`):

```python
MENSAGEM_DESFECHO_NAO_CONFIRMADO = "desfecho no banco não confirmado"
MENSAGEM_RECUSA_PKG = "Encerramento NÃO executado: recusado pelo PKG_OPS_KILL (status {status})."
STATUS_PKG_VAZIO = "DESCONHECIDO"
```

- Ramo desconhecido do `p_status`:
  `f"{MENSAGEM_RESULTADO_DESCONHECIDO}. Status retornado pelo PKG_OPS_KILL: {status_banco}; {MENSAGEM_DESFECHO_NAO_CONFIRMADO}. Consulte OPS_KILL_AUDIT."`
- "executado para" só aparece no ramo `RESULTADOS_KILL_EXECUTADO`.

**c) `executar_kill_verificado`:** `"resultado_desconhecido": False` nas 4 recusas (`:1050`, `:1069`, `:1089` e `:1104`).

**d) `registrar_decisao_kill` (`:1688-1748`):**

```python
# ERRO_INTERNO (:1694): + "resultado_desconhecido": True, e a mensagem passa a
#   f"{MENSAGEM_RESULTADO_DESCONHECIDO}. Erro interno no fluxo de kill; estado no banco não confirmado. Consulte OPS_KILL_AUDIT."
try:
    dados_exec = json.loads(resultado_exec)
    parse_ok = isinstance(dados_exec, dict)
except (TypeError, ValueError):
    parse_ok = False
if not parse_ok:   # sem eco do texto recebido (hoje :1745 ecoa str(resultado_exec) ao LLM)
    dados_exec = {"status": "erro", "status_banco": STATUS_PKG_VAZIO, "resultado_desconhecido": True,
                  "mensagem": f"{MENSAGEM_RESULTADO_DESCONHECIDO}. Retorno do fluxo de kill ilegível; "
                              "estado no banco não confirmado. Consulte OPS_KILL_AUDIT."}
resultado_banco = str(dados_exec.get("status_banco") or dados_exec.get("motivo") or "DESCONHECIDO")
resultado_desconhecido = not (parse_ok and dados_exec.get("resultado_desconhecido") is False)
executado = resultado_banco in RESULTADOS_KILL_EXECUTADO and not resultado_desconhecido
```

- Em `:1815-1817`, também `dados_exec["resultado_desconhecido"] = resultado_desconhecido`: o LLM vê o valor efetivo.
- Uma chave ausente, um `0`, um `None` ou um `"false"` dão desconhecido, porque só o `False` literal tira o desconhecido.

**e) E-mail (A9, `:1407`, `:1412`, `:1423`):**
- a assinatura passa a `canal: str, *, resultado_desconhecido: bool` (sem default). O único chamador já passa por nome (`:1804`);
- o corpo do desconhecido passa a `f"foi aprovado por {aprovador} ({canal}); {MENSAGEM_DESFECHO_NAO_CONFIRMADO}.\n"`, no lugar de "a chamada ao PKG_OPS_KILL retornou erro do Oracle.";
- a docstring troca "(ERRO_ORACLE a partir do execute do PKG)" por "(qualquer desfecho fora da lista fechada)".

**Efeito declarado (P1):** um ERRO_INTERNO **antes** da conta KILL, como a sonda da reconsulta em `:590`, passa a sair como "resultado desconhecido". É mais conservador, mas muda o `test_item1_intencao.py:651`. Avaliei a alternativa precisa, `ErroPreKill`, que envolveria a parte antes do KILL em `executar_kill_verificado` e marcaria o desconhecido como False. Não a adoto:
- ela cria um ramo que pode abrir a falha se a chamada a `matar_sessao_oracle` entrar na região envolvida;
- `resultado["motivo"] == "RuntimeError"` (`:648`) exigiria repassar `tipo_erro`.

## 4. Ponto 3: nenhuma exceção sai de `matar_sessao_oracle` depois do `execute_iniciado`

Helper total, perto de `_texto_identidade_invalido`:

```python
def _descrever_erro(exc: BaseException) -> str:
    """Texto do erro para mensagem; nunca levanta (A3): str(exc), senão o nome do tipo, senão texto fixo."""
    try:
        return str(exc)
    except Exception:
        pass
    try:
        return type(exc).__name__
    except Exception:
        return "Exception"
```

- `:906`: `f"...: {_descrever_erro(db_err)}"`. `:908`: `_descrever_erro(db_err)`. `:929`: `_descrever_erro(exc)`. `:927`, `:933` e `:938` continuam com `type(exc).__name__`.
- **Erro antes do `execute` passa pelo helper: sim, com desconhecido `False`.** O `execute_iniciado` só vira `True` em `:843`, depois de `connect`, `cursor`, `var` e `setvalue`. O PKG não rodou. O conteúdo do `str` cru continua como hoje e é saneado na R1 (8.8).
- O dict do `except` só leva inteiros, textos fixos e o texto do helper. O `"instancia": dsn` sai de `:935` (A5). O de `:915` fica para a R1.
- `BaseException` não é capturada e chega ao INTERROMPIDO (`:1706-1740`), que já registra "desfecho desconhecido".
- Defesa em profundidade: se algo escapar mesmo assim (um `MemoryError` dentro do `except`), o ponto 2d classifica como desconhecido. As duas camadas falham fechadas.

## 5. Ponto 4: texto da CLI e da Web

Constante compartilhada, importada por `main.py` (`:139-148`) e `app.py` (`:146-155`) do mesmo jeito que `MENSAGEM_RESULTADO_DESCONHECIDO`:
- `src/main.py:259-261`: `f"{MENSAGEM_RESULTADO_DESCONHECIDO} ({MENSAGEM_DESFECHO_NAO_CONFIRMADO}; resultado: {desfecho['resultado_banco']}).\033[0m"`;
- `app.py:512-513`: `f"... {MENSAGEM_RESULTADO_DESCONHECIDO}** ({MENSAGEM_DESFECHO_NAO_CONFIRMADO}; resultado: \`{desfecho['resultado_banco']}\`). "`.

O texto é "desfecho **no banco**", e não "da chamada ao PKG", porque o ERRO_INTERNO e o parse falho podem acontecer sem chamada ao PKG. A ordem dos `elif` não muda (desconhecido antes de executado).

## 6. Ponto 5: A10, parte 2 (validação pré-HITL e evento próprio)

- **Validação:** separar `campos_invalidos_identidade(identidade) -> List[str]`, que é total, e fazer `campos_invalidos_identidade_e_ref` chamá-la e acrescentar o ref. Em `preparar_intervencao_kill`, depois da elegibilidade (`:1875-1896`) e **antes** do hash (`:1900`):
  `alvo = check_alvo.get("alvo")`, `fonte = alvo if isinstance(alvo, dict) else {}`, `identidade = {c: fonte[c] for c in CAMPOS_IDENTIDADE_ESPERADA if c in fonte}` (a mesma montagem de `:1118`, sem `.get` com default).
- **A10, parte 1:** `_texto_identidade_invalido` passa a `len(valor) > LIMITE_TEXTO_IDENTIDADE or len(valor) < 1` nos dois casos. O `""` é recusado em `program` e `machine`.
- **Evento:** constante `FASE_RECUSA_PRE_HITL = "RECUSA_PRE_HITL"`. Ela **não** entra em `FASES_REGISTRO_KILL` (`:41`), e `registrar_log_aprovacao_kill(fase="RECUSA_PRE_HITL")` continua dando `ValueError`. Builder próprio `_montar_registro_recusa_pre_hitl`, gravado pelo `_gravar_linha_jsonl_duravel` (ponto único; atualizar a docstring de `:1225`). As chaves são exatamente estas:

  ```json
  {"timestamp": "<UTC ISO>", "fase": "RECUSA_PRE_HITL", "id_intervencao": "<uuid4().hex novo>",
   "motivo": "PARAM_INVALIDO", "campos_invalidos": ["logon_time"],
   "parametros": {"inst_id": 1, "sid": 101, "serial": 202}}
  ```

  - `campos_invalidos`: sublista, na ordem da função, de `("identidade_esperada","username","program","machine","logon_time")`. Só nomes.
  - Ficam de fora `alvo`, `aprovador`, `decisao`, `hash_payload` e `resultado_banco`.
  - O `id_intervencao` é só deste evento: não vai ao PKG, ao LLM nem a uma INTENCAO. Ele existe porque o reconciliador conta como inválida uma linha com `fase` e sem id de 32 hex (`:1347-1350`). Com ele, o reconciliador **não muda**.
- **Quem lê:** só o auditor. `reconciliar_intencoes_orfas` ignora a linha porque a fase não é INTENCAO nem RESULTADO (`:1351-1354`). O teste prova `reconciliadas == []`, `linhas_invalidas == 0` e o arquivo igual.
- **E-mail: não.** O e-mail é da intervenção aprovada e aqui não houve aprovação nem conexão KILL. Um SMTP dentro de `preparar`, no rerun da Web, seria superfície nova. A identidade inválida vinda da `GV$SESSION` só aparece por defeito (DATE não tem µs; o Oracle devolve `''` como NULL), então basta `logger.warning` com nomes e id:
  `f"HITL RECUSADO LOCALMENTE: PARAM_INVALIDO (identidade do alvo) | inst_id=..., sid=..., serial=... | campos={...} | id_intervencao=..."`.
- **Falha ao gravar o evento:** `except Exception` dá `logger.error` com o tipo, o errno e `_serializar_para_log(registro)`, e a recusa segue (sem prompt, sem KILL). `BaseException` propaga, e nada foi feito ainda.
- **Retorno:** `{"requer_aprovacao": False, "motivo": "PARAM_INVALIDO", "mensagem": M, "resultado_tool": json.dumps({"status": "recusado", "motivo": "PARAM_INVALIDO", "status_banco": "PARAM_INVALIDO", "mensagem": M})}`, sem `alvo`. O texto é:
  `M = "Identidade do alvo lida na GV$SESSION fora do formato esperado; aprovação não solicitada e encerramento NÃO executado. Campos inválidos: <nomes>."`

  O `id_intervencao` do `conduzir_kill_hitl` continua `None`, e a CLI e a Web não mudam: usam `prep["motivo"]` e `prep["resultado_tool"]` (`main.py:241-242`, `app.py:314-327`).
- **Destino do log:** `preparar_intervencao_kill(argumentos, ferramenta=..., caminho_log: Optional[Path] = None)`. `None` resolve na chamada, como em `registrar_log_aprovacao_kill`. O `conduzir_kill_hitl` repassa o seu `caminho_log`. O `app.py:312` não muda.
- **T7 (declarado no commit e no log, decisão 8.10.2):** o caso `param_invalido` (`test_oracle_kill.py:911-912`) passa a conferir:
  - `prompt_exibido is False`, `motivo == "PARAM_INVALIDO"`, `conexoes_kill == []`;
  - o JSONL com uma só linha, de fase `RECUSA_PRE_HITL`;
  - o id do evento e os `proibidos` fora do `resultado_tool`.

  O `fullmatch` de `:930` passa a valer sobre o id do evento. A cobertura do PARAM_INVALIDO de `matar_sessao_oracle` fica no T2 (chamada direta, `:787`).

## 7. Pontos 6, 7 e 8

- **6. Charset:** aceito como proposto.
  - `PREMISSA_CHARSET_MODELO = "AL32UTF8"`, com o comentário "NÃO VERIFICADA (L7): o charset do MODELO não foi lido".
  - O fake responde `p_status="PARAM_INVALIDO"` quando algum dos 3 textos não nulos tem `len(v.encode("utf-8")) > 128`.
  - O limite local continua `len(s) > 128` em caracteres (D1).
  - A leitura que fecha a premissa no ensaio 4.1, a ser fornecida pelo responsável: `SELECT value FROM nls_database_parameters WHERE parameter = 'NLS_CHARACTERSET'`.
- **7. A8:** basta tirar da exportação (`__init__.py:6` e `:30`), sem renomear. O nome da ferramenta é texto no schema (`:2035`) e no roteamento, e renomear a função não cria barreira: qualquer código no processo alcança `src.tools.oracle_dba` e o `oracledb`. A barreira real é o grant EXECUTE só para STARTUP_KILL mais o PKG, e o ref não é autorização (`ops_kill.sql:53-55`). Fica registrado como residual (P3).
- **8. A6, gate:** aceito, na forma de um helper no `test_oracle_kill.py`, chamado como **1º comando** do corpo de cada um dos 4 (depois da docstring):

  ```python
  def _exigir_pkg_kill_v2() -> None:
      """Gate do ensaio 4.1 (A6). Não substitui o ORACLE_SANDBOX, que o conftest confere antes."""
      if os.getenv("OPS_KILL_PKG_VERSAO") != "2":
          pytest.skip("Teste ignorado: requer OPS_KILL_PKG_VERSAO=2 (PKG_OPS_KILL v2 instalado)")
  ```

  - Sem sandbox, o `conftest:185-188` pula antes, e o skipped continua 16.
  - O gate não é barreira de segurança. Mesmo que a variável venha do perfil do Windows ou do `python.envFile`, o Python v2 contra o PKG v1 dá PLS-00306 e nada executa.
  - Nenhum teste define `OPS_KILL_PKG_VERSAO`, nem por `monkeypatch`.
  - O teste AST (m28) confere nos 4: o 1º comando é `_exigir_pkg_kill_v2()`, que vem antes de qualquer `oracledb.connect`; `identidade_esperada` e `ref_aprovacao` estão em toda chamada a `matar_sessao_oracle`; e `connect`/`close` ficam em `try/finally`.

## 8. Recusas e registros, depois da correção

| Caso | KILL conecta? | JSONL | OPS_KILL_AUDIT | E-mail | `desconhecido` |
|---|---|---|---|---|---|
| inst/sid/serial inválidos; não elegível na pré-consulta | não | nada | não | não | False |
| **identidade inválida na pré-consulta (novo)** | não | **RECUSA_PRE_HITL** | não | não | False |
| REJEITADO / SEM_IDENTIFICACAO / TIMEOUT; FALHA_LOG_APROVACAO | não | RESULTADO; nada | não | não | False |
| reconsulta falha / ALVO_ALTERADO / não elegível / APROVACAO_EXPIRADA; PARAM_INVALIDO local; ERRO_CONFIG; VPN | não | INTENCAO+RESULTADO | não | "NÃO executada" | False explícito |
| erro em `connect`/`var`/`setvalue` | tenta | INTENCAO+RESULTADO ERRO_ORACLE ou tipo | não | "NÃO executada" | False (`execute_iniciado`) |
| `p_status` em `RECUSAS_PKG_SEM_KILL` | sim | INTENCAO+RESULTADO | sim, com ref (doc) | "NÃO executada" | False |
| ENCERRADA / MARCADA_PARA_KILL | sim | INTENCAO+RESULTADO | sim (doc) | "Aprovada" | False |
| ERRO_ORACLE, `""`, `None` ou código novo no `p_status`; exceção depois do execute; PLS-00306 | sim | INTENCAO+RESULTADO | sim ou não (doc) | "resultado desconhecido" | **True** |
| ERRO_INTERNO (qualquer ponto); retorno ilegível | talvez | INTENCAO+RESULTADO | ? | "resultado desconhecido" | **True** (P1) |
| `BaseException` | talvez | INTENCAO+RESULTADO INTERROMPIDO | ? | não | re-raise |

- O `auditoria_oracle.log` recebe o `resultado_tool`, agora com `resultado_desconhecido` e sem id (`main.py:428`, `app.py:538`).
- A conta KILL continua executando só o bloco constante de 9 binds.
- Falha fechada em todas as linhas. Os pontos que não fecham continuam os do `decisao.md` §10 (a micro-janela no PKG, o MARCADA_PARA_KILL concorrente) e a imprecisão conservadora do ERRO_INTERNO antes do KILL.

## 9. Ataques

- **TOCTOU:** sem mudança. O PKG compara no mesmo SELECT (D2). A validação pré-HITL não abre janela, porque a fonte do kill continua sendo a reconsulta cujo hash bateu.
- **Ambiente:** nenhum `getenv` novo em produção. O gate só existe em teste, depois do conftest.
- **Concorrência:** o evento usa os mesmos dois locks (`:1231-1234`). Lock indisponível é `TimeoutError`, que leva ao `logger.error` com a recusa mantida.
- **Rerun e abas (L8):** `preparar` não chama `st.*`, então o rerun não a interrompe no meio (inferência sobre o Streamlit, a mesma do `decisao.md` §11). Um evento duplicado teria ids distintos e não teria efeito.
- **Exceção ou interrupção:** pontos 3 e 2d. Uma linha parcial por interrupção já conta como `linhas_invalidas` (comportamento atual).
- **Desconhecido depois do execute:** fechado pelo bool explícito com `is False`.

## 10. Testes e controle negativo (todos falham em `921e6ef`, salvo onde se indica)

| Teste | Mata | Por que falha hoje |
|---|---|---|
| `p_status` ∈ {ERRO_ORACLE, `""`, `None`, `"XYZ"`, `"encerrada"`}: desconhecido True, `executado` False, 1 execute KILL, e-mail e tool com `MENSAGEM_RESULTADO_DESCONHECIDO` e sem "NÃO executada" nem "executado para" | A1, m17, m18 | `passo0.md:11-13` |
| as 6 recusas do PKG: desconhecido False, `MENSAGEM_RECUSA_PKG` (o ALVO_DIVERGENTE com o texto próprio), sem "executado para" | A1 | hoje "executado para" |
| invariantes do ponto 1 (com a união × `ops_kill.sql`) | m17 | a constante não existe |
| `__str__` do `db_err` levanta depois do execute: JSON ERRO_ORACLE, desconhecido True, nenhuma exceção sai | A3, m21 | `passo0.md:14` |
| o mesmo antes do execute (no `connect`): ERRO_ORACLE com desconhecido False e mensagem igual ao nome do tipo | m21 | hoje dá ERRO_INTERNO |
| `matar_sessao_oracle` monkeypatched devolvendo não JSON, `"[]"`, ou JSON sem a chave: desconhecido True; o texto não ecoa no tool | A3, m20 | `passo0.md:15`; `"[]"` levanta |
| ERRO_INTERNO: desconhecido True (`test_item1_intencao.py:651` alterado, **P1**) | m19 | `passo0.md:14` |
| AST: todo `json.dumps({...})` de `matar_sessao_oracle` e `executar_kill_verificado` tem a chave `resultado_desconhecido` | ponto 2a/2c | as chaves faltam |
| `inspect`: `resultado_desconhecido` de `montar_notificacao_kill` keyword-only, sem default | ponto 2e | hoje tem default |
| CLI e Web com `p_status=""`: tela com `MENSAGEM_RESULTADO_DESCONHECIDO` e `MENSAGEM_DESFECHO_NAO_CONFIRMADO`, sem "NÃO EXECUTADA"/"NÃO executada" | m29, m30 | hoje "NÃO EXECUTADA" |
| e-mail do D8 e do `p_status=""`: sem "erro do Oracle", com `MENSAGEM_DESFECHO_NAO_CONFIRMADO` | A9, m24 | `passo0.md:16` |
| `program=""` e `machine=""` são inválidos | A10, m25 | `passo0.md:19` |
| fluxo com µs ou `""` na DIAG: sem prompt, sem KILL, só a linha RECUSA_PRE_HITL com as chaves exatas, sem valores; o reconciliador a ignora; `registrar_log_aprovacao_kill(fase=...)` dá `ValueError`. Usar o ano 2001 no `logon_time` para não coincidir com o `timestamp` | A10-2, m31 | hoje há prompt e INTENCAO |
| `"é"*128` (128 caracteres, 256 bytes) aceito localmente; o fake dá PARAM_INVALIDO; `"é"*64` passa; `"a"*128` aceito e `"a"*129` recusado | m27, M_LIMITE_GE_128 | o fake não simula (C2) |
| `import src.tools`: o nome fora de `__all__` e sem atributo | A8, m23 | `__init__.py:6`, `:30` |

## 11. PENDENTE ao responsável (antes do C2/C3)

- **P1 (bloqueia o C3/C4).** Confirmar que o ERRO_INTERNO é **sempre** desconhecido, com a mudança declarada de `test_item1_intencao.py:651`:
  - de `"NÃO executada" in assunto` para `MENSAGEM_RESULTADO_DESCONHECIDO in assunto and "NÃO executada" not in assunto and desfecho["resultado_desconhecido"] is True`;
  - o `conexoes_kill == []` (`:650`) fica.

  Não é enfraquecimento, mas muda uma asserção existente (CLAUDE.md, §8.7). A alternativa é o `ErroPreKill` (§3), que não recomendo.
- **P2 (aceite de risco).** O ALVO_NAO_ENCONTRADO por ORA-00030 é relatado como "NÃO executada", e o código próprio fica para a PENDENTE APROVAÇÃO 1 (SQL v2).
- **P3 (residual).** `matar_sessao_oracle` continua alcançável por `src.tools.oracle_dba`. O ref não é autorização.
- **P4 (L7).** `PREMISSA_CHARSET_MODELO` fica não verificada até a leitura do §7. A variável `OPS_KILL_PKG_VERSAO` no `.env.example` (área do §2) fica para o ensaio 4.1, como o plano prevê.
- **Sem mudança aqui:** `db/ops_kill.sql`, `registry/`, a lista de protegidos e os privilégios. K2 e K4 continuam "PENDENTE APROVAÇÃO".
- **Sugestão, não exigida:** mostrar o `id_intervencao` na tela e no e-mail do desconhecido facilitaria cruzar com `OPS_KILL_AUDIT.ref_aprovacao` (tarefa própria).

## 12. Fato × inferência

- **Verificado:** todas as linhas do §1 e as citadas nos pontos, lidas em `f9482c4`. Para os comportamentos de hoje, a fonte são as saídas do `passo0.md`.
- **Inferência:**
  - o ORA-00030 implica que nada foi encerrado (documentação Oracle, não lida no banco);
  - `str()` nunca devolve não-str (contrato do Python);
  - o rerun do Streamlit só age em chamadas `st.*`;
  - o `MemoryError` no `except` é hipotético, citado só para justificar a segunda camada.
