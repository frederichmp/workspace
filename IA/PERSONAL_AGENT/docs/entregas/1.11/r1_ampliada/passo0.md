# P0 da R1 ampliada: reprodução de V1 a V9 (só leitura)

- **Plano:** `docs/plans/1.11-R1-ampliada.md` §4, passo P0.
- **Base:** branch `r1-ampliada`, HEAD `36746cf` (código igual a `cdc8f6d`).
- **Autor:** sessão principal, claude-opus-5-5.
- **Meio:**
  - a sonda `passo0/sonda_r1.py.txt` (rodada como `.py` fora de `tests/`, L49) troca `oracledb.connect` por fakes e usa credenciais fictícias;
  - o DSN sentinela é `host-sentinela-r1:1599/SVC_SENTINELA`;
  - o `ORACLE_SANDBOX` não é tocado, e o `.env` não é lido.
- **Saída:** `passo0/sondas.txt`, com uma linha por caso e as sentinelas achadas no `resultado_tool`. Deu 30 passed.
- **Fora da evidência:** a saída completa do pytest, porque traz o caminho do usuário nos avisos (L57).

## 1. Reproduzidos pela sonda

| V | Dado | Casos em que apareceu (`sondas.txt`) | Reproduzido |
|---|---|---|---|
| V1 | DSN completo | `coletar_sessoes_ativas` e `coletar_top_sql` em todos os ramos, inclusive o de sucesso; `coletar_plano_execucao` em ERRO_CONFIG e rede; `matar_sessao_oracle` em ERRO_CONFIG, rede, ERRO_ORACLE antes e depois do execute; fluxo HITL com ERRO_ORACLE depois do execute | sim |
| V2 | `host:porta` e erro de rede | ramo de rede das 3 ferramentas de diagnóstico e de `matar_sessao_oracle` (`erro_rede` cru); pré-consulta (`preparar`, rede: `host:porta` na mensagem) | sim |
| V3 | texto cru de exceção | ERRO_ORACLE e exceção nas 3 ferramentas de diagnóstico, na pré-consulta e no kill antes e depois do execute (o texto `ORA-99999 ...` vai ao LLM) | sim |
| V4 | usuário protegido | pré-consulta com `STARTUPADMIN`: o nome está na mensagem da recusa | sim |
| V5 | aprovador | REJEITADO: o identificador do aprovador está no `resultado_tool` | sim |
| V6 | nome do PKG | mensagem de ENCERRADA (no `matar_sessao_oracle` e no fluxo) e descrição da ferramenta em `oracle_tools_schema` | sim |
| V7 | `hash_aprovado` e `hash_atual` | fluxo com ALVO_ALTERADO | sim |
| V8 | dado de diagnóstico | sucesso das sessões (username, `program`, `machine`), sucesso do top SQL (`sql_text_curto`), sucesso do plano (literal da *Predicate Information*) | sim |

Sem achado:
- o ramo D8 do kill, já corrigido no item 6 (`:987`);
- o plano no sucesso não traz o DSN, só o literal (V8).

## 2. Conferidos no código (a sonda não cobre)

| V | Evidência |
|---|---|
| V3 nas interfaces | `app.py:394-396` e `src/main.py:416-420`: a exceção genérica de ferramenta vira `{"erro_execucao": str(e)}` no `role: "tool"` |
| V9 | `analisar_log_complexo` está em `TODAS_FERRAMENTAS` (`app.py:170`, enviado em `:265`) e em `todas_ferramentas` (`src/main.py:189`, enviado em `:323`). `gemini_router.py:27` manda o `dados_brutos` ao Gemini. |
| **V9, agravante não listado no plano** | O prompt de sistema manda o LLM enviar **imediatamente** todo plano `DBMS_XPLAN` ao `analisar_log_complexo`, ou seja, à nuvem, mesmo com o coordenador local (`app.py:181`, `src/main.py:201`: "REGRA DE OURO"). A decisão 5.2.2 (tirar a ferramenta da lista) precisa tirar também essa regra. |
| V1 no `executor.py` | `"instancia": dsn` em `executor.py:810, 848, 867, 886, 908, 927`. Nenhuma das interfaces importa o executor, o que confirma "ainda não ligado ao LLM" (A5). |
| Coordenador | Ollama local se a porta 11434 responde; senão, o Gemini (`app.py:198-214`, `src/main.py:162-180`) |

## 3. Para o C1 (decisão do `seguranca`)

- **Falha fechada do V8 (5.2.1):** com que sinal o código sabe que o coordenador é a nuvem.
  - `obter_cliente_llm` devolve `ollama_ativo` na Web; `_inicializar_cliente_coordenador` devolve o par cliente e modelo na CLI.
  - Também falta decidir se a recusa é por retirar as ferramentas Oracle da lista ou por um retorno fixo.
- **Remoção do `analisar_log_complexo` e da "REGRA DE OURO" (5.2.2):** como fazer, nas duas interfaces.
- **`os_tools_schema`:** está na mesma lista de ferramentas e fora do A5. Não foi sondado; o C1 diz se entra.
- **Texto substituto por ponto:** o código do erro, a recusa genérica de protegido e a mensagem de executado sem o PKG. O log local continua com o detalhe.
