# Roteiro da janela (parte D do plano `1.11-sqlv2-parte2`, MODELO)

- **Quem executa:** o STARTUPADMIN, na janela marcada. A sessão principal não conecta ao banco.
- **Banco:** o MODELO, a base de teste do ambiente controlado do responsável, acessível só com a VPN ligada. É a mesma base do ensaio 4.1. **Antes de começar:** confirmar que a VPN está ligada.
- **Base:** `docs/entregas/1.11/item6/implantacao.md` §3.2 (com o gate, decisão S3) e §4.
- **Pré-requisitos, sem eles não marcar a janela:**
  1. ensaio 4.1 limpo (`roteiro_ensaio_4_1.md`, passos 3 e 5);
  2. texto do SQL v2 aprovado (parte C);
  3. v2 commitado em `db/ops_kill.sql`.
- **Saídas brutas:** em `docs/entregas/1.11/sqlv2/janela/`, com credenciais, usuário do Windows, organização e e-mail retirados (L57).

## Parte 1 já aplicada

O passo 2 da parte 1 (`ALTER TABLE ... ADD`) foi aplicado no MODELO em 2026-11-17 (`implantacao.md` §7.6), e o rollback não remove as colunas. Rodá-lo de novo daria ORA-01430, e o `WHENEVER SQLERROR EXIT` abortaria o script. Por isso a janela roda só os passos 0 e 1 e confere as colunas em `DBA_TAB_COLUMNS` (consulta do `roteiro_ensaio_4_1.md`, passo 2). O SQL não muda.

## Passos

| # | O que fazer | Conferir | Kill disponível? | Saída |
|---|---|---|---|---|
| 0–2 | **Parte 1, só passos 0 e 1** (ver acima), com `SPOOL`, e a conferência das colunas | pré-condições; backup igual a `rollback_ops_kill_v1.sql` (se divergir, **parar**); 3 colunas presentes; body VALID | sim (v1) | `j1_parte1.txt` |
| — | **Parada humana:** avaliar a parte 1 | | sim (v1) | |
| 3 | **Antes da janela:** CLI e Web rodando a `main` integrada, **sem** `OPS_KILL_PKG_VERSAO` no shell | nenhuma subida mostra o aviso "HABILITADO". Não fazer kill de prova: com o PKG ainda v1 e o gate ligado por engano, a chamada daria PLS-00306 e resultado desconhecido, sem encerrar sessão, e só sujaria o registro | **não** (gate desligado) | `j3_gate_desligado.txt` |
| ▶ | **Início da janela:** `SPOOL` e depois `@ops_kill_v2_migracao_parte2.sql`. O script grava `inicio_janela` | | não | `j4_parte2.txt` |
| 4–5 | Spec e body v2; conferências do script | `DBA_ERRORS` vazio; spec e body VALID; `DBA_ARGUMENTS` com 9 linhas, sem sobrecarga e sem DEFAULT; grant; `DBA_SOURCE` com 2 linhas (`ALVO_AUSENTE_NO_KILL` 1 e `ERRO_PRE_KILL` 1). **Falhou alguma?** Ir ao rollback, com o gate ainda desligado | não | (mesma) |
| 6 | Só a sessão do operador sobe com `OPS_KILL_PKG_VERSAO=2` no shell | o aviso "HABILITADO" aparece na subida | não, até o passo 7 | `j6_gate_ligado.txt` |
| 7 | Primeiro kill sandbox v2 com identidade correta: `ORACLE_SANDBOX=1 OPS_KILL_PKG_VERSAO=2 python -m pytest -q -rs -p no:cacheprovider tests/test_oracle_kill.py::test_sandbox_kill_sessao_valida_encerrada` | **passed** (ENCERRADA) | **sim (v2)** | `j7_primeiro_kill.txt` |
| ■ | **Fim da janela:** hora do passo 7. Anotar `inicio_janela` e o fim | | sim (v2) | `j_veredito.md` |
| 8 | Demais testes sandbox v2: `-m sandbox_only tests/test_oracle_kill.py` | todos passed | sim (v2) | `j8_demais.txt` |

## Rollback (implantacao.md §4)

1. **Desligar o gate:** parar a CLI e a Web e subir sem `OPS_KILL_PKG_VERSAO`. O aviso "HABILITADO" não pode aparecer.
2. `SPOOL` e depois `@rollback_ops_kill_v1.sql`. Conferir `DBA_ERRORS` vazio, VALID, `DBA_ARGUMENTS` com 4 linhas e o grant (consultas do `roteiro_ensaio_4_1.md`, passo 5).
3. **Sem `git revert`:** o Python v2 com o gate desligado não chama o PKG. O kill fica indisponível até nova decisão.

A ordem (1 e só depois 2) evita PLS-00306, que daria resultado desconhecido. Saída em `jr_rollback.txt`.

## Depois

A sessão principal confere as saídas e registra no GOVERNANCA_LOG o início e o fim da janela e o veredito. Fecha o plano e acrescenta as lições ao PROCESSO §7.
