# K6.5: conferência do diff `3b0c08d..73e9484` (R-a e N1-N8)

- Tarefa: 1.11-V2-item6, passo K6.5 (plano §8.12). Autor: subagente `seguranca`, modelo `claude-opus-5-5`.
- Escopo: só leitura. Sem Oracle e sem pytest. Li o diff dos 5 commits, a `k6/decisao_ra.md`, os relatórios `k6/*.md` e os trechos citados.
- Veredito: **NÃO CONFORME** por um ponto só, o N7 no T3 (§3.1). A correção é de uma linha e não pede decisão do responsável. Todo o resto está CONFORME. Há uma ressalva: o K6.4 de regressão ainda não tinha terminado quando conferi (§5).

## 0. Fatos verificados agora

| Fato | Onde |
|---|---|
| 5 commits, 4 arquivos: `oracle_dba.py` +45, `fakes_oracle.py` +11/-2, `test_item1_intencao.py` +307, `test_oracle_kill.py` +137 | `git diff --stat` |
| `registry/` e `db/` sem mudança | `git diff --stat 3b0c08d..73e9484 -- registry/ db/` vazio |
| Só o commit `7d76b60` (R-a) toca produção, e ele está marcado "PENDENTE APROVAÇÃO" | `git log` |
| Validação e chave condicionada à fase | `src/tools/oracle_dba.py:1323-1337` |
| Assinaturas keyword-only sem default | `oracle_dba.py:1307`, `:1379` |
| Repasse de `registrar` para `_montar` | `oracle_dba.py:1397` |
| Valores das chamadas: reconciliador `True`, recusa humana `False`, INTENCAO `None`, INTERROMPIDO `True`, principal = variável | `oracle_dba.py:1476`, `:1661`, `:1739`, `:1835`, `:1883` |
| Valores dos registros de recuperação: recusa `False`, INTERROMPIDO `True`, principal = variável | `oracle_dba.py:1677`, `:1817`, `:1898` |
| A fórmula do valor principal não mudou | `oracle_dba.py:1866` |
| O bloco do KILL não tem literal de string, então a limpeza de comentários não pode cortar código real | `oracle_dba.py:889-903` |
| Controle negativo do R-a em `3b0c08d`: 28 falhas e 6 aprovados. Os 6 aprovados são o teste de legado, como previsto na `decisao_ra.md` §8 | `k6/k62_ra_controle_negativo_3b0c08d.txt` |
| Mutantes: R-a 16/16 mais R-a5b; R-a9 só contra a AST; N1-N8 todos DETECTADA | `mut_ra.md`, `mut_ra9.md`, `mut_c4..c7_*.md` |
| P0: os 8 N sobrevivem na base | `passo0_n_prod.md`, `passo0_n_testes.md` |
| Contagem de testes: 34 (R-a) + 2 (N2, N3) + 10 (N5, N6) + 0 (N7) + 10 (N4, N8) = 56, e 1378 + 56 = 1434 | conta feita sobre o diff |

## 1. R-a contra a `decisao_ra.md`, ponto a ponto

| Ponto | Regra | Diff | Veredito |
|---|---|---|---|
| 1 | O bool vai em toda RESULTADO, com os 4 valores | `:1476`, `:1661`, `:1835` e `:1883` batem com a tabela do §1 da decisão | CONFORME |
| 2 | A INTENCAO não leva a chave e exige `None` | `:1326-1327`, `:1336-1337`, `:1739` | CONFORME |
| 3 | Keyword-only sem default; `ValueError` antes de qualquer E/S; AST com 6 chamadas | `:1307`, `:1379`, `:1323-1327`. O teste AST está em `test_item1_intencao.py` (`_chamadas_de_registro_na_producao`) | CONFORME |
| 4 | Os 3 registros de recuperação levam o campo | `:1677`, `:1817`, `:1898` | CONFORME |
| 5 | O reconciliador não lê o campo | Única mudança no reconciliador: `:1476`. A leitura ficou intacta | CONFORME |
| 6 | RECUSA_PRE_HITL inalterada | `_montar_registro_recusa_pre_hitl` fora do diff | CONFORME |

**Chamadas de teste que ganharam o argumento.** São 21: 16 em `test_item1_intencao.py` e 5 em `test_oracle_kill.py`. Todas são só mudança de chamada, e cada valor bate com a tabela do §3 da decisão (`:388`/`:390` com `False`; `"X"`, INTENCAO e `:1190` com `None`). Nenhuma asserção foi tocada.

**Testes novos do R-a.** São 34 e cobrem toda a lista do §8.12.2.
- Os valores lidos do JSONL usam `is True` ou `is False`.
- A AST percorre `app.py` e `src/**`, aceita `Name` e `Attribute`, recusa `**kwargs` e fixa a contagem em 6.

**Correção da minha própria decisão.** Na `decisao_ra.md` §1, o caso ALVO_DIVERGENTE aparece como "a segunda linha DIAG diverge". Isso está inexato: na v2, o ALVO_DIVERGENTE só vem do PKG (`oracle_dba.py:925`). A divergência local é ALVO_ALTERADO (`:1085`, valores `False` em `:1107-1164`).
- O teste usou `status_pkg="ALVO_DIVERGENTE"`, declarado no id `alvo_divergente_pkg`. Isso está correto.
- Fica descoberto o campo do JSONL no caso ALVO_ALTERADO. É uma recomendação, e não bloqueia o veredito: o valor vem da mesma fórmula de `:1866`, já coberta pelos R-a1 e R-a2.

## 2. N1-N8 contra o §8.12.3

| N | Classe da mudança | Onde | Veredito |
|---|---|---|---|
| N1 | Asserção acrescentada: `"falha simulada"` entra em `proibidos_extra`. A lista só cresce, e a mudança está declarada no comentário e no plano | `test_oracle_kill.py:1067-1073` | CONFORME |
| N2 | Teste novo. O alvo vem de monkeypatch de `consultar_alvo_sessao_diag`, e o meio está dito na docstring, como o plano exige | `test_oracle_kill.py` (`test_k6_n2_...`) | CONFORME |
| N3 | Teste novo. Usa `caminho_log` omitido e `isolar_log_aprovacao`, e confere `set(reg) == _CHAVES_RECUSA_PRE_HITL` | `test_k6_n3_...` | CONFORME |
| N4 | Testes novos (5 casos de skip e 1 que segue). O monkeypatch é só de `OPS_KILL_PKG_VERSAO`. O gate não lê o `ORACLE_SANDBOX` | `test_oracle_kill.py:1821-1824` | CONFORME |
| N5 | Teste novo. A mensagem conferida é mais estrita que a do plano (inclui o `;`) | `test_k6_n5_...` | CONFORME |
| N6 | Teste novo com 9 casos. `test_kill_param_invalido_sem_conexao` ficou fora do diff | `test_k6_n6_...` | CONFORME |
| N7 | Mudança de fake e de asserção | §3 | **NÃO CONFORME** no T3; CONFORME nos 3 pontos de `test_item1_intencao.py` |
| N8 | Teste novo de AST: o valor não pode ser `ast.Constant` | `test_k6_n8_...` | CONFORME |

## 3. N7: julgamento

**Fake.** `_sem_comentarios_sql` passa a remover `/* ... */` antes de `--` (`tests/fakes_oracle.py:89-97`). O efeito chega a dois lugares: a conferência de placeholders contra binds (`:118`, `:132`) e `_colunas_do_select` (`:104`).
- Isso fica mais fiel ao Oracle e ao parser do driver, que também ignoram comentários. O mutante N7 (5 formais dentro de `/* */`) passa a dar DPY-4008 no fake, com 62 falhas.
- A regex não guloso termina no primeiro `*/`, como o Oracle, que não aninha comentários.
- Residual: um `/*` sem fechamento não é removido, e o Oracle o recusaria. Não vale a pena cobrir agora.

**As asserções de pares, nos dois sentidos.**
- (a) Um par real comentado deixa de contar, e a asserção falha. Antes ela passava sem ver nada; esse é o N7.
- (b) Um par que só existe dentro de um comentário também deixa de contar, e a asserção passa. Antes ela falhava. Nesse sentido ela afrouxou.

**Nos 3 pontos de `test_item1_intencao.py` (`:228-229`, `:609-610`, `:655-656`).** A linha de formais `re.findall(r"\b(p_\w+)\s*=>", sql)` continua sobre o **SQL cru**. Só os pares passaram a usar o SQL limpo.
- A combinação formais crus mais pares limpos rejeita o (a) e o (b).
- O ponto, portanto, ficou estritamente mais forte que na base. **CONFORME.**

**3.1 No T3 (`test_oracle_kill.py:858-860`).** A linha de **formais** também passou para `sql_efetivo` (`:859`).
- O plano autoriza só os 4 pontos do `REGEX_PAR_FORMAL_PLACEHOLDER`, e no T3 esse ponto é o par em `:854` da base. O commit `a3809ef` declara só os pares.
- A linha de formais da base (`:853`) não estava no escopo. Ela afrouxou no sentido (b) e não foi declarada.
- Na suíte inteira não se perde detecção: os 3 pontos de `test_item1_intencao.py` ainda conferem os formais sobre o SQL cru. No T3 isolado, porém, a perda existe.
- Isso dispara a parada do 8.12.5 ("expectativa alterada além das declaradas") e o critério "nenhuma asserção enfraquecida sem declaração". **NÃO CONFORME.**

**Mudança mínima.** Em `tests/test_oracle_kill.py:859`, a linha volta a usar o SQL cru, e a linha `:860` continua sobre `sql_efetivo`:

```python
assert re.findall(r"\b(p_\w+)\s*=>", sql) == ORDEM_V2
```

Com isso, o T3 fica no mesmo desenho dos outros 3 pontos e estritamente mais forte que a base nos dois sentidos. A suíte continua verde, porque a base passava com o mesmo SQL de produção.

**Teste que prova, com controle negativo** (a sessão principal roda, com `tools/controle_mutacao.py`):
- **Mutante:** `M_T3_COMENTARIO_COM_FORMAL`. Uma única troca em `src/tools/oracle_dba.py`, que acrescenta logo depois da linha `p_status => :p_status` uma linha de comentário `-- p_extra => :p_extra`.
  - O `de` precisa ser único no arquivo, que está em CRLF (L3, L16).
  - O fake remove o `--` dos placeholders, então não há DPY-4008. Quem mata o mutante é a linha de formais.
- **Rodada:** `--teste tests/test_oracle_kill.py`. Para isolar o T3, use o mesmo meio do R-a9 (nodeid restrito).
- **Controle negativo, em `73e9484`:** o mutante PASSA (o T3 está cego).
- **Depois da correção:** o mutante dá DETECTADA.
- **Conferência extra:** o `N7_BLOCO_COMENTARIO_PLSQL_V1` continua DETECTADA. A linha de pares, limpa, segue matando esse mutante.

**Alternativa.** Manter `:859` como está e declarar a mudança no log. Como é uma parada do 8.12.5, essa opção é do responsável. Recomendo a correção de uma linha.

## 4. Greps 3.x do §5 sobre as 465 linhas acrescentadas no diff

| Grep | Resultado |
|---|---|
| 3.1 `ORACLE_USER\b` | 0 |
| 3.2 `alter system`/`alter session` | 0 |
| 3.3 `override=True` | 0 |
| 3.4 `load_dotenv(` | 0 |
| 3.5 sandbox ligado | 0 |
| 3.6 credencial em `print` ou em log | 0 |
| 3.7 `registry/` e `db/` | vazio |
| 3.8 `.env` versionado | 0 |

`setenv` e `delenv` aparecem só em `OPS_KILL_PKG_VERSAO`. O `ORACLE_SANDBOX` aparece só em comentário e em docstring.

**Linhas removidas nos testes.** Foram 6, todas acima: os 4 pontos de pares, os formais do T3 e a lista do d8. Nenhuma outra asserção saiu.

## 5. Ataque e residuais

- **TOCTOU, concorrência e resultado desconhecido.** O R-a não muda locks, ordem nem a conta KILL. O valor principal é sempre bool (`not (...)` em `:1866`), então a validação nova não dispara no fluxo real. Uma regressão futura cairia no `except` de `:1884` (logger.critical, e o kill não é refeito).
- **Ambiente.** Nada lê ambiente novo. O `.env` não é tocado.
- **Residuais aceitos.** Não pedem decisão: ficam dentro do que o plano pediu.
  - A AST do R-a não vê import com alias nem `getattr`. A contagem fixa em 6 atenua.
  - O N8 não vê um `Name` ligado a `None`, porque o plano pede só `ast.Constant`.
  - O `/*` sem fechamento no fake (§3).
- **Recomendação, sem bloquear.** Acrescentar o caso `alvo_alterado_local` em `CASOS_RA_FLUXO`: a segunda linha DIAG diverge, com `resultado_banco == "ALVO_ALTERADO"` e `is False` (§1).
- **K6.4 de regressão incompleto quando conferi.** A pasta `k6/regressao/` tinha `resumo.txt` só com o cabeçalho "inicio 17:24:11" e `r_m1_m16_run.txt` vazio, conferidos às 17:27. O 0 sobrevivente dos conjuntos m1-m16, Gemini, m17-m31 e `mecanico` não está verificado por mim. A mudança do fake (`_colunas_do_select`) pode, em tese, alterar a detecção de mutantes do SELECT. O K6.4 precisa fechar com 0 sobreviventes antes do K6.6.

## 6. PENDENTE APROVAÇÃO

Nenhum item novo. O commit `7d76b60` já está marcado PENDENTE APROVAÇÃO, por ser código do §2. Não há mudança em `db/`, `registry/`, privilégios nem na lista de protegidos. Só a alternativa do §3.1 (aceitar `:859` e declarar) seria do responsável.
