# Roteiro do ensaio 4.1 (parte B do plano `1.11-sqlv2-parte2`)

- **Quem executa:** o STARTUPADMIN, em **sandbox autorizado**. `ORACLE_SANDBOX=1` é definida **só por ele**, no shell da sessão autorizada. A sessão principal não conecta ao banco.
- **Banco:** o MODELO, a base de teste do ambiente controlado do responsável (informado em 2026-11-26), acessível só com a VPN ligada. Não é produção.
- **Ensaio e janela rodam na mesma base:** o ensaio termina com o rollback e a v1 restaurada. A janela (`roteiro_janela.md`) repete a parte 2 depois da aprovação do texto.
- **Antes de começar:** confirmar que a VPN está ligada e que o DSN da sessão aponta para o MODELO.
- **Base:** `docs/entregas/1.11/item6/implantacao.md` §4.1 e §5; scripts em `docs/entregas/1.11/item6/`.
- **Saídas brutas:** em `docs/entregas/1.11/sqlv2/ensaio/`, um arquivo por passo, com o nome indicado abaixo.
- **Antes de trazer as saídas:** tirar credenciais, nome de usuário do Windows, organização e e-mail (L57). Senha nunca vai para arquivo.
- **Regra de parada:** qualquer resultado fora do esperado → **parar**, não seguir para o passo seguinte, trazer a saída.

## Pendência antes do ensaio (decisão do responsável)

A §4.1 passo 4 e a §5 citam testes sandbox que **não existem como código**. Hoje há só 4 testes v2 de kill em `tests/test_oracle_kill.py`: `test_sandbox_kill_sessao_valida_encerrada`, `_alvo_nao_encontrado`, `_param_invalido` e `_propria_sessao_ou_usuario_protegido`.

Faltam:
- Python v2 × PKG v1 (PLS-00306, alvo vivo, auditoria inalterada);
- bloco v1 literal (4 argumentos) × PKG v2;
- divergência de `program`/`logon_time`, NLS linguístico, null-safe, esperado acima de 128 bytes e `ref` maiúscula.

**Decisão do responsável (2026-11-26, "pode seguir a recomendação"):** tarefa própria, antes do ensaio, para escrever esses testes sandbox. Plano: `docs/plans/1.11-sandbox-transicao.md`. É código do PROCESSO §2, então só Opus. O passo 4 abaixo só roda depois dela.

## Passos

| # | O que fazer | Conferir | Arquivo de saída |
|---|---|---|---|
| 1 | **Linha de base v1.** PKG v1 instalado. Rodar os testes sandbox numa cópia de trabalho do commit `ede7525`, a última com o Python v1 (`git worktree add <pasta> ede7525`, fora do diretório de trabalho atual), com as credenciais da sessão autorizada de costume: `ORACLE_SANDBOX=1 python -m pytest -q -rs -p no:cacheprovider -m sandbox_only tests/test_oracle_kill.py` | testes de kill sandbox **passed**, nenhum skipped por falta de sandbox | `p1_linha_base_v1.txt` |
| 2 | **Parte 1, só passos 0 e 1.** O passo 2 (`ALTER TABLE ... ADD`) já foi aplicado no MODELO em 2026-11-17 (`implantacao.md` §7.6); rodá-lo de novo dá ORA-01430. Com `SPOOL <saída>`, executar as consultas dos passos 0 e 1 do `ops_kill_v2_migracao_parte1.sql` (até a linha `SET PAGESIZE 100 LINESIZE 200`) e a conferência das colunas abaixo | pré-condições como o script pede; backup igual a `rollback_ops_kill_v1.sql` (se divergir, **parar**); as 3 colunas presentes, anuláveis; spec e body **VALID** | `p2_parte1.txt` e `p2_backup_dbms_metadata.sql` |
| — | **Parada humana:** avaliar o passo 2 antes da parte 2 | | |
| 3 | **Parte 2:** `SPOOL <saída>` e depois `@ops_kill_v2_migracao_parte2.sql` | `inicio_janela` impresso; `DBA_ERRORS` **vazio**; spec e body **VALID**; `DBA_ARGUMENTS` com **9** linhas, sem sobrecarga e sem DEFAULT; grant EXECUTE para STARTUP_KILL; `DBA_SOURCE` com **2** linhas (`ALVO_AUSENTE_NO_KILL` 1 e `ERRO_PRE_KILL` 1) e **4** linhas com `v_pode_encerrar` | `p3_parte2.txt` |
| 4 | **Testes v2:** na cópia de trabalho da `main` (Python v2), `ORACLE_SANDBOX=1 OPS_KILL_PKG_VERSAO=2 python -m pytest -q -rs -p no:cacheprovider -m sandbox_only tests/test_oracle_kill.py`. Testes de transição: conforme a pendência acima | os 4 `test_sandbox_kill_*` **passed** (ENCERRADA, ALVO_NAO_ENCONTRADO, PARAM_INVALIDO, PROPRIA_SESSAO/USUARIO_PROTEGIDO); os 2 de privilégio negativo **passed** | `p4_testes_v2.txt` |
| 5 | **Rollback:** `SPOOL <saída>` e depois `@rollback_ops_kill_v1.sql`. Conferir à mão em seguida (consultas abaixo) | `DBA_ERRORS` **vazio**; spec e body **VALID**; `DBA_ARGUMENTS` com **4** linhas (`P_INST_ID`, `P_SID`, `P_SERIAL`, `P_STATUS`), sem sobrecarga; grant EXECUTE para STARTUP_KILL | `p5_rollback.txt` |
| 6 | **Depois do rollback:** repetir o passo 1 na cópia `ede7525` | o mesmo resultado do passo 1; as colunas v2 continuam na tabela e não atrapalham | `p6_v1_restaurada.txt` |
| 7 | **Registro:** veredito do operador (limpo ou não, e o que divergiu) | só com os passos 3 e 5 limpos a janela pode ser marcada | `p7_veredito.md` |

Conferência das colunas do passo 2 (só leitura; esperado: `ALVO_LOGON_TIME` DATE, `CAMPOS_DIVERGENTES` VARCHAR2(64), `REF_APROVACAO` VARCHAR2(64), todas `NULLABLE = Y`):

```sql
SELECT column_name, data_type, data_length, nullable FROM dba_tab_columns
 WHERE owner = 'OPS_OWNER' AND table_name = 'OPS_KILL_AUDIT'
   AND column_name IN ('ALVO_LOGON_TIME', 'REF_APROVACAO', 'CAMPOS_DIVERGENTES')
 ORDER BY column_name;
```

Consultas de conferência do passo 5 (só leitura):

```sql
SELECT name, type, line, text FROM dba_errors WHERE owner = 'OPS_OWNER' AND name = 'PKG_OPS_KILL';
SELECT object_type, status FROM dba_objects WHERE owner = 'OPS_OWNER' AND object_name = 'PKG_OPS_KILL';
SELECT argument_name, position, overload FROM dba_arguments
 WHERE owner = 'OPS_OWNER' AND package_name = 'PKG_OPS_KILL' AND object_name = 'KILL_SESSION' ORDER BY position;
SELECT grantee, privilege FROM dba_tab_privs WHERE owner = 'OPS_OWNER' AND table_name = 'PKG_OPS_KILL';
```

## O que a sessão principal faz com as saídas

- Confere cada arquivo contra a coluna "Conferir" e grava o parecer em `docs/entregas/1.11/sqlv2/ensaio/conferencia.md`.
- Registra no GOVERNANCA_LOG.
- Com o ensaio limpo, o responsável decide a parte C (aprovação do texto, pendência 1). Só então o v2 vai para `db/ops_kill.sql`, em commit próprio.
