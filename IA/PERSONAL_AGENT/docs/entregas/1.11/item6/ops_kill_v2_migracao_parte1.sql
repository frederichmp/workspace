-- PROPOSTA (tarefa 1.11, item 6) — PENDENTE APROVAÇÃO. NÃO EXECUTAR.
-- Migração v1 -> v2, PARTE 1 de 2: pré-condições, backup e colunas novas.
-- Executar como STARTUPADMIN, primeiro no MODELO. Ver implantacao.md.
-- Esta parte NÃO altera o pacote: o kill v1 continua disponível.
-- Ao fim, o operador avalia as saídas. Só então, e só se tudo estiver como esperado,
-- executa a PARTE 2 (arquivo separado de propósito: a troca da spec não roda
-- junto se uma pré-condição falhar).

WHENEVER SQLERROR EXIT FAILURE ROLLBACK
SET ECHO ON

-- ============================================================================
-- PASSO 0 — Pré-condições (só leitura). Qualquer resultado inesperado: PARAR.
-- ============================================================================
-- 0.1 Nenhum outro objeto depende do pacote (esperado: só PACKAGE BODY OPS_OWNER.PKG_OPS_KILL)
SELECT owner, name, type FROM dba_dependencies
 WHERE referenced_owner = 'OPS_OWNER' AND referenced_name = 'PKG_OPS_KILL';
-- 0.2a Só STARTUP_KILL tem EXECUTE no pacote (esperado: 1 linha, STARTUP_KILL / EXECUTE)
SELECT grantee, privilege FROM dba_tab_privs
 WHERE owner = 'OPS_OWNER' AND table_name = 'PKG_OPS_KILL';
-- 0.2b Quem pode executar qualquer procedure (documentar; esperado: só contas DBA conhecidas)
SELECT grantee FROM dba_sys_privs WHERE privilege = 'EXECUTE ANY PROCEDURE' ORDER BY grantee;
-- 0.3 Nenhum job ou programa chama o pacote (esperado: 0 linhas em cada)
SELECT owner, job_name FROM dba_scheduler_jobs
 WHERE UPPER(job_action) LIKE '%PKG_OPS_KILL%';
SELECT owner, program_name FROM dba_scheduler_programs
 WHERE UPPER(program_action) LIKE '%PKG_OPS_KILL%';
SELECT job, log_user FROM dba_jobs
 WHERE UPPER(what) LIKE '%PKG_OPS_KILL%';
-- 0.4 Chamadas recentes por outros usuários, em todas as instâncias (esperado: 0 linhas).
--     Só INDÍCIO: gv$sql vê apenas cursores ainda no shared pool.
SELECT DISTINCT inst_id, parsing_schema_name FROM gv$sql
 WHERE UPPER(sql_text) LIKE '%PKG_OPS_KILL%'
   AND parsing_schema_name NOT IN ('STARTUP_KILL', 'STARTUPADMIN');
-- 0.5 Privilégios de sistema do OPS_OWNER (documentar; ALTER SYSTEM não está em db/ops_kill.sql)
SELECT privilege FROM dba_sys_privs WHERE grantee = 'OPS_OWNER';
-- 0.6 UTL_RAW executável pelo OPS_OWNER (a v2 usa UTL_RAW.CAST_TO_RAW; esperado: PUBLIC ou OPS_OWNER)
SELECT grantee, privilege FROM dba_tab_privs
 WHERE owner = 'SYS' AND table_name = 'UTL_RAW' AND grantee IN ('PUBLIC', 'OPS_OWNER');

-- ============================================================================
-- PASSO 1 — Backup do que está IMPLANTADO (salvar a saída fora do banco)
-- ============================================================================
SET LONG 200000 PAGESIZE 0 LINESIZE 32767
SELECT DBMS_METADATA.GET_DDL('PACKAGE_SPEC', 'PKG_OPS_KILL', 'OPS_OWNER') FROM dual;
SELECT DBMS_METADATA.GET_DDL('PACKAGE_BODY', 'PKG_OPS_KILL', 'OPS_OWNER') FROM dual;
SELECT DBMS_METADATA.GET_DDL('TABLE', 'OPS_KILL_AUDIT', 'OPS_OWNER') FROM dual;
SELECT DBMS_METADATA.GET_DEPENDENT_DDL('OBJECT_GRANT', 'PKG_OPS_KILL', 'OPS_OWNER') FROM dual;
-- Comparar spec/body com rollback_ops_kill_v1.sql (ignorando espaços). Se divergir: PARAR.
SET PAGESIZE 100 LINESIZE 200

-- ============================================================================
-- PASSO 2 — Colunas novas (aditivas, anuláveis). O kill v1 continua funcionando.
-- ============================================================================
ALTER TABLE ops_owner.ops_kill_audit ADD (
  alvo_logon_time     DATE,
  ref_aprovacao       VARCHAR2(64),
  campos_divergentes  VARCHAR2(64)
);
-- (PACKAGE VALID; PACKAGE BODY VALID). Se o BODY ficou INVALID:
--   ALTER PACKAGE ops_owner.pkg_ops_kill COMPILE BODY;
SELECT object_type, status FROM dba_objects
 WHERE owner = 'OPS_OWNER' AND object_name = 'PKG_OPS_KILL';

-- FIM DA PARTE 1. Avaliar as saídas acima antes de executar a PARTE 2.
