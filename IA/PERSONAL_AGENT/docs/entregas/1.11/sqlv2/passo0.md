# P0 da parte A do SQL v2 (`docs/plans/1.11-sqlv2-parte2.md` §2): só leitura

- **Base:** `main` em `871ae13`. Autor: sessão principal (claude-opus-5-5). Sem Oracle e sem teste rodado.
- **Fontes:**
  - `docs/entregas/1.11/item6/ops_kill.sql` (rascunho v2, 215 linhas);
  - `src/tools/oracle_dba.py` (`:82-96` e `:1176-1240`);
  - `tests/fakes_oracle.py` (`:130-215`).

## Insumo 1: erro antes × durante o `ALTER SYSTEM`

- **Fato, SQL:**
  - o `BEGIN ... EXCEPTION WHEN NO_DATA_FOUND` do SELECT (`:140-156`) só trata a ausência do alvo; qualquer outro erro no SELECT, no `UTL_RAW` ou nas checagens 5/6 **sai do PKG como exceção**;
  - só o `ALTER SYSTEM` (`:184-199`) tem `WHEN OTHERS`, que dá `MARCADA_PARA_KILL` (-31), `ALVO_NAO_ENCONTRADO` (-30) ou `ERRO_ORACLE`, este com o `SQLERRM` na mensagem.
- **Fato, Python:** exceção depois do `execute` vira `ERRO_ORACLE` com `resultado_desconhecido True` (`:1219-1235`). O erro antes do kill fica, portanto, como "pode ter encerrado", embora o `ALTER SYSTEM` nunca tenha rodado.
- **Fato, auditoria:** nesse caminho, o `registra` (`:203-205`) não roda, e o erro pré-kill não deixa linha em `OPS_KILL_AUDIT`.

## Insumo 2: ORA-00030 com código próprio

- **Fato:** o ORA-00030 no `ALTER SYSTEM` (`:193-194`) e o `NO_DATA_FOUND` do SELECT (`:155`) dão o mesmo `ALVO_NAO_ENCONTRADO`. Não se distingue "alvo inexistente" de "alvo saiu entre o SELECT e o kill" (a micro-janela de `:180-182`).
- **Fato, Python:** `ALVO_NAO_ENCONTRADO` está em `RECUSAS_PKG_SEM_KILL` (`:88-91`), e o comentário de `:87` registra o ORA-00030.

## Insumo 3: revalidar o fake contra o SQL

- **Fato:**
  - a classificação do Python é por lista fechada (`RESULTADOS_KILL_EXECUTADO` e `RECUSAS_PKG_SEM_KILL`), e fora dela tudo é resultado desconhecido (`:1183-1200`);
  - o status `ERRO_ORACLE` **devolvido** pelo PKG cai em desconhecido;
  - o fake (`fakes_oracle.py:141`) devolve qualquer `status_pkg`;
  - ~~nenhum teste amarra os literais `v_status := '...'` do SQL às listas do Python~~. **Corrigido pelo C1:** o teste existe, `test_k2_invariantes_das_listas_de_status_do_pkg` (`tests/test_oracle_kill.py:1524-1539`), sobre o `ops_kill.sql`. Falta cobrir o `parte2.sql`, o literal fora de `[A-Z_]` e o fake (`decisao_c1.md` §4).

## Perguntas para o C1 (`seguranca`)

1. **Código do erro pré-kill:** qual (`ERRO_PRE_KILL`?), onde capturar no PKG (bloco externo em volta das etapas 3 a 6, sem engolir o caminho do `ALTER SYSTEM`) e se o `registra` grava a linha com `SQLERRM` truncado.
   - No Python, ele entra em `RECUSAS_PKG_SEM_KILL` (prova de não execução)?
   - Qual texto vai ao LLM, já que a R1 proíbe texto cru?
2. **Código do ORA-00030:** qual (por exemplo, `ALVO_SAIU_ANTES_DO_KILL`), e se fica nas recusas sem kill.
3. **`ERRO_ORACLE` devolvido pelo PKG** (falha do `ALTER SYSTEM`): continua desconhecido, como é hoje, conservador, ou vira recusa? Há códigos do `ALTER SYSTEM` que deixam a sessão em estado indefinido.
4. **Teste de amarração:** um teste sem conexão que extrai todos os literais de `v_status := '...'` do SQL v2 e exige que cada um esteja numa das listas do Python ou na lista declarada de desconhecidos; e que o fake recuse `status_pkg` fora desse conjunto.
5. **Migração e rollback:** as colunas e os grants mudam com os códigos novos? (`status_codigo` é `VARCHAR2`; conferir o tamanho.) O `rollback_ops_kill_v1.sql` não muda.
6. **`implantacao.md`:** `:159-161` e `:208` desatualizados; a §3.2 passa a usar o gate `OPS_KILL_PKG_VERSAO` (S3).
