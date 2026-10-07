-- ROTINA DE COLETA DE ESTATISTICAS CONTROLADA POR TABELA


--------------------------------------------------------------------------------
-- 0) DROPS SEGUROS (ignora se não existir)
--------------------------------------------------------------------------------

-- Drop JOB
BEGIN
  DBMS_SCHEDULER.DROP_JOB('STARTUPADMIN.JN_COLETA_STATS_DIARIA', TRUE);
EXCEPTION
  WHEN OTHERS THEN
    -- ORA-27475: job não existe
    IF SQLCODE != -27475 THEN RAISE; END IF;
END;
/

-- Drop PROCEDURE COMO SYS
BEGIN
  EXECUTE IMMEDIATE 'DROP PROCEDURE SYS.P_STR_GATHER_STATS_CTL';
EXCEPTION
  WHEN OTHERS THEN
    -- ORA-04043: objeto não existe
    IF SQLCODE != -4043 THEN RAISE; END IF;
END;
/

-- Drop SEQUENCE
BEGIN
  EXECUTE IMMEDIATE 'DROP SEQUENCE STARTUPADMIN.SEQ_TAB_STATS_LOG';
EXCEPTION
  WHEN OTHERS THEN
    -- ORA-02289: sequência não existe
    IF SQLCODE != -2289 THEN RAISE; END IF;
END;
/

-- Drop TABELAS (LOG primeiro; PURGE evita recycle bin)
BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE STARTUPADMIN.TAB_STATS_LOG PURGE';
EXCEPTION
  WHEN OTHERS THEN
    -- ORA-00942: tabela não existe
    IF SQLCODE != -942 THEN RAISE; END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE STARTUPADMIN.TAB_STATS_CONTROL PURGE';
EXCEPTION
  WHEN OTHERS THEN
    -- ORA-00942: tabela não existe
    IF SQLCODE != -942 THEN RAISE; END IF;
END;
/



-- === 1) Tabelas de controle e log ===

CREATE TABLE STARTUPADMIN.TAB_STATS_CONTROL (
  owner           VARCHAR2(30)   NOT NULL,
  table_name      VARCHAR2(30)   NOT NULL,
  enabled         CHAR(1)        DEFAULT 'Y' CHECK (enabled IN ('Y','N')),
  sample_percent  NUMBER(5,2)    DEFAULT 100,
  method_opt      VARCHAR2(400)  DEFAULT 'FOR ALL COLUMNS SIZE AUTO',
  cascade_flag    CHAR(1)        DEFAULT 'Y' CHECK (cascade_flag IN ('Y','N')),
  degree          NUMBER         DEFAULT NULL,
  last_run        DATE,
  last_result     VARCHAR2(20),
  last_analyzed   DATE,
  last_num_rows   NUMBER,
  stale_stats     VARCHAR2(3),
  CONSTRAINT PK_TAB_STATS_CONTROL PRIMARY KEY (owner, table_name)
);

CREATE TABLE STARTUPADMIN.TAB_STATS_LOG (
  run_id              NUMBER       NOT NULL,
  run_dttm            DATE         DEFAULT SYSDATE,
  owner               VARCHAR2(30) NOT NULL,
  table_name          VARCHAR2(30) NOT NULL,
  action              VARCHAR2(20) DEFAULT 'GATHER',
  sample_percent      NUMBER(5,2),
  cascade_flag        CHAR(1),
  degree              NUMBER,
  before_last_analyzed DATE,
  after_last_analyzed  DATE,
  before_num_rows     NUMBER,
  after_num_rows      NUMBER,
  stale_before        VARCHAR2(3),
  stale_after         VARCHAR2(3),
  status              VARCHAR2(20),
  err_msg             VARCHAR2(4000),
  CONSTRAINT PK_TAB_STATS_LOG PRIMARY KEY (run_id)
);

CREATE SEQUENCE STARTUPADMIN.SEQ_TAB_STATS_LOG START WITH 1 INCREMENT BY 1 CACHE 100;

-- === 2) Carga inicial (ajuste se quiser) ===
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('STARTUPADMIN','TAB_STATS_CONTROL');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('STARTUPADMIN','TAB_STATS_LOG');

INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('SFT','SFT_CONTA_CORRENTE_BANCARIO');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('SFT','SFT_LANCTO_CTA_CORRENTE_BANC');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('SFT','SFT_RESUMO_EXTRATO_BANCO');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('SFT','SFT_EXTRATO_BANCO');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('SFT','SFT_LANC_CTA_CORR_EXTRATO_BCO');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('SFT','SFT_TIPO_CTA_CORRENTE_BANCARIO');

INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('SFT','SFT_ABASTECIMENTO_OS_TAMANHO');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('SFT','SFT_ITEM_NF_SAIDA_TAMANHO');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('SFT','SFT_ITEM_REM_RET_TALAO_TEMP');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('SFT','SFT_ITEM_REM_RET_TAL_TAM_TEMP');

INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('ESTOQUE','NOTA_FISCAL_ENTRADA');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('ESTOQUE','OS_REQUISICAO_INTERNA');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('ESTOQUE','ABASTECIMENTO_ORDEM_SERVICO');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('ESTOQUE','ABAST_REQUISICAO_INTERNA');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('ESTOQUE','REQUISICAO_INTERNA');

INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('PCP','REFERENCIA');
INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('PCP','COMPONENTE_ORDEM_SERVICO');

INSERT INTO STARTUPADMIN.TAB_STATS_CONTROL (owner, table_name) VALUES ('GENERICO','UNIDADE_MEDIDA');

COMMIT;

-- === 3) Procedure de coleta e auditoria ===

CREATE OR REPLACE PROCEDURE SYS.P_STR_GATHER_STATS_CTL(
  p_only_if_enabled IN CHAR DEFAULT 'Y'
) AUTHID DEFINER IS
  CURSOR c_tabs IS
    SELECT owner,
           table_name,
           NVL(sample_percent,10)                     sp,
           NVL(method_opt,'FOR ALL COLUMNS SIZE AUTO') mo,
           CASE WHEN cascade_flag='N' THEN 'N' ELSE 'Y' END cf,
           degree                                      dg   -- pode ser NULL
      FROM STARTUPADMIN.TAB_STATS_CONTROL
     WHERE (p_only_if_enabled='Y' AND enabled='Y')
        OR (p_only_if_enabled<>'Y');

  v_before_last   DATE;
  v_after_last    DATE;
  v_before_rows   NUMBER;
  v_after_rows    NUMBER;
  v_stale_before  VARCHAR2(3);
  v_stale_after   VARCHAR2(3);
  v_status        VARCHAR2(20);
  v_err           VARCHAR2(4000);
  v_run_id        NUMBER;
BEGIN
  DBMS_STATS.FLUSH_DATABASE_MONITORING_INFO;

  FOR r IN c_tabs LOOP
    v_before_last := NULL; v_after_last := NULL;
    v_before_rows := NULL; v_after_rows := NULL;
    v_stale_before:= NULL; v_stale_after:= NULL;
    v_status := 'STARTED'; v_err := NULL;

    BEGIN
      BEGIN
        SELECT s.last_analyzed, s.num_rows, NVL(s.stale_stats,'NO')
          INTO v_before_last, v_before_rows, v_stale_before
          FROM sys.dba_tab_statistics s
         WHERE s.owner = r.owner AND s.table_name = r.table_name;
      EXCEPTION WHEN NO_DATA_FOUND THEN
        v_before_last := NULL; v_before_rows := NULL; v_stale_before := NULL;
      END;

      DBMS_STATS.GATHER_TABLE_STATS(
        ownname          => r.owner,
        tabname          => r.table_name,
        estimate_percent => r.sp,
        method_opt       => r.mo,
        cascade          => (r.cf='Y'),
        degree           => r.dg,                      -- NULL = Oracle decide
        no_invalidate    => DBMS_STATS.AUTO_INVALIDATE
      );

      BEGIN
        SELECT s.last_analyzed, s.num_rows, NVL(s.stale_stats,'NO')
          INTO v_after_last, v_after_rows, v_stale_after
          FROM sys.dba_tab_statistics s
         WHERE s.owner = r.owner AND s.table_name = r.table_name;
      EXCEPTION WHEN NO_DATA_FOUND THEN
        v_after_last := NULL; v_after_rows := NULL; v_stale_after := NULL;
      END;

      v_status := CASE
                    WHEN v_after_last IS NOT NULL
                         AND (v_before_last IS NULL OR v_after_last > v_before_last)
                    THEN 'UPDATED'
                    ELSE 'NOCHANGE'
                  END;

      UPDATE STARTUPADMIN.TAB_STATS_CONTROL t
         SET t.last_run      = SYSDATE,
             t.last_result   = v_status,
             t.last_analyzed = v_after_last,
             t.last_num_rows = v_after_rows,
             t.stale_stats   = v_stale_after
       WHERE t.owner = r.owner AND t.table_name = r.table_name;

    EXCEPTION WHEN OTHERS THEN
      v_status := 'ERROR';
      v_err    := SUBSTR(SQLERRM,1,4000);
      UPDATE STARTUPADMIN.TAB_STATS_CONTROL t
         SET t.last_run    = SYSDATE,
             t.last_result = v_status
       WHERE t.owner = r.owner AND t.table_name = r.table_name;
    END;

    v_run_id := STARTUPADMIN.SEQ_TAB_STATS_LOG.NEXTVAL;
    INSERT INTO STARTUPADMIN.TAB_STATS_LOG
      (run_id, owner, table_name, sample_percent, cascade_flag, degree,
       before_last_analyzed, after_last_analyzed, before_num_rows, after_num_rows,
       stale_before, stale_after, status, err_msg)
    VALUES
      (v_run_id, r.owner, r.table_name, r.sp, r.cf, r.dg,
       v_before_last, v_after_last, v_before_rows, v_after_rows,
       v_stale_before, v_stale_after, v_status, v_err);
  END LOOP;

  COMMIT;
END;
/

-- opcional: grants conforme sua política
GRANT EXECUTE ON SYS.P_STR_GATHER_STATS_CTL TO STARTUPADMIN;

-- === 4) Job diário 06:00 ===
BEGIN
  DBMS_SCHEDULER.CREATE_JOB (
    job_name        => 'STARTUPADMIN.JB_COLETA_STATS_DIARIA',
    job_type        => 'PLSQL_BLOCK',
    job_action      => 'BEGIN SYS.P_STR_GATHER_STATS_CTL(''Y''); END;',
    start_date      => SYSTIMESTAMP,
    repeat_interval => 'FREQ=DAILY;BYHOUR=3;BYMINUTE=0;BYSECOND=0',
    enabled         => TRUE,
    auto_drop       => FALSE,
    comments        => 'Coleta baseada na tabela STARTUPADMIN.TAB_STATS_CONTROL (11g)'
  );
END;
/

-- EXECUTAR UM TESTE ---
BEGIN 
STARTUPADMIN.P_STR_GATHER_STATS_CTL('Y'); 
END; 
/

-- === 5) Consulta ===
SELECT owner, table_name, enabled, last_result, last_analyzed, stale_stats, last_run
FROM STARTUPADMIN.TAB_STATS_CONTROL
ORDER BY owner, table_name;


