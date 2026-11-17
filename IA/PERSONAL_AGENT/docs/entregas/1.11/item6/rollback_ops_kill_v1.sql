-- PROPOSTA (tarefa 1.11, item 6) — rollback para a v1. Usar só conforme implantacao.md.
-- Executar como STARTUPADMIN. Spec e body abaixo são cópia literal de db/ops_kill.sql (v1, commit atual).
-- As colunas novas de OPS_KILL_AUDIT são MANTIDAS: o body v1 faz INSERT com lista de
-- colunas explícita e continua compilando; removê-las perderia auditoria da v2.
-- Antes de executar, confirmar que este texto é igual ao backup do PASSO 1 da migração.

WHENEVER SQLERROR EXIT FAILURE ROLLBACK
SET ECHO ON

ALTER SESSION SET CURRENT_SCHEMA = OPS_OWNER;

CREATE OR REPLACE PACKAGE pkg_ops_kill AS
  PROCEDURE kill_session (
    p_inst_id IN  NUMBER,
    p_sid     IN  NUMBER,
    p_serial  IN  NUMBER,
    p_status  OUT VARCHAR2
  );
END pkg_ops_kill;
/

CREATE OR REPLACE PACKAGE BODY pkg_ops_kill AS
  -- Usuários que esta rotina nunca derruba
  c_protegidos CONSTANT VARCHAR2(200) :=
    ',SYS,SYSTEM,DBSNMP,SYSMAN,OUTLN,STARTUPADMIN,OPS_OWNER,';

  PROCEDURE registra (
    p_solicitante VARCHAR2, p_inst NUMBER, p_sid NUMBER, p_serial NUMBER,
    p_user VARCHAR2, p_prog VARCHAR2, p_mach VARCHAR2,
    p_status VARCHAR2, p_msg VARCHAR2
  ) IS
    PRAGMA AUTONOMOUS_TRANSACTION;
  BEGIN
    INSERT INTO ops_kill_audit (solicitante, inst_id, sid, serial_no,
      alvo_username, alvo_program, alvo_machine, status_codigo, mensagem)
    VALUES (p_solicitante, p_inst, p_sid, p_serial,
      p_user, p_prog, p_mach, p_status, SUBSTR(p_msg, 1, 400));
    COMMIT;
  END registra;

  PROCEDURE kill_session (
    p_inst_id IN  NUMBER,
    p_sid     IN  NUMBER,
    p_serial  IN  NUMBER,
    p_status  OUT VARCHAR2
  ) IS
    v_solicitante VARCHAR2(128) := SYS_CONTEXT('USERENV', 'SESSION_USER');
    v_user   VARCHAR2(128);
    v_prog   VARCHAR2(128);
    v_mach   VARCHAR2(128);
    v_type   VARCHAR2(10);
    v_status VARCHAR2(40);
    v_msg    VARCHAR2(400);
  BEGIN
    IF p_inst_id IS NULL OR p_sid IS NULL OR p_serial IS NULL
       OR p_inst_id <= 0 OR p_sid <= 0 OR p_serial <= 0 THEN
      v_status := 'PARAM_INVALIDO';

    ELSIF p_inst_id = SYS_CONTEXT('USERENV', 'INSTANCE')
      AND p_sid = SYS_CONTEXT('USERENV', 'SID') THEN
      v_status := 'PROPRIA_SESSAO';

    ELSE
      BEGIN
        SELECT username, program, machine, type
          INTO v_user, v_prog, v_mach, v_type
          FROM sys.gv_$session
         WHERE inst_id = p_inst_id
           AND sid = p_sid
           AND serial# = p_serial;
      EXCEPTION
        WHEN NO_DATA_FOUND THEN
          v_status := 'ALVO_NAO_ENCONTRADO';
      END;

      IF v_status IS NULL THEN
        IF v_type <> 'USER' THEN
          v_status := 'NAO_USUARIO';
        ELSIF v_user IS NULL
           OR INSTR(c_protegidos, ',' || UPPER(v_user) || ',') > 0 THEN
          v_status := 'USUARIO_PROTEGIDO';
        END IF;
      END IF;

      IF v_status IS NULL THEN
        BEGIN
          EXECUTE IMMEDIATE 'ALTER SYSTEM KILL SESSION '''
            || TO_CHAR(p_sid) || ',' || TO_CHAR(p_serial)
            || ',@' || TO_CHAR(p_inst_id) || ''' IMMEDIATE';
          v_status := 'ENCERRADA';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE = -31 THEN
              v_status := 'MARCADA_PARA_KILL';
            ELSIF SQLCODE = -30 THEN
              v_status := 'ALVO_NAO_ENCONTRADO';
            ELSE
              v_status := 'ERRO_ORACLE';
              v_msg := SUBSTR(SQLERRM, 1, 400);
            END IF;
        END;
      END IF;
    END IF;

    registra(v_solicitante, p_inst_id, p_sid, p_serial,
             v_user, v_prog, v_mach, v_status, v_msg);
    p_status := v_status;
  END kill_session;
END pkg_ops_kill;
/

SHOW ERRORS PACKAGE BODY pkg_ops_kill

ALTER SESSION SET CURRENT_SCHEMA = STARTUPADMIN;

-- ============================================================================
-- Conferências pós-compilação (esperado entre parênteses)
-- ============================================================================
-- (0 linhas)
SELECT name, type, line, text FROM dba_errors
 WHERE owner = 'OPS_OWNER' AND name = 'PKG_OPS_KILL';
-- (PACKAGE VALID; PACKAGE BODY VALID)
SELECT object_type, status FROM dba_objects
 WHERE owner = 'OPS_OWNER' AND object_name = 'PKG_OPS_KILL';
-- (4 linhas, posições 1 a 4, OVERLOAD nulo, nenhuma DEFAULTED = 'Y')
SELECT position, argument_name, data_type, in_out, overload, defaulted
  FROM dba_arguments
 WHERE owner = 'OPS_OWNER' AND package_name = 'PKG_OPS_KILL' AND object_name = 'KILL_SESSION'
 ORDER BY position;
-- (STARTUP_KILL / EXECUTE; CREATE OR REPLACE preserva o grant)
SELECT grantee, privilege FROM dba_tab_privs
 WHERE owner = 'OPS_OWNER' AND table_name = 'PKG_OPS_KILL';

-- Em seguida: git revert do commit Python do item 6.
