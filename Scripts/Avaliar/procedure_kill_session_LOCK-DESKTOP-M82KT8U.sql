
--
--
-- Oferece ao usuário o privilégio de extender a permissão a outros usuários
GRANT EXECUTE ON SYS.WDS_KILL_SESSIONS_LOCK to STARTUPADMIN WITH GRANT OPTION;



--
-- Executar o comando abaixo para ativar o DBMS_OUTPUT
SET SERVEROUTPUT ON;


-- Verificar se a tabela existe antes de criar essa tabela
-- Tabela para armazenar os logs de KILL_SESSION realizados pelos usuários através da Procedure SYS.WDS_KILL_SESSIONS_LOCK
CREATE TABLE STARTUPADMIN.WDS_TBL_KILL_SESSIONS
( 
   ID NUMBER
  ,DATE_REGISTER DATE
  ,LAST_CALL_ET VARCHAR2(255)
  ,INST_ID NUMBER
  ,SID NUMBER
  ,SERIAL NUMBER
  ,MACHINE VARCHAR2(255)
  ,USERNAME VARCHAR2(255)
  ,MODULE VARCHAR2(255)
  ,PROGRAM VARCHAR2(255)
  ,OSUSER VARCHAR2(255)
  ,STATUS VARCHAR2(255)
  ,SQL_ID VARCHAR2(255)
);





CREATE TABLE STARTUPADMIN.WDS_TBL_SESSIONS_BLOCK
( 
   ID NUMBER
  ,DATE_REGISTER DATE
  ,LAST_CALL_ET VARCHAR2(255)
  ,INST_ID NUMBER
  ,SID NUMBER
  ,SERIAL NUMBER
  ,MACHINE VARCHAR2(255)
  ,USERNAME VARCHAR2(255)
  ,MODULE VARCHAR2(255)
  ,PROGRAM VARCHAR2(255)
  ,OSUSER VARCHAR2(255)
  ,STATUS VARCHAR2(255)
  ,SQL_ID VARCHAR2(255)
  ,INST_ID_LOCK NUMBER
  ,SID_LOCK NUMBER  
);






CREATE OR REPLACE PROCEDURE SYS.WDS_KILL_SESSIONS_LOCK IS
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

	V_LOG_ID NUMBER;
	V_COUNT_RESULT NUMBER;	
	V_CMD VARCHAR2 (100);
	
	
	v_STMT_INSERT_LOCK constant VARCHAR2(4000):= 'INSERT INTO STARTUPADMIN.WDS_TBL_KILL_SESSIONS 
																							( 
																								 ID
																								,DATE_REGISTER
																								,LAST_CALL_ET
																								,INST_ID
																								,SID
																								,SERIAL
																								,MACHINE
																								,USERNAME
																								,MODULE
																								,PROGRAM
																								,OSUSER
																								,STATUS
																								,SQL_ID
																							 ) 
																								VALUES 
																							 ( 
																								 :ID
																								,:DATE_REGISTER
																								,:LAST_CALL_ET
																								,:INST_ID
																								,:SID
																								,:SERIAL
																								,:MACHINE
																								,:USERNAME
																								,:MODULE
																								,:PROGRAM
																								,:OSUSER
																								,:STATUS
																								,:SQL_ID
																							 )';


	v_STMT_INSERT_BLOCK constant VARCHAR2(4000):= 'INSERT INTO STARTUPADMIN.WDS_TBL_SESSIONS_BLOCK 
																							( 
																								 ID
																								,DATE_REGISTER
																								,LAST_CALL_ET
																								,INST_ID
																								,SID
																								,SERIAL
																								,MACHINE
																								,USERNAME
																								,MODULE
																								,PROGRAM
																								,OSUSER
																								,STATUS
																								,SQL_ID
																								,INST_ID_LOCK
																								,SID_LOCK
																							 ) 
																								VALUES 
																							 ( 
																								 :ID
																								,:DATE_REGISTER
																								,:LAST_CALL_ET
																								,:INST_ID
																								,:SID
																								,:SERIAL
																								,:MACHINE
																								,:USERNAME
																								,:MODULE
																								,:PROGRAM
																								,:OSUSER
																								,:STATUS
																								,:SQL_ID
																								,:INST_ID_LOCK
																								,:SID_LOCK
																							 )';

	
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
				S.MODULE,
				S.STATUS,
				S.SQL_ID
		  FROM 
				GV$SESSION S
		  WHERE 
				LAST_CALL_ET > 900
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
				AND USERNAME NOT IN ('ACESSOAPISAE','ACESSOCS','ACESSOLOGISTICA','ACESSOPORTARIA','ACESSOPORTLAUDOS','CARTORIO','DBAAEC','DBAMV','DBAPS','DBASGU','DBATUALIZA','DIAGNOSTICO_WS','IDCE','LICENSE_SERVICE','MPACS','MTPATOLOG','MVAUTENTICADOR_CAS','MVCONTROLESALA','MVEDITOR','MVGESTORFLUXO','MVPAINEL','MVPAINELRECEPCAO','MVSACR','MVTOTEMSENHA','REMWEB','REMWEB','SOROTECA','SOUL_INTEGRATED_SERVICES','TIHFR','TISS','WESLEY_FERREIRA')
				AND (SID, INST_ID) IN ( SELECT BLOCKING_SESSION, FINAL_BLOCKING_INSTANCE FROM GV$SESSION WHERE BLOCKING_SESSION IS NOT NULL );
								
				
		
BEGIN 
        
		DBMS_OUTPUT.PUT_LINE('INICIO KILL SESSION LOCK');
		DBMS_OUTPUT.PUT_LINE('');
		V_COUNT_RESULT:=0;
		
		-- Gerador de código único
		SELECT EXTRACT(DAY FROM(SYS_EXTRACT_UTC(SYSTIMESTAMP) - TO_TIMESTAMP('1970-01-01', 'YYYY-MM-DD'))) * 86400000 + TO_NUMBER(TO_CHAR(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'SSSSSFF3')) INTO V_LOG_ID FROM DUAL;
		
		
			-- INÍCIO KILL SESSIONS
			FOR I IN KILL_SESSIONS_LOCK
				LOOP
					
					DBMS_OUTPUT.PUT_LINE('-- ' || V_CMD);	
					
						BEGIN
						
							-- Registra sessão que vai sofre o KILL
							EXECUTE IMMEDIATE v_STMT_INSERT_LOCK USING V_LOG_ID, SYSDATE, I.LAST_CALL_ET, I.INST_ID, I.SID, I.SERIAL, I.MACHINE, I.USERNAME, I.MODULE, I.PROGRAM, I.OSUSER, I.STATUS, I.SQL_ID;

							
							-- Pecorre os usuários que estão sofrendo com o lock
							FOR loop_LOCK in ( 
												SELECT
													LAST_CALL_ET,
													inst_id,
													sid,
													serial#,
													username,
													machine,
													osuser,
													module,
													client_info,
													status,
													blocking_session SID_LOCK,
													FINAL_BLOCKING_INSTANCE INST_ID_LOCK,
													event,
													sql_id
												FROM
													gv$session
												WHERE
													blocking_session = I.SID
													AND FINAL_BLOCKING_INSTANCE = I.INST_ID
													
											)
											LOOP
																								
											
											-- Registra as sessoes que estao sofrendo lock
											EXECUTE IMMEDIATE v_STMT_INSERT_BLOCK USING V_LOG_ID, SYSDATE, I.LAST_CALL_ET, I.INST_ID, I.SID, I.SERIAL, I.MACHINE, I.USERNAME, I.MODULE, I.PROGRAM, I.OSUSER, I.STATUS, I.SQL_ID, I.INST_ID, I.SID;
											
											
							END LOOP;
							
							
							
							COMMIT;
						
						
							V_CMD := 'ALTER SYSTEM KILL SESSION '''||I.SID||','||I.SERIAL||',@'||I.INST_ID||''' IMMEDIATE';
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



