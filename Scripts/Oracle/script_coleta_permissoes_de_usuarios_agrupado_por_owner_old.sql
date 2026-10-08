SET SERVEROUTPUT ON;
SET TIMING ON;

set serveroutput on;            
exec DBMS_OUTPUT.ENABLE (buffer_size => NULL);


spool "C:\Users\WDS-Startup\Downloads\testes\permissoes.html"
set echo on;

DECLARE

DATA_ATUAL VARCHAR2(255); -- Nao Mexer - Flag usada para informa se existe GRANT para execuçao manual


	PROCEDURE LISTA_PERMISSAO( par_username VARCHAR2 )
	IS
		
		--name_user VARCHAR2(255) := '"'||par_username||'"'; -- Nao Mexer - Nome do usuário concatenado com aspas duplas
		
		-- Retorna a lista de permissÃµes
		CURSOR c_etlPERMISSOES IS
		WITH 
			TBL_LIST_PRIVILEGE_OBJECT AS (				  
				SELECT DISTINCT 
					OWNER, 
					PRIVILEGE
				FROM
				(
					SELECT DISTINCT 
						OWNER, PRIVILEGE
					FROM
						DBA_TAB_PRIVS
					WHERE 
						 GRANTEE = par_username
				)
			),
			TBL_LIST_PRIVILEGE_USER AS (
				select OWNER, PRIVILEGE from (
					select DISTINCT 
						'SISTEMA' AS OWNER,
						PRIVILEGE AS PRIVILEGE
					from 
						dba_sys_privs
					where grantee = UPPER( par_username )
				union all
					select DISTINCT
						OWNER,
						PRIVILEGE PRIVILEGE
					from 
						dba_tab_privs
					where grantee = UPPER( par_username )
				union all
					select 
						'ROLE' AS OWNER,
						 GRANTED_ROLE PRIVILEGE
					from 
						dba_role_privs
					where grantee = UPPER( par_username ))
			),
			TBL_UNION_GRANT AS (
				SELECT DISTINCT
					OWNER OWNER,
					PRIVILEGE PRIVILEGE
				FROM
					(
						SELECT
							OWNER OWNER,
							PRIVILEGE PRIVILEGE
						FROM
							TBL_LIST_PRIVILEGE_USER
						UNION ALL
						SELECT
							OWNER OWNER,
							PRIVILEGE PRIVILEGE
						FROM
							TBL_LIST_PRIVILEGE_OBJECT
					)
				ORDER BY OWNER, PRIVILEGE
			)
		SELECT
			OWNER,
			rtrim(xmlagg(XMLELEMENT(e,PRIVILEGE,', ').EXTRACT('//text()') ).GetClobVal(), ', ') PRIVILEGE
		FROM
			TBL_UNION_GRANT
		GROUP BY
           OWNER
		ORDER BY
			OWNER;
			
			
	BEGIN
	
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr><td colspan="2" align="center" class="name_user">' );	
		DBMS_OUTPUT.PUT_LINE( 'USER:  ' );	
		DBMS_OUTPUT.PUT_LINE( par_username );	
		DBMS_OUTPUT.PUT_LINE( '</td></tr>' );	
		
		DBMS_OUTPUT.PUT_LINE( '<tr><th>OWNER</th><th>PRIVILEGE</th></tr>' );	
		
	
		FOR I IN c_etlPERMISSOES
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' );
					DBMS_OUTPUT.PUT_LINE( I.OWNER ); 
				DBMS_OUTPUT.PUT_LINE( '</td>' );					
				
				DBMS_OUTPUT.PUT_LINE( '<td>' );
					DBMS_OUTPUT.PUT_LINE( I.PRIVILEGE ); 
				DBMS_OUTPUT.PUT_LINE( '</td>' );					
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		DBMS_OUTPUT.PUT_LINE( '</table>' );
		
		DBMS_OUTPUT.PUT_LINE( '<br /><br />' );
		
		
	END;
	
	
	PROCEDURE CATALOG_USERS
    IS	 
		-- Retorna a lista de permissÃµes
		CURSOR c_etlLISTA_USERS IS
			-- SELECT USERNAME FROM DBA_USERS WHERE USERNAME NOT IN ('SYS', 'SYSTEM') ORDER BY USERNAME ASC;
			SELECT USERNAME FROM DBA_USERS WHERE USERNAME NOT IN ('QS_CB','PERFSTAT','QS_ADM', 'SYSRAC',
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
									                               'APEX_030200','FLOWS_020100','STARTUPADMIN','ZABBIX','STARTUPMONITOR','STARTUP','PUBLIC')
												 AND  USERNAME IN (  COLOQUE_AQUI_A_LISTA_DE_USUÁRIOS_A_SEREM_PESQUISADOS  ) 
			ORDER BY USERNAME ASC;
		
	   
	BEGIN
		FOR U IN c_etlLISTA_USERS
			
		LOOP
		
			-- Chama a procedure de lista de permissoes
			LISTA_PERMISSAO(U.USERNAME);
		
		END LOOP;
		
	END;    
	
	
BEGIN

	SELECT TO_CHAR(sysdate, 'DD "de" fmMonth "de" YYYY','NLS_DATE_LANGUAGE=PORTUGUESE') || ' - ' || TO_CHAR(sysdate, 'HH24:MI:SS') INTO DATA_ATUAL FROM DUAL;

	DBMS_OUTPUT.PUT_LINE( '<!DOCTYPE html>' );
	DBMS_OUTPUT.PUT_LINE( '<html>' );
	DBMS_OUTPUT.PUT_LINE( '<head>' );
	DBMS_OUTPUT.PUT_LINE( '<style> #customers { font-family: "Trebuchet MS", Arial, Helvetica, sans-serif; border-collapse: collapse; width: 100%; } #customers td, #customers th { border: 1px solid #ddd; padding: 8px; } #customers tr:nth-child(even){background-color: #f2f2f2;} #customers tr:hover {background-color: #ddd;} #customers th { padding-top: 12px; padding-bottom: 12px; text-align: left; background-color: #4CAF50; color: white; } .header { padding: 60px; text-align: center; background: #1abc9c; color: white; font-size: 30px; } .name_user { background-color: blue; color: #fff; font-weight: bold; font-size: 30px; }</style>' );
	DBMS_OUTPUT.PUT_LINE( '</head>' );
	DBMS_OUTPUT.PUT_LINE( '<body>' );
	
	DBMS_OUTPUT.PUT_LINE( '<div class="header">' );
	  DBMS_OUTPUT.PUT_LINE( '<h1>Startup - Dados e Sistemas</h1>' );
	  DBMS_OUTPUT.PUT_LINE( '<p>Relatório: Lista de permissoes dos usuários</p>' );
	  DBMS_OUTPUT.PUT_LINE( '<p style="font-size: 20px;">DBA: Nome do DBA que gerou o relatório</p>' );
	DBMS_OUTPUT.PUT_LINE( '</div>' );
	
	
	-- Chama a procedure para catalogar os usuários a serem listados
	CATALOG_USERS;
	
	
	DBMS_OUTPUT.PUT_LINE( '<div>' );
		DBMS_OUTPUT.PUT_LINE( '<p>' );
			DBMS_OUTPUT.PUT_LINE( 'Belo Horizonte, ' );
			DBMS_OUTPUT.PUT_LINE( DATA_ATUAL );
		DBMS_OUTPUT.PUT_LINE( '</p>' );
	DBMS_OUTPUT.PUT_LINE( '</div>' );
	
	
	DBMS_OUTPUT.PUT_LINE( '</body>' );
	DBMS_OUTPUT.PUT_LINE( '</html>' );	
	
END;
/



spool off
set serveroutput off;
set echo off;