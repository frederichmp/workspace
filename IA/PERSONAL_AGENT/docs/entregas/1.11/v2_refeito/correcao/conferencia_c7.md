# Conferência C7: 1.11-V2-item6, correção depois da revisão do Gemini (plano §8.4; decisões §8.10)

- Quem: `seguranca`, claude-opus-5-5, effort high. 2026-11-24. Só leitura: sem Oracle, sem pytest, sem `.env`.
- Diff conferido: `git diff f9482c4 bb9f74b` (482feb4, a7cd549, 76232b2, 240fb00, bb9f74b). HEAD = `bb9f74b` (`git rev-parse`). `src/`, `app.py` e `tests/` sem diff no working tree em relação a `bb9f74b`.
- Referência: `correcao/decisao_c1.md` (pontos 1 a 8, P1 a P4 aceitos no §8.10.7) e a triagem do §8.2.
- Modelo de ameaça: defeito ou acidente (L40). Rodada estreita: só este diff.

## Veredito: CONFORME

Os 8 pontos da decisão e os achados A1 a A10 (no escopo do §8.2) estão implementados como decididos. Não há falha aberta e não há asserção enfraquecida sem declaração. As duas mudanças de expectativa são as declaradas, e as duas aparecem no corpo dos commits a7cd549 e 240fb00. Os achados abaixo são observações e residuais: nenhum bloqueia o C8.

## 1. Pontos da decisão × código (linhas de `bb9f74b`, conferidas agora)

| Ponto | Onde | Veredito |
|---|---|---|
| 1. `RECUSAS_PKG_SEM_KILL` (6 códigos, lista fechada) | `oracle_dba.py:84-90` | conforme; o texto é o da decisão |
| 2a. Classificação na ordem EXECUTADO, DIVERGENTE, RECUSAS, resto=desconhecido; `""`/`None` viram `DESCONHECIDO` | `oracle_dba.py:914-950` | conforme; "executado para" só em `:919-924` |
| 2a. Bool literal nos 4 retornos antes do `try` e `execute_iniciado` nos 2 `except` | `:798`, `:818`, `:837`, `:854`; `:966`, `:986` | conforme; o AST do teste exige >= 7 `json.dumps`, todos com a chave |
| 2b. Constantes `MENSAGEM_DESFECHO_NAO_CONFIRMADO`, `MENSAGEM_RECUSA_PKG`, `STATUS_PKG_VAZIO` | `oracle_dba.py:54-57` | conforme, texto literal |
| 2c. `False` nas 4 recusas de `executar_kill_verificado` | diff `+1107`, `+1127`, `+1148`, `+1164` | conforme |
| 2d. ERRO_INTERNO com desconhecido True; parse com `isinstance(dict)`; sem eco do texto; `is False` como única saída; `executado` exige não desconhecido | `oracle_dba.py:1771-1784`, `:1823-1840` | conforme |
| 2d. O LLM recebe o valor efetivo | `oracle_dba.py:1910` | conforme |
| 2e. `resultado_desconhecido` keyword-only e sem default; corpo sem "erro do Oracle"; docstring | `oracle_dba.py:1474-1500`; único chamador por nome em `:1888-1897` | conforme |
| 3. `_descrever_erro` total; usado em `:957`, `:960` e `:981`; `type(exc).__name__` mantido nos demais; `BaseException` não é capturada | `oracle_dba.py:719-728`, `:952-994`; INTERROMPIDO em `:1785-1819` | conforme |
| 4. CLI e Web com `MENSAGEM_DESFECHO_NAO_CONFIRMADO`; a ordem dos `elif` não muda | `src/main.py:258-262`; `app.py:511-516` | conforme |
| 5. `campos_invalidos_identidade` separada; `""` inválido nos dois casos; validação depois da elegibilidade e antes do hash; `RECUSA_PRE_HITL` fora de `FASES_REGISTRO_KILL`; builder com as 6 chaves; falha de gravação vira `logger.error` e a recusa se mantém; retorno sem `alvo`; `caminho_log` repassado | `oracle_dba.py:42-44`, `:730-770`, `:1331-1346`, `:1929-2034`, `:2072` | conforme; `fonte = alvo if isinstance(alvo, dict) else {}` equivale ao `.get` da decisão, porque esse ramo só é alcançado com `elegivel` |
| 6. `PREMISSA_CHARSET_MODELO` "NÃO VERIFICADA (L7)"; o fake simula `LENGTHB > 128` em UTF-8; o limite local continua em caracteres | `tests/fakes_oracle.py:23-28`, `:114-122` | conforme (m27 e M_LIMITE_GE_128 morrem) |
| 7. A8: fora de `__init__` e de `__all__`, sem renomear | `src/tools/__init__.py:3-9`, `:28-31` | conforme (P3) |
| 8. Gate `_exigir_pkg_kill_v2` como 1º comando dos 4 sandbox; nenhum teste define `OPS_KILL_PKG_VERSAO` | `tests/test_oracle_kill.py` (diff `+767-770`, `+807`, `+854`, `+882`, `+909`) | conforme; um grep nas linhas `+` do diff inteiro não acha `setenv`, `ORACLE_SANDBOX`, `ALTER SYSTEM` nem `ORACLE_USER` legado |

Triagem do §8.2, fora da decisão:
- **A2:** pares (formal, placeholder) em `test_item1_intencao.py` (3 pontos) e no T3.
- **A4 1/2/3/5:** fake com `size`, `p_status` só no execute, `setvalue` validado, `description` derivada do SELECT e conferência de placeholders.
- **A4.4:** spec e body × `ORDEM_BINDS_KILL_V2` (`ops_kill.sql:56`, `:92`).
- **A5 `:935`:** `instancia` só sai do ramo D8 (`:987`); o `:967` fica para a R1, como previsto.
- **A7:** testes K3.

Tudo conforme.

## 2. Asserções alteradas

Linhas `-` dos diffs de teste:
- `test_item1_intencao.py:651` → `:691-694`: P1, declarado. A nova asserção é mais forte: exige `MENSAGEM_RESULTADO_DESCONHECIDO`, a ausência de "NÃO executada" e `resultado_desconhecido is True`.
- T7 `param_invalido`: declarado (§8.10.2). O `resultado_banco == esperado` e o `fullmatch` do id continuam no `else`. No ramo novo, o `fullmatch` vale sobre o id do evento, e os `proibidos` continuam a valer.
- 4 sandbox: as asserções de status estão iguais, agora dentro do `try`.
- `fakes_oracle.py`: só código do fake, sem asserção.

Não há outra remoção.

## 3. Evidências

- **Mutação (todas DETECTADA):**
  - `mut_c6_m1_m16.md` (m1-m16);
  - `mut_k2_dba.md` (m17, m17b, m18-m21, m24);
  - `mut_k2_m29_main.md` e `mut_k2_m30_app.md`;
  - `mut_k3_oficial_dba.md` (os 8 do A7, X_REGEX, X_SERIAL, X_SELECT, m27);
  - `mut_k3_oficial_sql.md` (m26, m26b);
  - `mut_k4_oficial_dba.md` (m25, m31a-g), `mut_k4_oficial_init.md` (m23a/b), `mut_k4_oficial_m22.md`;
  - `mut_k5_oficial.md` (m28a-c).
- **Controle negativo do K2** (`k2_controle_negativo_482feb4.txt`): 34 failed contra a produção de `482feb4`, entre eles os testes da CLI, da Web e o `test_erro_interno_grava_resultado`.
- **Suíte:** K1 com 1290/16 em `tests/` (nota sobre a sonda), K2 1326/16, K3 1356/16, K4 1366/16 e K5 1378/16.

## 4. Ataques

- **TOCTOU:** sem mudança. A validação pré-HITL é uma camada a mais. O kill continua validando a identidade da reconsulta (`campos_invalidos_identidade_e_ref`), e o PKG compara no mesmo SELECT.
- **Ambiente:** nenhum `getenv` novo em produção. O gate só existe em teste e não é barreira (decisão §7.8).
- **Concorrência:** o evento usa `_gravar_linha_jsonl_duravel` (os mesmos 2 locks). Um lock indisponível leva ao `logger.error`, e a recusa se mantém.
- **Rerun (L8):** `preparar_intervencao_kill` roda uma vez por tool call (`app.py:313`). O ramo novo não chama `st.*`. A CLI e a Web só leem `requer_aprovacao`, `resultado_tool`, `motivo` (`app.py:315-326`) e, na aprovação, `alvo`/`hash_identidade`, que só existem quando `requer_aprovacao` é True (`app.py:331-334`, `src/main.py:211`).
- **Exceção no meio:** depois de `execute_iniciado`, os dois `except` são totais. Fora deles, o ERRO_INTERNO dá desconhecido True, e a `BaseException` vai para o INTERROMPIDO.
- **Resultado desconhecido depois do execute:** fechado pelo `is False` em `:1839`.

## 5. Achados (nenhum bloqueante)

- **O1 (sandbox, inferência; vai para o ensaio 4.1):** `test_sandbox_kill_propria_sessao_ou_usuario_protegido` fecha a sessão STARTUPADMIN **antes** do kill, um padrão anterior ao diff e mantido na migração. No PKG v2, o USUARIO_PROTEGIDO (`ops_kill.sql:176`) só é avaliado depois do SELECT do alvo, e o NO_DATA_FOUND (`:154-155`) vem antes. Com a sessão fechada, o resultado esperado pela leitura do SQL é ALVO_NAO_ENCONTRADO, e o teste falharia de forma visível, sem abrir falha. Manter a sessão admin aberta durante o kill depende da proteção do PKG: é **PENDENTE APROVAÇÃO** do responsável (aceite de risco) antes do ensaio.
- **O2 (sandbox, verificado no código):** `test_sandbox_kill_param_invalido` usa `sid=-1`, que `validar_parametros_kill` recusa antes de conectar (`oracle_dba.py:792-795`). O PKG não é exercitado, e a conexão DIAG aberta no teste não é necessária. Semântica anterior ao diff. O docstring "validado no MODELO" engana.
- **R-a (residual anterior ao diff, fora da rodada):** a linha RESULTADO do JSONL não tem `resultado_desconhecido` (`oracle_dba.py:1317-1327`). Um `ERRO_ORACLE` antes do execute (conhecido) e um depois dele (desconhecido) ficam iguais no `kill_approval.log`. O e-mail, o tool e o log da aplicação (`:1879-1885`) distinguem os dois. Sugestão para uma tarefa própria ou para a R1.
- **Controle negativo de K3 a K5:** não há um arquivo próprio contra `921e6ef`. As mutações dirigidas (m22-m31 e os 10 do Gemini) cumprem esse papel. Fica registrado.

## 6. Decisões do responsável (sem mudança aqui)

- P1 a P4, já aceitos.
- O1: manter ou não a sessão protegida aberta no ensaio 4.1.
- K2 e K4 continuam "PENDENTE APROVAÇÃO".
- Sem mudança em `db/ops_kill.sql`, `registry/`, na lista de protegidos e nos privilégios.

## 7. Fato × inferência

- **Verificado:** as linhas citadas em `bb9f74b`, os diffs, os resumos de mutação e de suíte (saídas fornecidas em `correcao/`) e o corpo dos commits.
- **Inferência:**
  - O1, pela leitura do SQL, sem banco (L7);
  - o Oracle devolver `''` como NULL;
  - o rerun do Streamlit só agir nas chamadas `st.*`;
  - `_serializar_para_log` ser total (não conferido nesta rodada).
