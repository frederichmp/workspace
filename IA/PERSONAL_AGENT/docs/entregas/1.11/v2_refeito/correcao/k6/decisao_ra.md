# K6.1: decisão do R-a (`resultado_desconhecido` na linha RESULTADO)

- Tarefa: 1.11-V2-item6, passo K6.1 (plano §8.12.0 e §8.12.2)
- Base: branch `item6/v2`, HEAD `3b0c08d`. Baseline: 1378 passed, 16 skipped.
- Autor: subagente `seguranca`, modelo `claude-opus-5-5`. Só leitura, sem Oracle e sem pytest.
- Veredito: **CONFORME para executar o K6.2**, nada PENDENTE. O ponto 3 foi decidido pelo responsável: opção (a), keyword-only sem default.

## 0. Fatos verificados agora (L9)

| Fato | Onde |
|---|---|
| `_montar_registro_aprovacao_kill`: keyword-only `fase` e `id_intervencao`; valida decisão, fase, id e a INTENCAO; não toca o disco | `src/tools/oracle_dba.py:1296-1328` |
| `registrar_log_aprovacao_kill` monta (`:1374`) e só depois grava (`:1378`) | `oracle_dba.py:1349-1379` |
| `FASES_REGISTRO_KILL = ("INTENCAO", "RESULTADO")` | `oracle_dba.py:41` |
| Chamadas de produção às duas funções: **6**, todas em `oracle_dba.py`: `:1374` (interna), `:1445` (reconciliador), `:1628` (recusa humana), `:1704` (INTENCAO), `:1798` (INTERROMPIDO), `:1845` (RESULTADO principal). `app.py` e `src/**` não as chamam. | Grep em `*.py` |
| Valor da linha principal: `resultado_desconhecido = not (parse_ok and dados_exec.get("resultado_desconhecido") is False)` | `oracle_dba.py:1839` |
| Recusa humana devolve `resultado_desconhecido: False` | `oracle_dba.py:1696` |
| Registros de recuperação: `logger.error` da recusa humana (`:1643-1659`, dict em `:1648-1657`); `registro_interrompido` (`:1786-1795`, serializado em `:1817`); `logger.critical` da RESULTADO principal (`:1860-1876`, dict em `:1864-1874`) | `oracle_dba.py` |
| Um `TypeError` nas chamadas `:1628`, `:1704`, `:1798` e `:1845` é engolido pelo `except Exception` (`:1640`, `:1716`, `:1811`, `:1857`). O resultado é a recusa ou o registro de recuperação, sem queda. | `oracle_dba.py` |
| Quem chama o reconciliador engole a exceção: `app.py:627-632` (uma vez por sessão do navegador) e `src/main.py:287-295` (CLI) | Read |
| Precedente: `montar_notificacao_kill(..., *, resultado_desconhecido: bool)` é keyword-only sem default, com teste de assinatura | `oracle_dba.py:1483`; `tests/test_oracle_kill.py:1554-1560` |
| O ponto 6 já está coberto: `assert set(reg) == _CHAVES_RECUSA_PRE_HITL` | `tests/test_oracle_kill.py:1108`, `:1159` |
| Nenhum teste compara o conjunto exato de chaves da INTENCAO ou da RESULTADO. Os testes de recuperação leem chaves isoladas. | `tests/test_item1_intencao.py:736-737`, `:759-760`, `:786-788` |
| `registry/` não cita `oracle_dba` | Grep |
| `tools/controle_mutacao.py:94-103` exige **exatamente 1** ocorrência de `de` por mutante | Read |

**Entradas.** O LLM, a CLI (`src/main.py:374`) e a Web (`app.py:446`) chegam por `conduzir_kill_hitl` ou por `registrar_decisao_kill`. Nenhuma das duas assinaturas recebe `resultado_desconhecido`. O valor é sempre calculado dentro de `oracle_dba.py`, a partir do JSON montado pelo próprio código (`:800-1164`). Nenhuma entrada externa define o campo.

**Inferência.** Hoje, um `TypeError` por falta do argumento não derruba nada: vira falha de gravação, ou reconciliação não executada com só um `logging.error`. Por isso a proteção real é o teste AST (ponto 3), e não o `TypeError` do Python.

## 1. Ponto 1: toda linha RESULTADO leva `resultado_desconhecido` booleano

**Regra.** O campo é gravado por `_montar_registro_aprovacao_kill`, só quando `fase == "RESULTADO"`, com a chave logo depois de `resultado_banco`. Nenhum teste depende da ordem das chaves.

| Chamada | Valor passado | Fundamento |
|---|---|---|
| `:1628`, recusa humana (REJEITADO, TIMEOUT, APROVACAO_EXPIRADA, SEM_IDENTIFICACAO; todas passam por este ramo, `:1610-1622`) | `False` literal | Não houve conexão posterior à decisão. Igual ao retorno em `:1696`. |
| `:1845`, linha principal | `resultado_desconhecido=resultado_desconhecido`, a variável de `:1839` | Uma só fonte de verdade para JSONL, e-mail (`:1896`), retorno (`:1922`) e tool (`:1910`) |
| `:1798`, INTERROMPIDO | `True` literal | O `BaseException` chegou durante `executar_kill_verificado`, e o estado do banco não é conhecido |
| `:1445`, NAO_CONCLUIDA do reconciliador | `True` literal | "A conferir em OPS_KILL_AUDIT" (`:1392`) |

Valores esperados pela fórmula de `:1839`, a provar nos testes de fluxo completo (`conduzir_kill_hitl`/`registrar_decisao_kill` com `_OracleFake`):

| Caso | Valor | Meio no fake |
|---|---|---|
| ENCERRADA | `False` | `status_pkg="ENCERRADA"` |
| ALVO_DIVERGENTE | `False` | a segunda linha DIAG diverge |
| recusa do PKG | `False` | `status_pkg` da lista fechada de recusa |
| `p_status` vazio | `True` | `status_pkg=""` |
| ERRO_ORACLE antes do execute | `False` | `erro_connect_kill` ou `erro_var_kill` |
| ERRO_ORACLE depois do execute | `True` | `erro_kill` |
| `ENCERRADA` sem a flag (§2 do Gemini) | `True` | monkeypatch de `executar_kill_verificado` que devolve `json.dumps({"status": "ok", "status_banco": "ENCERRADA"})` |
| REJEITADO | `False` | |
| INTERROMPIDO | `True` | `_sonda_que_levanta_na_2a(KeyboardInterrupt())`, como em `test_item1_intencao.py:703-719` |
| NAO_CONCLUIDA | `True` | INTENCAO antiga, sem RESULTADO, e depois `reconciliar_intencoes_orfas` |

**Asserções.** Use `is True` e `is False` sobre a linha lida do JSONL, nunca `==`, porque `1 == True`.

**Mutantes.**
- R-a1 tira o campo da chamada `:1845`.
- R-a2 grava `False` fixo em `:1845`.
- R-a3 troca `True` por `False` em `:1798`.
- R-a4 troca `True` por `False` em `:1445`.
- R-a7 troca `False` por `True` em `:1628`.

## 2. Ponto 2: INTENCAO sem o campo, e o campo proibido nela

**Regra.** A linha INTENCAO não tem a chave, nem com `null`. Como o parâmetro não tem default (ponto 3), a chamada da INTENCAO em `:1704` passa `resultado_desconhecido=None` explicitamente. Qualquer valor diferente de `None` numa INTENCAO dá `ValueError`.

**Falha fechada.** Se alguém passar um bool em `:1704`, o `ValueError` cai no `except` de `:1716`, que leva a FALHA_LOG_APROVACAO, sem conta KILL.

**Testes.**
- No fluxo ENCERRADA: `"resultado_desconhecido" not in intencao`.
- Direto: INTENCAO com `True`, `False` ou `0` dá `ValueError`, e o arquivo não é criado.

**Mutantes complementares** (decisão minha; o 8.12.2 não tinha mutante para este ponto):
- R-a11: a condição `elif resultado_desconhecido is not None:` vira `elif False:`.
- R-a12: a chave entra em toda fase, sem o `if fase == "RESULTADO"`.

## 3. Ponto 3: obrigatoriedade (opção (a), decidida pelo responsável)

**Assinaturas.** Nas duas funções, `resultado_desconhecido: Optional[bool]` entra depois de `id_intervencao`, no bloco keyword-only e **sem default**. `registrar_log_aprovacao_kill` repassa o valor a `_montar` em `:1374-1377`.

**Validação.** Fica em `_montar`, depois da checagem da INTENCAO (`:1315-1316`) e antes do `return`. Por isso vale também para o reconciliador, e roda antes de qualquer E/S.

```python
if fase == "RESULTADO":
    if not isinstance(resultado_desconhecido, bool):
        raise ValueError("RESULTADO exige resultado_desconhecido booleano (True ou False).")
elif resultado_desconhecido is not None:
    raise ValueError("INTENCAO não leva resultado_desconhecido (passe None).")
```

**Consequências.**
- "Faltar" se divide em dois casos:
  - argumento omitido: `TypeError`, do Python;
  - `None` numa RESULTADO: `ValueError`.
- Valores rejeitados numa RESULTADO: `None`, `0`, `1`, `"False"` e `""`.

**Chamadas de teste que ganham o argumento.** É mudança de chamada; nenhuma asserção muda. São **21** chamadas, e não 13: o 8.12.2 contou só as de `fase="RESULTADO"`, mas sem default **toda** chamada precisa do argumento. A mudança fica declarada aqui para a parada do 8.12.5 não disparar.

| Arquivo:linha | Fase | Argumento | Por quê |
|---|---|---|---|
| `test_item1_intencao.py:376` | RESULTADO | `False` | |
| `:388` (sem `fase`) | — | `False` | o `TypeError` continua vindo só da falta de `fase` |
| `:390` (sem id) | RESULTADO | `False` | o `TypeError` continua vindo só da falta do id |
| `:392` | `"X"` | `None` | isola a causa |
| `:393`, `:394` | INTENCAO | `None` | isola a causa (decisão; `resultado_banco`) |
| `:395`, `:396`, `:397`, `:398` | RESULTADO | `False` | isola a causa (id; decisão) |
| `:880`, `:1069`, `:1096` | RESULTADO | `False` | |
| `:1033`, `:1041`, `:1054` | INTENCAO | `None` | sem o argumento, `:1033` levantaria `TypeError` em vez de `LockLogAprovacaoIndisponivel` |
| `test_oracle_kill.py:213`, `:231`, `:262`, `:697` | RESULTADO | `False` | |
| `test_oracle_kill.py:1190` | RECUSA_PRE_HITL | `None` | o `ValueError` continua vindo da fase |

Nos casos de `:391-401`, o valor vai em cada dict, e não no `base`. Assim nenhum caso passa a falhar pela validação nova em vez da causa original.

**Testes novos.**
1. **Assinatura** (no molde de `test_oracle_kill.py:1554`): nas duas funções, `kind is KEYWORD_ONLY` e `default is inspect.Parameter.empty`. Uma RESULTADO sem o argumento dá `TypeError`.
2. **Validação**: RESULTADO com `None`, `0`, `1`, `"False"` ou `""` dá `ValueError`, e `not log.exists()`. Vale também para `_montar` chamada direto.
3. **AST** (8.12.0.2):
   - percorre `app.py` e `src/**/*.py`;
   - para cada `ast.Call` cujo `func` seja `Name` ou `Attribute` com nome `registrar_log_aprovacao_kill` ou `_montar_registro_aprovacao_kill`, exige um `keyword` com `arg == "resultado_desconhecido"`;
   - recusa `**kwargs`: `keyword.arg is None` reprova;
   - contra teste vazio, exige exatamente **6** chamadas, todas em `oracle_dba.py`, e 0 nos demais arquivos. Uma chamada nova em código do §2 obriga a revisar o teste, o que é intencional.

**Mutantes.**
- R-a8: `if not isinstance(resultado_desconhecido, bool):` vira `if False:`. Morre no teste 2.
- R-a9: tira `resultado_desconhecido=True,` da chamada `:1798` e roda o `controle_mutacao` com `--teste` restrito ao nodeid do teste AST. Esse teste só lê o fonte e não executa a chamada, então o `TypeError` não acontece e quem mata o mutante é a AST.
  - O "default posto só no mutante" do 8.12.2 exigiria duas trocas não contíguas (assinatura e chamada), e `aplicar_troca` aceita só uma (`controle_mutacao.py:101-102`).
  - A forma com `--teste` restrito prova a mesma coisa. É a forma decidida.
- R-a15 (complementar): `default = True` na assinatura de `registrar_log_aprovacao_kill`. Morre no teste 1 e prova o "sem default" do responsável.

## 4. Ponto 4: registros de recuperação

**Regra.** Cada `registro=` de recuperação leva o mesmo valor passado à gravação que falhou.

| Local | O que entra | Valor |
|---|---|---|
| `:1648-1657` (`logger.error`, recusa humana) | `"resultado_desconhecido": False` | `False` |
| `:1786-1795` (`registro_interrompido`, serializado em `:1817`) | `"resultado_desconhecido": True` | `True` |
| `:1864-1874` (`logger.critical`, RESULTADO principal) | `"resultado_desconhecido": resultado_desconhecido` | a variável de `:1839`, a mesma da chamada `:1845` |

**Testes.** Usam o meio já existente, `_instalar_open_proxy(..., falhar_na_gravacao=2)` (`test_item1_intencao.py:727`, `:747`, `:771`), em testes novos. Os existentes não são tocados.
- `:1863`: dois casos com o valor certo. ENCERRADA dá `serializado["resultado_desconhecido"] is False`; `status_pkg=""` dá `is True`.
- `:1647`: REJEITADO e TIMEOUT dão `is False`.
- `:1786`: INTERROMPIDO com a segunda gravação falhando dá `is True`.

**Mutantes.**
- R-a10: tira a chave do dict de `:1864-1874`.
- Complementares:
  - R-a10b: `False` fixo nesse mesmo dict;
  - R-a13: tira a chave de `registro_interrompido`;
  - R-a14: tira a chave do dict de `:1648-1657`.

## 5. Ponto 5: legado no reconciliador

**Regra.** `reconciliar_intencoes_orfas` (`:1406-1457`) **não lê** o campo, e o código de leitura (`:1411-1429`) fica sem mudança. Uma RESULTADO sem o campo, ou com valor não booleano, continua entrando em `com_resultado`, não conta em `linhas_invalidas` e não gera anexo.

**Teste.** Parametrizado no valor do campo na RESULTADO antiga: ausente, `None`, `"talvez"`, `1`, `True` e `False`. Usa uma INTENCAO com mais que `RECONCILIACAO_IDADE_MINIMA_SEGUNDOS` e a RESULTADO com o mesmo id, e confere:
- `reconciliadas == []`;
- `linhas_invalidas == 0`;
- os bytes do arquivo iguais antes e depois.

**Mutantes.**
- R-a5: `elif reg.get("fase") == "RESULTADO":` vira `... == "RESULTADO" and "resultado_desconhecido" in reg:`. Morre no caso "ausente". A variante com `isinstance(..., bool)` morre nos casos não booleanos.
- R-a6: a RESULTADO sem o campo passa a somar `linhas_invalidas` e a dar `continue`.

## 6. Ponto 6: RECUSA_PRE_HITL

**Regra.** Fica inalterada. `_montar_registro_recusa_pre_hitl` (`:1331-1346`) não recebe o campo.

**Teste.** O existente, `test_oracle_kill.py:1159` (`set(reg) == _CHAVES_RECUSA_PRE_HITL`), já mata um mutante que acrescente a chave. Não há teste novo.

## 7. Ataque

- **TOCTOU e concorrência (CLI × Web × abas).** O campo é calculado localmente, depois do retorno do `execute`, e não muda os locks nem a ordem INTENCAO, execução, RESULTADO.
  - O reconciliador continua sob os dois locks (`:1406-1407`).
  - Uma RESULTADO real que chegue depois de uma NAO_CONCLUIDA (`True`) prevalece, comportamento já documentado em `:1392-1393`.
  - O residual de uma INTENCAO em curso há mais que a idade mínima ser reconciliada já existia. O `True` é o valor correto para ela.
- **Exceção no meio do fluxo.**
  - Um `ValueError` da validação nova em `:1845` cai em `:1857`: `logger.critical` mais e-mail com o marcador. O kill já ocorreu e o registro de recuperação o preserva.
  - Em `:1628`, cai em `logger.error`.
  - Em `:1704`, leva à FALHA_LOG_APROVACAO, sem KILL. **Falha fechada.**
  - Em `:1798`, `gravado=False` e o CRITICAL com o registro.
- **Resultado desconhecido depois do execute.** A RESULTADO passa a dizer explicitamente `True`. É o ganho do R-a: o auditor não depende do e-mail nem do log da aplicação para saber que precisa conferir em `OPS_KILL_AUDIT`.
- **Ambiente.** O R-a não lê variável de ambiente, não toca `.env` nem `ORACLE_SANDBOX`, e não muda `db/` nem `registry/`. Também não muda o que a conta KILL executa.
- **Unicidade dos `de` (L3, L16).** O trecho `resultado_desconhecido=resultado_desconhecido,` aparecerá em `:1845` e em `:1896`. O K6.2 precisa ancorar cada `de` com a linha vizinha, por exemplo `id_intervencao=id_intervencao,` junto com o argumento na indentação daquela chamada. Também deve conferir que `aplicar_troca` encontra exatamente 1 ocorrência (o arquivo está em CRLF).

## 8. Controle negativo (L17)

Em `049ed79`/`3b0c08d`, os testes novos têm de falhar:
- campo ausente na RESULTADO;
- assinatura sem o parâmetro;
- AST sem nenhum `keyword`;
- recuperação sem a chave.

A exceção é o teste de legado (ponto 5), que deve **passar** na base porque fixa o comportamento atual. Ele vale pelos mutantes R-a5 e R-a6, e não pelo controle negativo, o que deve ficar dito no relatório do K6.2.

## 9. Resumo dos mutantes (todos DETECTADA)

| Conjunto | Mutantes |
|---|---|
| Do plano | R-a1 a R-a10 |
| Complementares, decididos aqui | R-a10b, R-a11, R-a12, R-a13, R-a14, R-a15 |

São 16 no total. R-a9 roda só contra o nodeid do teste AST.

## 10. PENDENTE APROVAÇÃO

Nenhum item. Não há mudança em `db/ops_kill.sql`, em privilégios, em hash do `registry/` nem na lista de usuários protegidos. As 8 chamadas de teste além das 13 do plano são consequência direta da opção (a), já aprovada, e ficam declaradas no ponto 3.
