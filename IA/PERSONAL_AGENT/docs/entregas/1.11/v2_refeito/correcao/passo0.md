# PASSO 0 da correção do item 6 v2: reprodução independente da revisão do Gemini (só leitura)

- Quem: sessão principal, claude-opus-5-5. 2026-11-23.
- Base: `item6/v2` em `2210b31`. Foi feita uma cópia `git archive 2210b31 IA/PERSONAL_AGENT` no scratchpad, sem `.env`, e os `ORACLE_*`, `EMAIL_*`, `GEMINI_*` e `AGENTDBA_*` foram tirados do ambiente do filho. Sem `ORACLE_SANDBOX` e sem Oracle. O alvo na cópia está em CRLF (2063/2063), e cada `de` foi convertido para CRLF e conferido com 1 ocorrência (L46).
- Evidências em `passo0/`: `sondas_p0.txt`, `sonda_p0.py.txt` (renomeado de `test_sonda_p0.py`: o pytest.ini não tem testpaths e o coletava), `rodar_mutantes_p0.py`, `tabela.txt` e uma saída do pytest por mutante.

## Sondas (fluxo `conduzir_kill_hitl` com `_OracleFake`)

| Achado | Cenário | Observado | Reproduziu? |
|---|---|---|---|
| A1 | `p_status="ERRO_ORACLE"` | 1 execute KILL; `resultado_desconhecido=False`; e-mail "NÃO executada (status ERRO_ORACLE)"; `resultado_tool` com "executado para" | sim |
| A1 | `p_status=""` e `None` | `resultado_banco="DESCONHECIDO"`, `resultado_desconhecido=False`, e-mail "NÃO executada" | sim |
| A1 (extra) | `p_status="XYZ_DESCONHECIDO"` | o mesmo que acima: o código fora da lista conhecida cai em "NÃO executada" | sim, amplia o A1 |
| A3 | `str(db_err)` levanta no `except oracledb.Error` | 1 execute KILL; `ERRO_INTERNO`; `resultado_desconhecido=False`; e-mail "NÃO executada" | sim |
| A3 | `matar_sessao_oracle` devolve texto que não é JSON | `DESCONHECIDO`, `resultado_desconhecido=False`, e-mail "NÃO executada" | sim |
| A9 | D8 (`getvalue` levanta `RuntimeError`) | assunto "resultado desconhecido", corpo com "erro do Oracle" | sim |
| A5 (:935) | D8 | `resultado_tool` traz o DSN fictício `host-teste:1521/TESTE` | sim |
| A6 | chamada no formato dos 4 `sandbox_only` | `TypeError: ... missing 2 required keyword-only arguments` | sim |
| A10 | `program=""`, `machine=""` | aceitos (`[]`); `hash("") != hash(None)` | sim |

## Mutantes (pytest de `tests/test_item1_intencao.py` e `tests/test_oracle_kill.py`)

m0, sem mutação: `126 passed, 6 skipped` (igual ao do Gemini).

| Mutante | Origem | Resultado |
|---|---|---|
| M_RHS_SWAP_PROG_MACH | A2/A7 | SOBREVIVEU (126 passed) |
| M_RHS_SWAP_SID_SERIAL | A2/A7 | SOBREVIVEU |
| M_STATUS_VAR_SIZE_8 | A4/A7 | SOBREVIVEU |
| M_LOGON_COMENTARIO_NO_SELECT | A4/A7 | SOBREVIVEU |
| M_EXEC_INICIADO_ANTES_VAR | A7 | SOBREVIVEU |
| M_EXEC_KILL_GET_DEFAULT | A7 | SOBREVIVEU |
| M_FALLBACK_V1_NO_NAO_ENCONTRADO | A7 | SOBREVIVEU |
| M_LIMITE_GE_128 | A7 | SOBREVIVEU |
| X_REGEX_ID_0_9A_Z (`[0-9a-z]{32}`) | A7, "HIPÓTESE não executada" | SOBREVIVEU: a hipótese se confirma |
| X_SERIAL_FORA_ROW2 (`row[2]` → `row[1]`) | A4.3, "mover serial# fora do índice row[2]" | **MORTO** (2 failed): **não reproduzido** nesta forma |
| X_SELECT_SID_SERIAL_TROCADOS (sid e serial# trocados no texto do SELECT DIAG, `row[2]` mantido; 2026-11-24, pedido do responsável) | A4.3, variante | **SOBREVIVEU** (126 passed): **A4.3 reproduzido**; coberto pela `description` derivada do SELECT (§8 do plano) |

Os 8 mutantes do A7 (que incluem os 2 do A2 e os 2 do A4) se reproduzem.

**Atualização de 2026-11-24:** a variante X_SELECT_SID_SERIAL_TROCADOS sobreviveu, e o A4.3 fica **reproduzido** nessa forma. O parágrafo abaixo vale só para a forma `row[2]` → `row[1]`.

**Não reproduzido (reportado, não corrigido):** a frase do A4.3 "mover serial# fora do índice row[2] … passa em T8 e nos 126 testes". Na forma `row[2]` → `row[1]` o mutante morre: o hash muda (ALVO_ALTERADO) e um teste de usuário protegido falha. A outra forma possível, reordenar as colunas só no texto do SELECT, é cega por construção, porque a `description` e a linha do fake são fixas. É o mesmo defeito do A4.3 (`description` fixa) e entra na correção do fake. Não há mutante novo a registrar para ela além do M_LOGON_COMENTARIO_NO_SELECT.

**Contagem "10 do Gemini":** pela leitura da sessão principal, são os 8 do A7 mais os 2 extras desta tabela. O X_SERIAL_FORA_ROW2 já morre hoje e fica no conjunto de regressão como controle.
