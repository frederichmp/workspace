# Conferência: 1.11-V2-item6, passo 7 (passo 3 do 1.11-V2)

- Quem: subagente `seguranca`, modelo `claude-opus-5-5`. Só leitura, sem Oracle, sem pytest com `ORACLE_SANDBOX`.
- Base conferida agora: branch `item6/v2`, HEAD `ede7525`. O `git diff` atual dos 6 arquivos é **idêntico** a `diff_item6.diff` (sha256 `de84b764…a04d3` nos dois). `git status` não mostra `tests/conftest.py`, `db/` nem `registry/`.
- Referências: `decisao.md` (D1-D8, T1-T10, §10), plano `docs/plans/1.11-V2-item6.md` §4.2-§4.4 e §7, `docs/entregas/1.11/item6/implantacao.md` §2 e §5, `mut_item6_a2.md`, `mut_item6_b2.md`.
- **Veredito: NÃO CONFORME (só nos testes).** O código de produção está conforme em todos os pontos. Mas existe um teste cego: a retentativa ou o fallback v1 no ramo `ALVO_DIVERGENTE` não é detectado por nenhum teste (§3). Correção mínima no §4.

## 1. Produção: veredito por ponto (fatos conferidos agora)

| Ponto | Onde | Veredito |
|---|---|---|
| Validação local total, antes do `getenv` | `src/tools/oracle_dba.py:753-783` (inst/sid/serial com o texto antigo, depois a identidade e o ref). `getenv` só em `:786-788` | OK |
| Totalidade | `_texto_identidade_invalido` faz `isinstance(str)` antes de `len`. `campos_invalidos_identidade_e_ref` (`:719`) faz `isinstance(dict)` e conjunto exato de chaves antes de indexar. Depois `datetime`, `tzinfo is None` e `microsecond == 0`, e `isinstance(str)` antes do `fullmatch` (`_REGEX_ID_INTERVENCAO`, `:42`) | OK |
| Nenhuma transformação | binds `identidade_esperada[...]` crus (`:863-865`); `None` vai como `None` | OK |
| 9 formais nomeados, 1 bloco, sem fallback nem retentativa | único `KILL_SESSION(` em `src/` e `app.py` (`:847`); só 1 `cursor.execute` em `matar_sessao_oracle` (`:844-869`); nenhum `except` reexecuta (`:904-942`) | OK |
| var DATE | `cursor.var(oracledb.DB_TYPE_DATE)` e `setvalue(0, …)` em `:841-842`, **antes** de `execute_iniciado = True` (`:843`) | OK |
| ref keyword-only sem default, vindo do `id_intervencao` | assinaturas `:735` e `:1017-1025`; `ref_aprovacao=id_intervencao` em `:1686`; `id_intervencao = uuid.uuid4().hex` só em `:1531`; o LLM só fornece inst/sid/serial (`:1849-1851`) | OK |
| Identidade vinda da reconsulta cujo hash bateu, montada depois de hash, elegibilidade e TTL | `:1117-1118`, depois de `:1063`, `:1084` e `:1099`; só chaves presentes; falta de chave vira PARAM_INVALIDO local | OK |
| Mensagens sem SQL, ref, credenciais ou identidade | PARAM_INVALIDO local só nomeia campos (`:777-780`). ALVO_DIVERGENTE tem texto fixo (`:872-885`). D8 pós-execute leva só `type(exc).__name__` (`:927`). ERRO_ORACLE usa `str(db_err)` (decidido no D5) | OK |
| ALVO_DIVERGENTE fora de `RESULTADOS_KILL_EXECUTADO` | `:74`; `executado` vem de `:1747`; CLI e Web decidem pela flag `executado` (`src/main.py:263-271`, `app.py:517-528`) | OK |
| D8 | `except Exception` com `resultado_desconhecido = execute_iniciado` (`:923-942`), sem reexecutar; `registrar_decisao_kill` lê a flag em `:1748` | OK |
| Hash com logon_time | SELECT DIAG com `logon_time` no fim (`:616`); `serial#` continua `row[2]` (`:644`). `CAMPOS_IDENTIDADE_ALVO` = 3 + `CAMPOS_IDENTIDADE_ESPERADA` (`:77`, `:81`). Ramo `datetime` → `isoformat(sep=" ")` antes do `float` (`:966-967`). JSONL com `default=str` (`:1220`) | OK |
| Serialização do `alvo` com `datetime` | todo `json.dumps` que pode levar o `alvo` usa `default=str` (`:1220`, `:1477`, `:1818`, `:1894`). O payload leva a identidade já normalizada (`:1011`, `:982`). Nenhum `json.dumps` de `app.py` ou `main.py` leva o `alvo` | OK, sem `TypeError` novo |
| CLI e Web | mudança só de exibição: `main.py:219`, `app.py:828` e o texto do hash em `app.py:832` | OK |
| `ORACLE_USER` legado, `ALTER SYSTEM`/`ALTER SESSION` no Python | Grep em `src/` e `app.py`: nenhuma ocorrência | OK |

## 2. Testes: só mock, conformes no que cobrem

- Nenhuma linha `+` do diff define `ORACLE_SANDBOX`, mexe em `conftest` ou faz `setenv` novo. A única ocorrência é um comentário (`test_oracle_kill.py:706`). O T2 só faz `delenv` das credenciais KILL e do DSN.
- T1 `:745`; T2 `:801`, com credenciais ausentes, `connect` e `verificar_acessibilidade_host` falhando, o que prova a ordem antes do `getenv`; T3 `:832`; T4 `:861`; T5 `:880`; T7 `:921`; T8 `:942`; T9 `:973`; T10 `:995` (`tests/test_oracle_kill.py`). T6 está em `tests/test_item1_intencao.py:568`, e o §4.3 em `:185`, com `ORDEM_BINDS_KILL_V2` em `:58`.
- As mutações m1-m15 deram DETECTADA (`mut_item6_a2.md`, `mut_item6_b2.md`, saídas fornecidas pela sessão principal, com m0 verde).
- Fake: a var VARCHAR devolve `status_pkg` e as demais devolvem o que o `setvalue` gravou (`tests/fakes_oracle.py:79-86`).

## 3. Defeito: teste cego para retentativa ou fallback no ramo ALVO_DIVERGENTE

- **Requisito:** `implantacao.md:201-205` (`test_kill_ponto_unico_de_chamada`) pede o fluxo completo nos cenários ENCERRADA, **ALVO_DIVERGENTE** e erro no `execute`, cada um com **exatamente 1** `execute` e **1** conexão KILL. O pedido deste passo também exige "sem fallback v1 nem retentativa".
- **Fato:** ENCERRADA é contado (`test_item1_intencao.py:185`, desempacotamento único; T3 `:844`; T10 `:995`). O erro no `execute` também (T6 `:583`, T9 `:981`). **ALVO_DIVERGENTE não é contado:**
  - T5 (`test_oracle_kill.py:880-900`) confere `conexoes_kill` e o desfecho, mas não o número de `execute`;
  - T7 `divergente` só confere o conteúdo do `resultado_tool`;
  - nenhum outro teste usa `status_pkg="ALVO_DIVERGENTE"` (Grep em `tests/`).
- **Mutação m16 (inferência pela leitura do fake; não medida, ver §5):** dentro de `if status_banco == "ALVO_DIVERGENTE":`, antes do `return`, a mutação chama de novo `cursor.execute` com o bloco v1 de 4 formais no mesmo cursor e relê o `status_var`.
  - O fake não levanta erro no `execute` KILL sem `erro_kill` (`fakes_oracle.py:71`), e a var VARCHAR devolve `status_pkg` fixo (`:82`).
  - Por isso o desfecho continua ALVO_DIVERGENTE, com a mesma mensagem e 1 conexão. T5 e T7 passam, e a mutação **SOBREVIVE**.
- **Por que importa:** esse é o fallback mais perigoso, porque mata pela assinatura sem identidade justamente quando o PKG acusou divergência.
  - Contra o PKG v2 sem sobrecarga, o bloco v1 dá PLS-00306 (`implantacao.md:88-90`, documentação, não verificado em banco, L7).
  - Mesmo assim, a garantia "sem fallback" tem de estar no teste e não depender do estado do banco.

## 4. Mudança mínima proposta (só teste; classe de teste do kill, `mecanico` com o teste já especificado)

No fim de `test_t5_alvo_divergente_nao_executado` (`tests/test_oracle_kill.py:880`), acrescentar:
```python
execucoes = _binds_kill(oracle_fake)
assert len(execucoes) == 1, "ALVO_DIVERGENTE: sem fallback v1 nem retentativa (1 execute só)"
sql, binds = execucoes[0]
assert list(binds) == ORDEM_V2
assert re.findall(r"\b(p_\w+)\s*=>", sql) == ORDEM_V2
```
- **Prova:** é o cenário ALVO_DIVERGENTE do `implantacao.md:203-204`. A conexão KILL única já é conferida em `:889`.
- **Controle negativo:** no código atual o teste **passa** (1 execute). Com a m16 acima ele **falha** (`len == 2`). A sessão principal roda a m16 com `tools/controle_mutacao.py` (alvo `src/tools/oracle_dba.py`, testes `tests/test_oracle_kill.py tests/test_item1_intencao.py`) **antes** e **depois** do acréscimo. O esperado é SOBREVIVE antes e DETECTADA depois (L17: medir a correção pela própria mutação).
- **Opcional, mesmo padrão:** `assert len(_binds_kill(oracle_fake)) == 1` no parâmetro `divergente` do T7.

## 5. Experimentos barrados pelo guarda (PARE respeitado; nada contornado)

1. Um Grep por Bash com um padrão que citava o nome do arquivo de ambiente foi barrado (R2). Refeito pela ferramenta Grep, sem esse termo.
2. Um `grep -rn` sem caminho foi barrado (R2). Refeito pela ferramenta Grep, que o próprio guarda indica.
3. Um `cp` com destino de variável de laço foi barrado (R4). Refeito com destinos literais (cópias em `scratchpad/m0` e `scratchpad/m16`, com a m16 aplicada por `python -I`).
4. O `pytest` nas cópias, via `env -C` aninhado, foi barrado (R4, forma opaca). **Não foi refeito.** Pela L33, a sessão principal roda a m16 (§4).

## 6. Recusas e registros (sem mudança em relação ao `decisao.md` §10)

A tabela do `decisao.md` §10 vale para o código como está. Pontos que não fecham, todos já aceitos: a micro-janela dentro do PKG; MARCADA_PARA_KILL concorrente (CLI × Web × abas, R-F2-1); o PLS-00306 relatado como "desconhecido". Interrupção (`BaseException`) entre o `execute` e o `getvalue` cai no INTERROMPIDO (`:1706-1740`), sem mudança. O rerun do Streamlit não ganha chamada nova: em `app.py` mudou só o texto do painel.

## 7. Residuais (não bloqueiam; registrar)

- **Divergência de documentação:** `implantacao.md:159-161` e `:208` dizem que o PLS-00306 gera o e-mail "NÃO executada". O código, o `decisao.md` §10 e o plano §7.4 dão "resultado desconhecido" (decisão de 2026-11-17). O código segue a decisão mais recente. O texto da `implantacao.md` está velho e precisa de nota ou correção numa tarefa de docs.
- **CLI:** o ramo "desconhecido" diz "erro do Oracle a partir da chamada ao PKG" (`src/main.py:258-261`). Para a exceção não Oracle do D8 (por exemplo `RuntimeError`), o texto fica impreciso. É conservador e cosmético.
- **Mensagem genérica:** os outros códigos não executados do PKG (PARAM_INVALIDO, NAO_USUARIO, USUARIO_PROTEGIDO, PROPRIA_SESSAO, ALVO_NAO_ENCONTRADO, ERRO_ORACLE como status) ainda usam o texto "Procedimento … executado para …" (`oracle_dba.py:895-899`), embora `executado` seja False. Vem da v1. O D5 só exigiu o ALVO_DIVERGENTE.
- **`p_status` nulo ou vazio:** depois de um `execute` sem exceção, vira "DESCONHECIDO" com o e-mail "NÃO executada" (`:870`, `:1746-1748`). Vem da v1. Pelo texto proposto (`ops_kill.sql:206`), o PKG v2 sempre atribui `p_status`.
- Os residuais 1 e 2 (DSN e hashes no `resultado_tool`) seguem como tarefa própria (plano §7.2). O Residual 1 é pré-requisito do ensaio sandbox.

## 8. PENDENTE APROVAÇÃO (do responsável; nada decidido aqui)

Nenhum novo. Os existentes continuam fora do item 6 (plano §7.1): o texto do SQL v2, a migração e o rollback depois do ensaio 4.1, e o mínimo privilégio do executor.
