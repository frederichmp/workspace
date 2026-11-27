-- PROPOSTA (tarefa 1.11, item 6) — PENDENTE APROVAÇÃO. NÃO EXECUTAR.
-- Substituiria db/ops_kill.sql como script de INSTALAÇÃO COMPLETA (ambiente novo).
-- Para ambiente já instalado, usar ops_kill_v2_migracao_parte1.sql e depois
-- ops_kill_v2_migracao_parte2.sql (mesma pasta), conforme implantacao.md.
--
-- db/ops_kill.sql (v2)
-- Executar como STARTUPADMIN (DBA) no MODELO. Objetos criados no schema OPS_OWNER
-- (OPS_OWNER é conta bloqueada; ninguém faz login nela).
--
-- Mudança v1 -> v2: KILL_SESSION passa a receber a identidade esperada do alvo
-- (username, program, machine, logon_time) e a referência da aprovação; compara
-- com a linha lida da GV$SESSION no MESMO SELECT, antes do EXECUTE IMMEDIATE.
-- Divergência -> ALVO_DIVERGENTE, sem kill.
-- Erro antes do ALTER SYSTEM -> ERRO_PRE_KILL (sem kill, com auditoria); ORA-00030 no ALTER SYSTEM -> ALVO_AUSENTE_NO_KILL.
-- Sem sobrecarga e sem DEFAULT nos parâmetros novos: chamada com a assinatura v1
-- (4 argumentos) não compila (PLS-00306) e não executa nada.

-- 1. Privilégio de objeto. Roles não valem dentro de PL/SQL definer-rights,
--    então o OPS_OWNER precisa de grant direto para compilar e executar a consulta.
GRANT SELECT ON sys.gv_$session TO ops_owner;

-- 2. Objetos no schema OPS_OWNER
ALTER SESSION SET CURRENT_SCHEMA = OPS_OWNER;

CREATE TABLE ops_kill_audit (
  id                  NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dt_evento           TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
  solicitante         VARCHAR2(128) NOT NULL,
  inst_id             NUMBER,
  sid                 NUMBER,
  serial_no           NUMBER,
  alvo_username       VARCHAR2(128),
  alvo_program        VARCHAR2(128),
  alvo_machine        VARCHAR2(128),
  status_codigo       VARCHAR2(40) NOT NULL,
  mensagem            VARCHAR2(400),
  -- v2: valores OBSERVADOS na GV$SESSION e vínculo com a trilha JSONL da aplicação
  alvo_logon_time     DATE,
  ref_aprovacao       VARCHAR2(64),
  campos_divergentes  VARCHAR2(64)
);

CREATE OR REPLACE PACKAGE pkg_ops_kill AS
  -- Única procedure pública. Todos os parâmetros IN são obrigatórios (sem DEFAULT).
  --
  -- p_ref_aprovacao: identificador da intervenção, SÓ PARA REGISTRO.
  --   Quem gera: a aplicação (registrar_decisao_kill, uuid4().hex, 32 caracteres hex
  --   minúsculos), no momento em que grava a linha INTENCAO em kill_approval.log; o
  --   mesmo valor vai na linha RESULTADO.
  --   Quem valida: a aplicação (formato, antes de conectar) e este pacote (NOT NULL e
  --   formato ^[0-9a-f]{32}$; fora disso -> PARAM_INVALIDO, sem kill).
  --   O que o banco faz: apenas grava em OPS_KILL_AUDIT.ref_aprovacao, para ligar a
  --   linha de auditoria do banco às linhas do log da aplicação.
  --   O que o banco NÃO faz: não verifica que a aprovação existe, quem aprovou nem se
  --   ela ainda é válida (o banco não lê o log da aplicação). A autorização continua
  --   sendo o fluxo HITL da aplicação mais o grant EXECUTE restrito a STARTUP_KILL.
  PROCEDURE kill_session (
    p_inst_id             IN  NUMBER,
    p_sid                 IN  NUMBER,
    p_serial              IN  NUMBER,
    p_username_esperado   IN  VARCHAR2,
    p_program_esperado    IN  VARCHAR2,
    p_machine_esperado    IN  VARCHAR2,
    p_logon_time_esperado IN  DATE,
    p_ref_aprovacao       IN  VARCHAR2,
    p_status              OUT VARCHAR2
  );
END pkg_ops_kill;
/

CREATE OR REPLACE PACKAGE BODY pkg_ops_kill AS
  -- Usuários que esta rotina nunca derruba
  c_protegidos CONSTANT VARCHAR2(200) :=
    ',SYS,SYSTEM,DBSNMP,SYSMAN,OUTLN,STARTUPADMIN,OPS_OWNER,';

  PROCEDURE registra (
    p_solicitante VARCHAR2, p_inst NUMBER, p_sid NUMBER, p_serial NUMBER,
    p_user VARCHAR2, p_prog VARCHAR2, p_mach VARCHAR2, p_logon DATE,
    p_ref VARCHAR2, p_div VARCHAR2,
    p_status VARCHAR2, p_msg VARCHAR2
  ) IS
    PRAGMA AUTONOMOUS_TRANSACTION;
  BEGIN
    INSERT INTO ops_kill_audit (solicitante, inst_id, sid, serial_no,
      alvo_username, alvo_program, alvo_machine, alvo_logon_time,
      ref_aprovacao, campos_divergentes, status_codigo, mensagem)
    VALUES (p_solicitante, p_inst, p_sid, p_serial,
      p_user, p_prog, p_mach, p_logon,
      SUBSTRB(p_ref, 1, 64), SUBSTRB(p_div, 1, 64), p_status, SUBSTRB(p_msg, 1, 400));
    COMMIT;
  END registra;

  PROCEDURE kill_session (
    p_inst_id             IN  NUMBER,
    p_sid                 IN  NUMBER,
    p_serial              IN  NUMBER,
    p_username_esperado   IN  VARCHAR2,
    p_program_esperado    IN  VARCHAR2,
    p_machine_esperado    IN  VARCHAR2,
    p_logon_time_esperado IN  DATE,
    p_ref_aprovacao       IN  VARCHAR2,
    p_status              OUT VARCHAR2
  ) IS
    v_solicitante VARCHAR2(128) := SYS_CONTEXT('USERENV', 'SESSION_USER');
    v_user   VARCHAR2(128);
    v_prog   VARCHAR2(128);
    v_mach   VARCHAR2(128);
    v_type   VARCHAR2(10);
    v_logon  DATE;
    v_div    VARCHAR2(64);
    v_status VARCHAR2(40);
    v_msg    VARCHAR2(400);
    -- TRUE só na última instrução do bloco das etapas 1 a 6, com todas as checagens
    -- aprovadas. Exceção antes dela o deixa FALSE: sem ele, não há ALTER SYSTEM.
    v_pode_encerrar BOOLEAN := FALSE;
  BEGIN
    -- Etapas 1 a 6: nenhuma encerra sessão. Erro em qualquer delas vira ERRO_PRE_KILL,
    -- com linha em OPS_KILL_AUDIT e sem ALTER SYSTEM. O WHEN OTHERS deste bloco não
    -- cobre a etapa 7 nem o registra, que ficam depois do END do bloco.
    BEGIN
      -- 1. Parâmetros. program e machine podem ser NULL (a GV$SESSION pode trazê-los
      --    nulos; a comparação abaixo é null-safe). username e logon_time não.
      --    Tamanhos limitados aos das colunas da GV$SESSION (bytes), para que nenhum
      --    valor estoure variáveis/colunas e a chamada sempre termine com auditoria.
      --    REGEXP_LIKE com 'c': sensível a maiúsculas independentemente do NLS_SORT.
      --    p_ref_aprovacao: só formato é validado; o valor é apenas registrado (ver spec).
      IF p_inst_id IS NULL OR p_sid IS NULL OR p_serial IS NULL
         OR p_inst_id <= 0 OR p_sid <= 0 OR p_serial <= 0
         OR p_username_esperado IS NULL
         OR p_logon_time_esperado IS NULL
         OR LENGTHB(p_username_esperado) > 128
         OR LENGTHB(p_program_esperado) > 128
         OR LENGTHB(p_machine_esperado) > 128
         OR p_ref_aprovacao IS NULL
         OR NOT REGEXP_LIKE(p_ref_aprovacao, '^[0-9a-f]{32}$', 'c') THEN
        v_status := 'PARAM_INVALIDO';

      -- 2. Própria sessão
      ELSIF p_inst_id = SYS_CONTEXT('USERENV', 'INSTANCE')
        AND p_sid = SYS_CONTEXT('USERENV', 'SID') THEN
        v_status := 'PROPRIA_SESSAO';

      ELSE
        -- 3. Um único SELECT: lê o alvo e calcula os campos divergentes na mesma leitura.
        --    DECODE trata NULL = NULL como igual (comparação null-safe). Textos comparados
        --    como RAW (binário): o resultado não depende de NLS_COMP/NLS_SORT da sessão
        --    chamadora (BINARY_CI/AI tratariam 'App.exe' e 'app.exe' como iguais).
        BEGIN
          SELECT username, program, machine, type, logon_time,
                 RTRIM(
                   CASE WHEN DECODE(UTL_RAW.CAST_TO_RAW(username), UTL_RAW.CAST_TO_RAW(p_username_esperado), 0, 1) = 1 THEN 'USERNAME,' END ||
                   CASE WHEN DECODE(UTL_RAW.CAST_TO_RAW(program),  UTL_RAW.CAST_TO_RAW(p_program_esperado),  0, 1) = 1 THEN 'PROGRAM,'  END ||
                   CASE WHEN DECODE(UTL_RAW.CAST_TO_RAW(machine),  UTL_RAW.CAST_TO_RAW(p_machine_esperado),  0, 1) = 1 THEN 'MACHINE,'  END ||
                   CASE WHEN DECODE(logon_time, p_logon_time_esperado, 0, 1) = 1 THEN 'LOGON_TIME,' END,
                   ',')
            INTO v_user, v_prog, v_mach, v_type, v_logon, v_div
            FROM sys.gv_$session
           WHERE inst_id = p_inst_id
             AND sid = p_sid
             AND serial# = p_serial;
        EXCEPTION
          WHEN NO_DATA_FOUND THEN
            v_status := 'ALVO_NAO_ENCONTRADO';
        END;

        -- 4. Identidade divergente: não encerra. Observados vão nas colunas alvo_*;
        --    esperados (só dos campos divergentes) vão em mensagem.
        IF v_status IS NULL AND v_div IS NOT NULL THEN
          v_status := 'ALVO_DIVERGENTE';
          v_msg := SUBSTRB('divergente: ' || v_div || ' | esperado:'
            || CASE WHEN INSTR(v_div, 'USERNAME')   > 0 THEN ' username='   || p_username_esperado END
            || CASE WHEN INSTR(v_div, 'PROGRAM')    > 0 THEN ' program='    || NVL(p_program_esperado, '<null>') END
            || CASE WHEN INSTR(v_div, 'MACHINE')    > 0 THEN ' machine='    || NVL(p_machine_esperado, '<null>') END
            || CASE WHEN INSTR(v_div, 'LOGON_TIME') > 0 THEN ' logon_time=' || TO_CHAR(p_logon_time_esperado, 'YYYY-MM-DD HH24:MI:SS') END,
            1, 400);
        END IF;

        -- 5/6. Tipo e usuário protegido, sobre os valores OBSERVADOS.
        --      v_type nulo conta como não USER (null-safe).
        IF v_status IS NULL THEN
          IF v_type IS NULL OR v_type <> 'USER' THEN
            v_status := 'NAO_USUARIO';
          ELSIF v_user IS NULL
             OR INSTR(c_protegidos, ',' || UPPER(v_user) || ',') > 0 THEN
            v_status := 'USUARIO_PROTEGIDO';
          END IF;
        END IF;

        IF v_status IS NULL THEN
          v_pode_encerrar := TRUE;
        END IF;
      END IF;
    EXCEPTION
      WHEN OTHERS THEN
        v_status := 'ERRO_PRE_KILL';
        v_pode_encerrar := FALSE;
        v_msg := SUBSTRB(SQLERRM, 1, 400);
        -- Depois de exceção, as variáveis do INTO não são observação confiável.
        v_user := NULL; v_prog := NULL; v_mach := NULL; v_logon := NULL; v_div := NULL;
    END;

    -- 7. Encerramento: único ALTER SYSTEM do pacote. Micro-janela residual SELECT -> ALTER
    --    SYSTEM aceita: o comando é endereçado por sid + serial#; se a sessão não existir
    --    mais (inclusive SID reutilizado, com serial# novo), o Oracle devolve ORA-00030.
    IF v_pode_encerrar AND v_status IS NULL THEN
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
            v_status := 'ALVO_AUSENTE_NO_KILL';
          ELSE
            v_status := 'ERRO_ORACLE';
            v_msg := SUBSTRB(SQLERRM, 1, 400);
          END IF;
      END;
    END IF;

    registra(v_solicitante, p_inst_id, p_sid, p_serial,
             v_user, v_prog, v_mach, v_logon,
             p_ref_aprovacao, v_div, v_status, v_msg);
    p_status := v_status;
  END kill_session;
END pkg_ops_kill;
/

SHOW ERRORS PACKAGE BODY pkg_ops_kill

-- 3. Permissão de execução para o agente (somente a procedure de kill)
ALTER SESSION SET CURRENT_SCHEMA = STARTUPADMIN;
GRANT EXECUTE ON ops_owner.pkg_ops_kill TO startup_kill;
