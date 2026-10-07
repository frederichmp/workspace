
--
--
-- Oferece ao usuário o privilégio de extender a permissão a outros usuários
GRANT EXECUTE ON SYS.WDS_KILL_SES_INACTIVE to STARTUPADMIN WITH GRANT OPTION;




CREATE OR REPLACE PROCEDURE SYS.WDS_KILL_SES_INACTIVE IS
--
-- Verificar se procedure existe antes de criar ela.
-- Procedure para realizar o comando "alter system kill session"
-- Criar procedure com o usuário SYSDBA
-- Ao executar a procedure as sessões que se encaixem na query abaixo serão finalizadas
-- last_call_et -> Quanto tempo a sessão estava inativa em segundos na hora que foi finalizada
--
-- Autor: Wesley David Santos
-- Skype: wesleydavidsantos		
-- https://www.linkedin.com/in/wesleydavidsantos
--


	V_COUNT_RESULT NUMBER;	
	V_CMD   VARCHAR2 (100);
				
				
	CURSOR KILL_SESSIONS_INACTIVE
	   IS
		  SELECT
				S.INST_ID INST_ID,
				S.SID SID,
				S.SERIAL# SERIAL,
				S.USERNAME USERNAME,
				S.PROGRAM PROGRAM,
				S.LAST_CALL_ET LAST_CALL_ET
		  FROM 
				GV$SESSION S
		  WHERE 
				LAST_CALL_ET > 3600
				AND S.TYPE != 'BACKGROUND'
				AND S.STATUS IN ('INACTIVE')
				AND TYPE != 'BACKGROUND'
				AND USERNAME IS NOT NULL
				AND USERNAME NOT IN ('QS_CB','PERFSTAT','QS_ADM', 'SYSRAC',
						   'PM','SH','HR','OE',
						   'ODM_MTR','WKPROXY','ANONYMOUS',
						   'OWNER','SYS','SYSTEM','SCOTT',
						   'SYSMAN','XDB','DBSNMP','EXFSYS',
						   'OLAPSYS','MDSYS','WMSYS','WKSYS',
						   'DMSYS','ODM','EXFSYS','CTXSYS','LBACSYS',
						   'ORDPLUGINS','SQLTXPLAIN','OUTLN',
						   'TSMSYS','XS$NULL','TOAD','STREAM',
						   'SPATIAL_CSW_ADMIN','SPATIAL_WFS_ADMIN',
						   'SI_INFORMTN_SCHEMA','QS','QS_CBADM',
						   'QS_CS','QS_ES','QS_OS','QS_WS','PA_AWR_USER',
						   'OWBSYS_AUDIT','OWBSYS','ORDSYS','ORDDATA',
						   'ORACLE_OCM','MGMT_VIEW','MDDATA',
						   'FLOWS_FILES','FLASHBACK','AWRUSER',
						   'APPQOSSYS','APEX_PUBLIC_USER',
						   'APEX_030200','FLOWS_020100','STARTUPADMIN','ZABBIX','STARTUPMONITOR','STARTUP','PUBLIC', 'WDS_MONITORING')
				AND USERNAME NOT IN (
					'ACESSOPRD',
					'ACESSOAPISAE',
					'ACESSOCS',
					'ACESSOLOGISTICA',
					'ACESSOPORTARIA',
					'ACESSOPORTLAUDOS',
					'CARTORIO',
					'DBAAEC',
					'DBAMV',
					'DBAPS',
					'DBASGU',
					'DBATUALIZA',
					'DIAGNOSTICO_WS',
					'IDCE',
					'LICENSE_SERVICE',
					'MPACS',
					'MTPATOLOG',
					'MVAUTENTICADOR_CAS',
					'MVCONTROLESALA',
					'MVEDITOR',
					'MVGESTORFLUXO',
					'MVPAINEL',
					'MVPAINELRECEPCAO',
					'MVSACR',
					'MVTOTEMSENHA',
					'REMWEB',
					'REMWEB',
					'SOROTECA',
					'SOUL_INTEGRATED_SERVICES',
					'TISS');

				
				
				
		
BEGIN 
        DBMS_OUTPUT.PUT_LINE('INICIO KILL SESSION INACTIVE');
		DBMS_OUTPUT.PUT_LINE('');
		V_COUNT_RESULT:=0;
		
			-- INÍCIO KILL SESSIONS
			FOR KILL_SESSIONS_REC IN KILL_SESSIONS_INACTIVE
				LOOP
					
					DBMS_OUTPUT.PUT_LINE('-- ' || V_CMD);	
					
						BEGIN
						
							V_CMD := 'ALTER SYSTEM KILL SESSION '''||KILL_SESSIONS_REC.SID||','||KILL_SESSIONS_REC.SERIAL||',@'||KILL_SESSIONS_REC.INST_ID||''' IMMEDIATE';
							--
							-- Remova o comentário para ativar o KILL
							EXECUTE IMMEDIATE V_CMD;
							
						EXCEPTION
						WHEN OTHERS THEN
						
							DBMS_OUTPUT.PUT_LINE( SQLERRM );	
							
						END;
						
						
					V_COUNT_RESULT:=V_COUNT_RESULT+1;					
			
			END LOOP;
		
		
		DBMS_OUTPUT.PUT_LINE('--Sessions kill: ' || V_COUNT_RESULT);
		DBMS_OUTPUT.PUT_LINE('--Procedure kill_session is done');
		DBMS_OUTPUT.PUT_LINE('');		
		
END;			
/




BEGIN
    DBMS_SCHEDULER.CREATE_JOB (
            job_name => '"STARTUPADMIN"."JOB_WDS_KILL_SES_INACTIVE"',
            job_type => 'STORED_PROCEDURE',
            job_action => 'SYS.WDS_KILL_SES_INACTIVE',
            number_of_arguments => 0,
            start_date => TO_TIMESTAMP_TZ('2022-11-30 15:20:00.000000000 AMERICA/SAO_PAULO','YYYY-MM-DD HH24:MI:SS.FF TZR'),
            repeat_interval => 'FREQ=DAILY;BYTIME=0065959,115959,185959,235959',
            end_date => NULL,
            enabled => FALSE,
            auto_drop => FALSE,
            comments => 'Job criada pela Startup para matar todas as sessoes inativas com mais de 1hora');

         
     
 
    DBMS_SCHEDULER.SET_ATTRIBUTE( 
             name => '"STARTUPADMIN"."JOB_WDS_KILL_SES_INACTIVE"', 
             attribute => 'store_output', value => TRUE);
    DBMS_SCHEDULER.SET_ATTRIBUTE( 
             name => '"STARTUPADMIN"."JOB_WDS_KILL_SES_INACTIVE"', 
             attribute => 'logging_level', value => DBMS_SCHEDULER.LOGGING_OFF);
      
   
  
    
    DBMS_SCHEDULER.enable(
             name => '"STARTUPADMIN"."JOB_WDS_KILL_SES_INACTIVE"');
END;