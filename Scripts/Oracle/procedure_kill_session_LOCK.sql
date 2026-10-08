
--
--
-- Oferece ao usuário o privilégio de extender a permissão a outros usuários
GRANT EXECUTE ON SYS.WDS_KILL_SES_INACTIVE_LOCK to STARTUPADMIN WITH GRANT OPTION;



--
-- Executar o comando abaixo para ativar o DBMS_OUTPUT
SET SERVEROUTPUT ON;


-- Verificar se a tabela existe antes de criar essa tabela
-- Tabela para armazenar os logs de KILL_SESSION realizados pelos usuários através da Procedure SYS.WDS_KILL_SESSIONS_LOCK
CREATE TABLE STARTUPADMIN.WDS_TBL_SESSIONS_ISBLOCK
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





CREATE TABLE STARTUPADMIN.WDS_TBL_SESSIONS_BLOCKED
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



CREATE OR REPLACE PROCEDURE SYS.WDS_KILL_SES_INACTIVE_LOCK IS
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
	
	
	v_STMT_INSERT_LOCK constant VARCHAR2(4000):= 'INSERT INTO STARTUPADMIN.WDS_TBL_SESSIONS_ISBLOCK 
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


	v_STMT_INSERT_BLOCK constant VARCHAR2(4000):= 'INSERT INTO STARTUPADMIN.WDS_TBL_SESSIONS_BLOCKED 
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
						   'APEX_030200','FLOWS_020100','ZABBIX','STARTUPMONITOR','STARTUP','PUBLIC', 'WDS_MONITORING')
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
													serial# SERIAL,
													username,
													machine,
													osuser,
													module,
													program,
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
											EXECUTE IMMEDIATE v_STMT_INSERT_BLOCK USING V_LOG_ID, SYSDATE, loop_LOCK.LAST_CALL_ET, loop_LOCK.INST_ID, loop_LOCK.SID, loop_LOCK.SERIAL, loop_LOCK.MACHINE, loop_LOCK.USERNAME, loop_LOCK.MODULE, loop_LOCK.PROGRAM, loop_LOCK.OSUSER, loop_LOCK.STATUS, loop_LOCK.SQL_ID, I.INST_ID, I.SID;
											
											
							END LOOP;
							
							
							
							COMMIT;
						
						
							V_CMD := 'ALTER SYSTEM KILL SESSION '''||I.SID||','||I.SERIAL||',@'||I.INST_ID||''' IMMEDIATE';
				
			
							-- Monta o assunto e mensagem do e-mail
							DECLARE
								V_EMAIL_ASSUNTO VARCHAR2(200);
								V_EMAIL_MSG     VARCHAR2(4000);
							BEGIN
								V_EMAIL_ASSUNTO := '[ALERTA] Sessao em LOCK Identificada';
								V_EMAIL_MSG := '***ALERTA - UMA SESSAO FOI IDENTIFICADA POR LOCK NO SISTEMA***' || CHR(10) ||
											   'ABAIXO AS INFORMACOES:' || CHR(10) || CHR(10) ||
											   'Data Ocorrencia: ' || to_char(SYSDATE,'YYYY-MM-DD HH24:MI:SS') || CHR(10) ||
											   'Instancia: ' || I.INST_ID || CHR(10) ||
											   'Sid: ' || I.SID || CHR(10) ||
											   'Serial: ' || I.SERIAL || CHR(10) ||
											   'Usuario: ' || I.USERNAME || CHR(10) ||
											   'Usuario SO: ' || I.OSUSER || CHR(10) ||
											   'Maquina: ' || I.MACHINE || CHR(10) ||
											   'Modulo: ' || I.MODULE || CHR(10) ||
											   'Programa: ' || I.PROGRAM || CHR(10) ||
											   'Status: ' || I.STATUS || CHR(10) ||
											   'SQL_ID: ' || I.SQL_ID;

								STARTUPADMIN.PRC_ENVIA_EMAIL(V_EMAIL_ASSUNTO, V_EMAIL_MSG);
							END;

							--
							-- Remova o comentário para ativar o KILL
							--EXECUTE IMMEDIATE V_CMD;
							
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
            job_name => '"STARTUPADMIN"."JOB_WDS_KILL_SES_INACTIVE_LOCK"',
            job_type => 'STORED_PROCEDURE',
            job_action => 'SYS.WDS_KILL_SES_INACTIVE_LOCK',
            number_of_arguments => 0,
            start_date => TO_TIMESTAMP_TZ('2022-10-28 12:00:00.000000000 AMERICA/SAO_PAULO','YYYY-MM-DD HH24:MI:SS.FF TZR'),
            repeat_interval => 'FREQ=MINUTELY;INTERVAL=30',
            end_date => NULL,
            enabled => FALSE,
            auto_drop => FALSE,
            comments => 'Job criada pela Startup para matar todas as sessoes inativas com mais de 15 minutos travando alguem');

         
     
 
    DBMS_SCHEDULER.SET_ATTRIBUTE( 
             name => '"STARTUPADMIN"."JOB_WDS_KILL_SES_INACTIVE_LOCK"', 
             attribute => 'store_output', value => TRUE);
    DBMS_SCHEDULER.SET_ATTRIBUTE( 
             name => '"STARTUPADMIN"."JOB_WDS_KILL_SES_INACTIVE_LOCK"', 
             attribute => 'logging_level', value => DBMS_SCHEDULER.LOGGING_OFF);
      
   
  
    
    DBMS_SCHEDULER.enable(
             name => '"STARTUPADMIN"."JOB_WDS_KILL_SES_INACTIVE_LOCK"');
END;





CREATE OR REPLACE PROCEDURE STARTUPADMIN.PRC_ENVIA_EMAIL(
    p_assunto  IN VARCHAR2,
    p_mensagem IN VARCHAR2
)
AS
    vDE varchar2(50) := 'servicoscomp@startupnet.com.br';
    vPARA varchar2(50) := 'gustavo.tamietti.ext@vli-logistica.com.br';
    vSMTP varchar2(30) := 'smtp.office365.com';
    vPORTA number := 587;
    vWALLET_PATH CONSTANT VARCHAR2(500) := 'file:/u01/app/oracle/admin/acthmg/wallet/';
    vWALLET_PASSWORD CONSTANT VARCHAR2(500) := 'Wdscert123';
    vUSUAUTH varchar(100) := UTL_RAW.cast_to_varchar2(UTL_ENCODE.base64_encode(UTL_RAW.cast_to_raw('servicoscomp@startupnet.com.br')));
    vPASSAUTH varchar(30) := UTL_RAW.cast_to_varchar2(UTL_ENCODE.base64_encode(UTL_RAW.cast_to_raw('R=bLH?IeB~')));
    
    conn UTL_SMTP.CONNECTION;
    crlf VARCHAR2(2) := CHR(13) || CHR(10);
    mesg VARCHAR2(4000);
BEGIN
    conn := utl_smtp.open_connection(
        host => vSMTP,
        port => vPORTA,
        wallet_path => vWALLET_PATH,
        wallet_password => vWALLET_PASSWORD,
        secure_connection_before_smtp => false
    );

    utl_smtp.helo(conn, vSMTP);
    utl_smtp.starttls(conn);
    utl_smtp.helo(conn, vSMTP);

    UTL_SMTP.command(conn, 'AUTH LOGIN');
    UTL_SMTP.command(conn, vUSUAUTH);
    UTL_SMTP.command(conn, vPASSAUTH);

    utl_smtp.mail(conn, vDE);
    utl_smtp.rcpt(conn, vPARA);

    mesg := 'From: ' || vDE || crlf ||
            'Subject: ' || p_assunto || crlf ||
            'To: ' || vPARA || crlf ||
            crlf ||
            p_mensagem;

    utl_smtp.data(conn, mesg);
    utl_smtp.quit(conn);
END;
/