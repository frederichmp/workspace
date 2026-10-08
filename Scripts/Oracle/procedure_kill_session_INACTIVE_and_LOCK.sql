
--
--
-- Oferece ao usuário o privilégio de extender a permissão a outros usuários
GRANT EXECUTE ON SYS.WDS_KILL_SESSIONS_INACTIVE to USERNAME_FOR_KILL WITH GRANT OPTION;



--
-- Executar o comando abaixo para ativar o DBMS_OUTPUT
SET SERVEROUTPUT ON;


-- Verificar se a tabela existe antes de criar essa tabela
-- Tabela para armazenar os logs de KILL_SESSION realizados pelos usuários através da Procedure SYS.WDS_KILL_SESSIONS_INACTIVE
CREATE TABLE STARTUPADMIN.WDS_TBL_KILL_SESSIONS
( 
  DATE_REGISTER DATE,
  LAST_CALL_ET VARCHAR2(255),
  INST_ID NUMBER,
  SID NUMBER,
  SERIAL NUMBER,  
  MACHINE VARCHAR2(255),
  USERNAME VARCHAR2(255),
  MODULE VARCHAR2(255),
  PROGRAM VARCHAR2(255),
  OSUSER VARCHAR2(255)
);






CREATE OR REPLACE PROCEDURE SYS.WDS_KILL_SESSIONS_INACTIVE IS
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
	
	
	v_STMT_INSERT constant VARCHAR2(4000):= 'INSERT INTO STARTUPADMIN.WDS_TBL_KILL_SESSIONS ( DATE_REGISTER, LAST_CALL_ET, INST_ID, SID, SERIAL, MACHINE, USERNAME, MODULE, PROGRAM, OSUSER ) VALUES ( :DATE_REGISTER, :LAST_CALL_ET, :INST_ID, :SID, :SERIAL, :MACHINE, :USERNAME, :MODULE, :PROGRAM, :OSUSER )';
	
	CURSOR KILL_SESSIONS_LOCK
	   IS
		  SELECT
				S.INST_ID INST_ID,
				S.SID SID,
				S.SERIAL# SERIAL,
				S.USERNAME USERNAME,
				S.PROGRAM PROGRAM,
				S.LAST_CALL_ET LAST_CALL_ET,
				S.MACHINE,
				S.OSUSER,
				S.MODULE
		  FROM 
				GV$SESSION S
		  WHERE 
				LAST_CALL_ET > 300
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
				AND USERNAME NOT IN ('ACESSOPRD','MPACS','IDCE','DBAMV','CARTORIO','REMWEB','MTPATOLOG')
				AND (SID, INST_ID) IN ( SELECT BLOCKING_SESSION, FINAL_BLOCKING_INSTANCE FROM GV$SESSION WHERE BLOCKING_SESSION IS NOT NULL );
								
				
				
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
						   'APEX_030200','FLOWS_020100','STARTUPADMIN','ZABBIX','STARTUPMONITOR','STARTUP','PUBLIC', 'WDS_MONITORING');
				
				
				
		
BEGIN 
        
		DBMS_OUTPUT.PUT_LINE('INICIO KILL SESSION LOCK');
		DBMS_OUTPUT.PUT_LINE('');
		V_COUNT_RESULT:=0;
		
			-- INÍCIO KILL SESSIONS
			FOR I IN KILL_SESSIONS_LOCK
				LOOP
					
					DBMS_OUTPUT.PUT_LINE('-- ' || V_CMD);	
					
						BEGIN
						
							-- Registra sessão que vai sofre o KILL
							EXECUTE IMMEDIATE v_STMT_INSERT USING SYSDATE, I.LAST_CALL_ET, I.INST_ID, I.SID, I.SERIAL, I.MACHINE, I.USERNAME, I.MODULE, I.PROGRAM, I.OSUSER;							
							COMMIT;
						
						
							V_CMD := 'ALTER SYSTEM KILL SESSION '''||I.SID||','||I.SERIAL||',@'||I.INST_ID||''' IMMEDIATE';
							--
							-- Remova o comentário para ativar o KILL
							-- EXECUTE IMMEDIATE V_CMD;
							
						EXCEPTION
						WHEN OTHERS THEN
						
							DBMS_OUTPUT.PUT_LINE( SQLERRM );	
							
						END;
						
						
					V_COUNT_RESULT:=V_COUNT_RESULT+1;
			
			END LOOP;
		
		
		DBMS_OUTPUT.PUT_LINE('--Sessions kill: ' || V_COUNT_RESULT);
		DBMS_OUTPUT.PUT_LINE('--Procedure kill_session is done');
		DBMS_OUTPUT.PUT_LINE('');
		
		
		
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
							-- EXECUTE IMMEDIATE V_CMD;
							
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



