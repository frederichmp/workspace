-----------------------------------------------------------------------------------------------------------------------
------ COMO USAR ------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------
-- 1º - Alterar o caminho onde o relatório será criado
--		# Você altera no comando "spool"
--
-- 2 º - Alterar o valor das variáveis 
-- 		# NOME_CLIENTE VARCHAR2(255) :='Nome do Cliente'; -- Nome do Cliente
-- 		# NOME_BANCO_DE_DADOS VARCHAR2(255) :='PRDMV';
-- 		# NOME_DBA VARCHAR2(255) :=' Nome do DBA que Gerou o Relatório'; -- Nome do DBA que Gerou o Relatório
-- 		# TIPO_BANCO_DE_DADOS VARCHAR2(255) :='PRODUÇÃO'; -- PRODUÇÃO / HOMOLOGAÇÃO / SIMULAÇÃO
--
-- 3º - Dentro do Developer, selecionar todo o Script e mandar executar
-- 4º - Quando o relatório for gerado, abra ele com o Notepad e apague a linha número 01 até <!DOCTYPE html> e depois apague todas as linhas abaixo de </html>
-----------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------

SET HEAD ON;
SET FEED ON;
SET TERM OFF;
SET TRIMSPOOL ON;
SET TRIMOUT ON;
SET WRAP OFF;
SET TERMOUT OFF;
SET SERVEROUTPUT ON;
SET TIMING ON;

set serveroutput on;            
exec DBMS_OUTPUT.ENABLE (buffer_size => NULL);


spool "CAMINHO_GRAVAR_REPORT\nome_do_report.html"
set echo on;

DECLARE
	-- CREATE_REPORT_WDS
	
	
	-- Variáveis Editáveis
	NOME_DBA VARCHAR2(255) :='Nome do DBA que Gerou o Relatório'; -- Nome do DBA que Gerou o Relatório
	NOME_CLIENTE VARCHAR2(255) :='Nome do Cliente'; -- Nome do Cliente
	NOME_BANCO_DE_DADOS VARCHAR2(255) :='PRDMV';
	TIPO_BANCO_DE_DADOS VARCHAR2(255) :='PRODUÇÃO'; -- PRODUÇÃO / HOMOLOGAÇÃO / SIMULAÇÃO
	
	
	-- Variáveis não editáveis
	DATA_ATUAL VARCHAR2(255); -- Nao Mexer - Flag usada para informa se existe GRANT para execuçao manual
	DATE_YESTERDAY VARCHAR2(255); -- Nao Mexer - Flag usada para informa se existe GRANT para execuçao manual
	
	-- Gráfico da lista os objetos por usuário
	PROCEDURE LIST_OBJECT_USER_GRAF
	IS
		CURSOR c_SQL IS SELECT COUNT(OBJECT_TYPE) COUNT_OBJ, OWNER FROM DBA_OBJECTS group by OWNER, OWNER order by owner;
		
	BEGIN
		
		DBMS_OUTPUT.PUT_LINE( '<script>' );
		
			DBMS_OUTPUT.PUT_LINE( 'function LIST_OBJECT_USER_GRAF(){' );

				DBMS_OUTPUT.PUT_LINE( 'var tabela = new google.visualization.DataTable();' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("string","OWNER"); ');
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("number","QUANTIDADE");' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addRows([' );
			
				FOR I IN c_SQL
				LOOP
					
					DBMS_OUTPUT.PUT_LINE( '["' || I.OWNER || '",' || I.COUNT_OBJ || '],' );		
				
				END LOOP;
			
			DBMS_OUTPUT.PUT_LINE( ']);' );

				DBMS_OUTPUT.PUT_LINE( 'var grafico = new google.visualization.PieChart(document.getElementById("graf_LIST_OBJECT_USER_GRAF"));' );
				DBMS_OUTPUT.PUT_LINE( 'grafico.draw(tabela);' );
			DBMS_OUTPUT.PUT_LINE( '}' );
			
		
		DBMS_OUTPUT.PUT_LINE( '</script>' );
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
			DBMS_OUTPUT.PUT_LINE( '<tr><th>Gráfico com quantidade de objetos por usuário</th></tr>' );
			DBMS_OUTPUT.PUT_LINE( '<tr><td><div id="graf_LIST_OBJECT_USER_GRAF"></div></td></tr>' );
		DBMS_OUTPUT.PUT_LINE( '<table>' );
						
		
	END;
	
	-- Lista os objetos por usuário
	PROCEDURE LIST_OBJECT_USER
	IS
		CURSOR c_SQL IS SELECT COUNT(OBJECT_TYPE) COUNT_OBJ, OBJECT_TYPE, OWNER FROM DBA_OBJECTS group by OBJECT_TYPE, OWNER order by owner;
		
	BEGIN
	
		-- Chamada do gráfico
		LIST_OBJECT_USER_GRAF;
		
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">COUNT_OBJ</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">OBJECT_TYPE</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">OWNER</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.COUNT_OBJ || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.OBJECT_TYPE || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.OWNER || '</td>' );
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		DBMS_OUTPUT.PUT_LINE( '</table>' );
				
	END;
	
	
	-- Gráfico da lista os job inválidos do últimos 7 dias
	PROCEDURE LIST_JOB_FAILED_GRAF
	IS
		CURSOR c_SQL IS 
					SELECT
						COUNT(JOB_NAME) COUNT_EXECUTION,
						REQ_START_DATE
					FROM
						(
							SELECT
								JOB_NAME,
								TO_CHAR(REQ_START_DATE, 'DD-MM-YYYY') REQ_START_DATE
							FROM 
								ALL_SCHEDULER_JOB_RUN_DETAILS
							WHERE 
								STATUS != 'SUCCEEDED'
								AND TO_CHAR(REQ_START_DATE, 'YYYY-MM-DD') > TO_CHAR((SYSDATE -7), 'YYYY-MM-DD')
								AND TO_CHAR(REQ_START_DATE, 'YYYY-MM-DD') <= TO_CHAR((SYSDATE -1), 'YYYY-MM-DD')
						)
					GROUP BY 
						REQ_START_DATE
					ORDER BY REQ_START_DATE DESC;
		
	BEGIN
		
		DBMS_OUTPUT.PUT_LINE( '<script>' );
		
			DBMS_OUTPUT.PUT_LINE( 'function LIST_JOB_FAILED_GRAF(){' );

				DBMS_OUTPUT.PUT_LINE( 'var tabela = new google.visualization.DataTable();' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("string","DATA"); ');
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("number","FALHAS");' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addRows([' );
			
				FOR I IN c_SQL
				LOOP
					
					DBMS_OUTPUT.PUT_LINE( '["' || I.REQ_START_DATE || '",' || I.COUNT_EXECUTION || '],' );		
				
				END LOOP;
			
			DBMS_OUTPUT.PUT_LINE( ']);' );

				DBMS_OUTPUT.PUT_LINE( 'var grafico = new google.visualization.PieChart(document.getElementById("graf_LIST_JOB_FAILED_GRAF"));' );
				DBMS_OUTPUT.PUT_LINE( 'grafico.draw(tabela);' );
			DBMS_OUTPUT.PUT_LINE( '}' );
			
		
		DBMS_OUTPUT.PUT_LINE( '</script>' );
		
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
			DBMS_OUTPUT.PUT_LINE( '<tr><th>Gráfico com histórico dos últimos 7 dias</th></tr>' );
			DBMS_OUTPUT.PUT_LINE( '<tr><td><div id="graf_LIST_JOB_FAILED_GRAF"></div></td></tr>' );
		DBMS_OUTPUT.PUT_LINE( '<table>' );
				
		
	END;
	
	-- Lista os JOBS com falha do dia anterior
	PROCEDURE LIST_JOB_FAILED
	IS
		CURSOR c_SQL IS 
				SELECT
					COUNT(*) COUNT_EXECUTION,
					OWNER , 
					JOB_NAME,
					STATUS,
					ADDITIONAL_INFO 
				FROM 
					ALL_SCHEDULER_JOB_RUN_DETAILS
				WHERE 
					STATUS != 'SUCCEEDED'
					AND TO_CHAR(REQ_START_DATE, 'YYYY-MM-DD') = TO_CHAR((SYSDATE -1), 'YYYY-MM-DD')
				GROUP BY 
					OWNER , 
					JOB_NAME,
					STATUS,
					ADDITIONAL_INFO
				ORDER BY OWNER DESC;
		
	BEGIN
	
		-- Chamada do gráfico
		LIST_JOB_FAILED_GRAF;
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">COUNT_EXECUTION</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">OWNER</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">JOB_NAME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">STATUS</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">ADDITIONAL_INFO</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.COUNT_EXECUTION || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.OWNER || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.JOB_NAME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.STATUS || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.ADDITIONAL_INFO || '</td>' );
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		  DBMS_OUTPUT.PUT_LINE( '</table>' );
			 
	END;
	
	-- Gráfico da lista os objetos inválidos por tipo
	PROCEDURE LIST_OBJECT_INVALID_GRAF
	IS
		CURSOR c_SQL IS
					SELECT
						COUNT(OBJECT_TYPE) COUNT_OBJ_INVALID,
						OBJECT_TYPE
					FROM
						DBA_OBJECTS
					WHERE
						STATUS = 'INVALID'
					GROUP BY
						OBJECT_TYPE
					ORDER BY
						OBJECT_TYPE;
		
	BEGIN
		
		DBMS_OUTPUT.PUT_LINE( '<script>' );
		
			DBMS_OUTPUT.PUT_LINE( 'function LIST_OBJECT_INVALID_GRAF(){' );

				DBMS_OUTPUT.PUT_LINE( 'var tabela = new google.visualization.DataTable();' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("string","OBJECT_TYPE"); ');
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("number","QUANTIDADE");' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addRows([' );
			
				FOR I IN c_SQL
				LOOP
					
					DBMS_OUTPUT.PUT_LINE( '["' || I.OBJECT_TYPE || '",' || I.COUNT_OBJ_INVALID || '],' );		
				
				END LOOP;
			
			DBMS_OUTPUT.PUT_LINE( ']);' );

				DBMS_OUTPUT.PUT_LINE( 'var grafico = new google.visualization.BarChart(document.getElementById("graf_LIST_OBJECT_INVALID_GRAF"));' );
				DBMS_OUTPUT.PUT_LINE( 'grafico.draw(tabela);' );
			DBMS_OUTPUT.PUT_LINE( '}' );
									
		
		DBMS_OUTPUT.PUT_LINE( '</script>' );
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
			DBMS_OUTPUT.PUT_LINE( '<tr><th>Gráfico com objetos inválidos por tipo</th></tr>' );
			DBMS_OUTPUT.PUT_LINE( '<tr><td><div id="graf_LIST_OBJECT_INVALID_GRAF"></div></td></tr>' );
		DBMS_OUTPUT.PUT_LINE( '<table>' );
		
		
	END;
	
	-- Lista de objetos inválidos
	PROCEDURE LIST_OBJECT_INVALID
	IS
		CURSOR c_SQL IS 
				SELECT
					COUNT(OBJECT_TYPE) COUNT_OBJ_INVALID,
					OBJECT_TYPE,
					OWNER
				FROM
					DBA_OBJECTS
				WHERE
					STATUS = 'INVALID'
				GROUP BY
					OBJECT_TYPE,
					OWNER
				ORDER BY
					OWNER;
		
	BEGIN
	
		-- Chamada do gráfico
		LIST_OBJECT_INVALID_GRAF;
		
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">COUNT_OBJ_INVALID</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">OBJECT_TYPE</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">OWNER</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.COUNT_OBJ_INVALID || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.OBJECT_TYPE || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.OWNER || '</td>' );
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		  DBMS_OUTPUT.PUT_LINE( '</table>' );
			 
	END;
	
	-- Gráfico da lista os job inválidos do últimos 7 dias
	PROCEDURE LIST_COUNT_USER_STATUS_GRAF
	IS
		CURSOR c_SQL IS SELECT COUNT(*) COUNT_USERS, ACCOUNT_STATUS FROM DBA_USERS GROUP BY ACCOUNT_STATUS ORDER BY ACCOUNT_STATUS;
		
	BEGIN
		
		DBMS_OUTPUT.PUT_LINE( '<script>' );
		
			DBMS_OUTPUT.PUT_LINE( 'function LIST_COUNT_USER_STATUS_GRAF(){' );

				DBMS_OUTPUT.PUT_LINE( 'var tabela = new google.visualization.DataTable();' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("string","STATUS"); ');
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("number","USERS");' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addRows([' );
			
				FOR I IN c_SQL
				LOOP
					
					DBMS_OUTPUT.PUT_LINE( '["' || I.ACCOUNT_STATUS || '",' || I.COUNT_USERS || '],' );		
				
				END LOOP;
			
			DBMS_OUTPUT.PUT_LINE( ']);' );

				DBMS_OUTPUT.PUT_LINE( 'var grafico = new google.visualization.PieChart(document.getElementById("graf_LIST_COUNT_USER_STATUS_GRAF"));' );
				DBMS_OUTPUT.PUT_LINE( 'grafico.draw(tabela);' );
			DBMS_OUTPUT.PUT_LINE( '}' );
			
		
		DBMS_OUTPUT.PUT_LINE( '</script>' );
		
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
			DBMS_OUTPUT.PUT_LINE( '<tr><th>Gráfico quantidade de usuários por status</th></tr>' );
			DBMS_OUTPUT.PUT_LINE( '<tr><td><div id="graf_LIST_COUNT_USER_STATUS_GRAF"></div></td></tr>' );
		DBMS_OUTPUT.PUT_LINE( '<table>' );
				
		
	END;
	
	-- Lista de quantidade de usuários pelo Status
	PROCEDURE LIST_COUNT_USER_STATUS
	IS
		CURSOR c_SQL IS SELECT COUNT(*) COUNT_USERS, ACCOUNT_STATUS FROM DBA_USERS GROUP BY ACCOUNT_STATUS ORDER BY ACCOUNT_STATUS;
		
	BEGIN
	
		-- Chamada do gráfico
		LIST_COUNT_USER_STATUS_GRAF;
		
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">COUNT_USERS</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">ACCOUNT_STATUS</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.COUNT_USERS || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.ACCOUNT_STATUS || '</td>' );
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		  DBMS_OUTPUT.PUT_LINE( '</table>' );
			 
	END;
	
	-- Lista de usuários com privilégio de DBA
	PROCEDURE LIST_USER_DBA
	IS
		CURSOR c_SQL IS SELECT GRANTEE, GRANTED_ROLE FROM dba_role_privs where GRANTED_ROLE = 'DBA' ORDER BY GRANTEE;
		
	BEGIN
			
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">USER</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">PRIVILEGE</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.GRANTEE || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.GRANTED_ROLE || '</td>' );
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		  DBMS_OUTPUT.PUT_LINE( '</table>' );
			 
	END;
	
	-- Gráfico da lista os job inválidos do últimos 7 dias
	PROCEDURE LIST_TRIGGER_DISABLED_GRAF
	IS
		CURSOR c_SQL IS SELECT COUNT(*) COUNT_TRIGGER_DISABLED, TABLE_OWNER FROM   DBA_TRIGGERS WHERE  STATUS = 'DISABLED' GROUP BY TABLE_OWNER ORDER BY TABLE_OWNER;
		
	BEGIN
		
		DBMS_OUTPUT.PUT_LINE( '<script>' );
		
			DBMS_OUTPUT.PUT_LINE( 'function LIST_TRIGGER_DISABLED_GRAF(){' );

				DBMS_OUTPUT.PUT_LINE( 'var tabela = new google.visualization.DataTable();' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("string","TABLE OWNER"); ');
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("number","COUNT");' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addRows([' );
			
				FOR I IN c_SQL
				LOOP
					
					DBMS_OUTPUT.PUT_LINE( '["' || I.TABLE_OWNER || '",' || I.COUNT_TRIGGER_DISABLED || '],' );		
				
				END LOOP;
			
			DBMS_OUTPUT.PUT_LINE( ']);' );

				DBMS_OUTPUT.PUT_LINE( 'var grafico = new google.visualization.BarChart(document.getElementById("graf_LIST_TRIGGER_DISABLED_GRAF"));' );
				DBMS_OUTPUT.PUT_LINE( 'grafico.draw(tabela);' );
			DBMS_OUTPUT.PUT_LINE( '}' );
			
		
		DBMS_OUTPUT.PUT_LINE( '</script>' );
		
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
			DBMS_OUTPUT.PUT_LINE( '<tr><th>Gráfico quantidade trigger desabilitada por usuário</th></tr>' );
			DBMS_OUTPUT.PUT_LINE( '<tr><td><div id="graf_LIST_TRIGGER_DISABLED_GRAF"></div></td></tr>' );
		DBMS_OUTPUT.PUT_LINE( '<table>' );
				
		
	END;
	
	-- Lista de trigger desabilitadas
	PROCEDURE LIST_TRIGGER_DISABLED
	IS
		CURSOR c_SQL IS SELECT TRIGGER_NAME, TABLE_OWNER, TABLE_NAME, STATUS FROM ALL_TRIGGERS WHERE  STATUS = 'DISABLED' ORDER BY TABLE_OWNER;
		
	BEGIN
	
		-- Chamada do gráfico
		LIST_TRIGGER_DISABLED_GRAF;
			
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">TRIGGER NAME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">TABLE OWNER</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">TABLE NAME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">STATUS</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.TRIGGER_NAME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.TABLE_OWNER || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.TABLE_NAME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.STATUS || '</td>' );
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		  DBMS_OUTPUT.PUT_LINE( '</table>' );
			 
	END;
	
	-- Total recursos utilizados
	PROCEDURE LIST_RESOURCE_LIMIT
	IS

		CURSOR c_SQL IS select resource_name, current_utilization, max_utilization, limit_value from v$resource_limit where resource_name in ('sessions', 'processes');
		
	BEGIN
			
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">RESOURCE NAME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">CURRENT UTILIZATION</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">MAX UTILIZATION</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">LIMIT VALUE</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.RESOURCE_NAME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.CURRENT_UTILIZATION || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.MAX_UTILIZATION || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.LIMIT_VALUE || '</td>' );
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		  DBMS_OUTPUT.PUT_LINE( '</table>' );
			 
	END;
	
	-- Querys com alto consumo
	PROCEDURE TOP_QUERY
	IS
		CURSOR c_SQL IS 
			SELECT USERNAME,
			   BUFFER_GETS,
			   DISK_READS,
			   EXECUTIONS,
			   BUFFER_GET_PER_EXEC,
			   PARSE_CALLS,
			   SORTS,
			   ROWS_PROCESSED,
			   HIT_RATIO,
			   CPU_TIME,
			   ELAPSED_TIME,
			   USER_IO_WAIT_TIME,
			   MODULE,
			   SQL_ID,
			   SQL_TEXT   
			FROM (SELECT 
					   SQL_TEXT,
					   SQL_ID,					   
					   B.USERNAME,
					   A.DISK_READS,
					   A.BUFFER_GETS,
					   CASE A.EXECUTIONS
						WHEN 0 THEN 
							TRUNC(A.BUFFER_GETS)
						ELSE
							TRUNC(A.BUFFER_GETS / A.EXECUTIONS)
						END BUFFER_GET_PER_EXEC,
					   A.PARSE_CALLS,
					   A.SORTS,
					   A.EXECUTIONS,
					   A.ROWS_PROCESSED,
					   100 - ROUND (100 * A.DISK_READS / A.BUFFER_GETS, 2) HIT_RATIO,
					   MODULE,
					   CPU_TIME, ELAPSED_TIME, USER_IO_WAIT_TIME
				 FROM 
					   GV$SQLAREA A, DBA_USERS B
				 WHERE 
				   A.PARSING_USER_ID = B.USER_ID
				   AND B.USERNAME NOT IN ('SYS', 'SYSTEM', 'WDS')
				   AND A.BUFFER_GETS > 10000
				   --AND SQL_TEXT NOT LIKE '%CREATE_REPORT_WDS%'
				 ORDER BY A.DISK_READS DESC)
			 WHERE ROWNUM <= 50;
		
	BEGIN
			
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">USERNAME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">BUFFER GETS</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">DISK READS</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">EXECUTIONS</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">BUFFER GET PER EXEC</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">PARSE CALLS</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">SORTS</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">ROWS PROCESSED</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">HIT RATIO</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">CPU_TIME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">ELAPSED TIME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">USER_IO_WAIT_TIME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">MODULE</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">SQL_ID</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">SQL TEXT</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.USERNAME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.BUFFER_GETS || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.DISK_READS || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.EXECUTIONS || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.BUFFER_GET_PER_EXEC || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.PARSE_CALLS || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.SORTS || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.ROWS_PROCESSED || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.HIT_RATIO || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.CPU_TIME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.ELAPSED_TIME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.USER_IO_WAIT_TIME || '</td>' );				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.MODULE || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.SQL_ID || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.SQL_TEXT || '</td>' );				

			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		  DBMS_OUTPUT.PUT_LINE( '</table>' );
			 
	END;
	
	-- Gráfico tamanho do banco de dados
	PROCEDURE SIZE_DATABASE_GRAF
	IS
		-- Variáveis com os resultados
    	var_DATA_FILE_MB VARCHAR2(100);
		var_TEMP_FILE_MB VARCHAR2(100);
		var_LOG_FILE_MB VARCHAR2(100);
		var_CONTROL_FILE_MB VARCHAR2(100);
		
	BEGIN
		WITH
			DBF AS (
				SELECT TRUNC(SUM(BYTES/1024/1024)) DATA_FILE_MB FROM V$DATAFILE        
			),
			TMPDBF AS (
				SELECT TRUNC(SUM(BYTES/1024/1024)) TEMP_FILE_MB FROM V$TEMPFILE        
			),
			LGF AS (
				SELECT TRUNC(SUM(BYTES/1024/1024)) LOG_FILE_MB FROM V$LOG L, V$LOGFILE LF WHERE L.GROUP# = LF.GROUP#       
			),
			CTL AS (
				SELECT TRUNC(SUM(BLOCK_SIZE*FILE_SIZE_BLKS/1024/1024)) CONTROL_FILE_MB FROM V$CONTROLFILE
			)
		SELECT
			DATA_FILE_MB,
			TEMP_FILE_MB,
			LOG_FILE_MB,
			CONTROL_FILE_MB 
				INTO var_DATA_FILE_MB, var_TEMP_FILE_MB, var_LOG_FILE_MB, var_CONTROL_FILE_MB
		FROM
			DBF,
			TMPDBF,
			LGF,
			CTL;
			
		
		DBMS_OUTPUT.PUT_LINE( '<script>' );
		
			DBMS_OUTPUT.PUT_LINE( 'function SIZE_DATABASE_GRAF(){' );

				DBMS_OUTPUT.PUT_LINE( 'var tabela = new google.visualization.DataTable();' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("string","TIPO"); ');
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("number","TAMANHO");' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addRows([' );
			
				-- Tamanho database
				DBMS_OUTPUT.PUT_LINE( '["DATA_FILE_MB",'    || var_DATA_FILE_MB    || '],' );
				DBMS_OUTPUT.PUT_LINE( '["TEMP_FILE_MB",'    || var_TEMP_FILE_MB    || '],' );
				DBMS_OUTPUT.PUT_LINE( '["LOG_FILE_MB",'     || var_LOG_FILE_MB     || '],' );
				DBMS_OUTPUT.PUT_LINE( '["CONTROL_FILE_MB",' || var_CONTROL_FILE_MB || ']' );	
							
			DBMS_OUTPUT.PUT_LINE( ']);' );

				DBMS_OUTPUT.PUT_LINE( 'var grafico = new google.visualization.ColumnChart(document.getElementById("graf_SIZE_DATABASE_GRAF"));' );
				DBMS_OUTPUT.PUT_LINE( 'grafico.draw(tabela);' );
			DBMS_OUTPUT.PUT_LINE( '}' );
			
		
		DBMS_OUTPUT.PUT_LINE( '</script>' );
		
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
			DBMS_OUTPUT.PUT_LINE( '<tr><th>Gráfico tamanho do banco de dados</th></tr>' );
			DBMS_OUTPUT.PUT_LINE( '<tr><td><div id="graf_SIZE_DATABASE_GRAF"></div></td></tr>' );
		DBMS_OUTPUT.PUT_LINE( '<table>' );
				
		
	END;
	
	-- Tamanho do banco de dados
	PROCEDURE SIZE_DATABASE
	IS
		CURSOR c_SQL IS 
					WITH
						DBF AS (
							SELECT TRUNC(SUM(BYTES/1024/1024)) DATA_FILE_MB FROM V$DATAFILE        
						),
						TMPDBF AS (
							SELECT TRUNC(SUM(BYTES/1024/1024)) TEMP_FILE_MB FROM V$TEMPFILE        
						),
						LGF AS (
							SELECT TRUNC(SUM(BYTES/1024/1024)) LOG_FILE_MB FROM V$LOG L, V$LOGFILE LF WHERE L.GROUP# = LF.GROUP#       
						),
						CTL AS (
							SELECT TRUNC(SUM(BLOCK_SIZE*FILE_SIZE_BLKS/1024/1024)) CONTROL_FILE_MB FROM V$CONTROLFILE
						)
					SELECT
						DATA_FILE_MB,
						TEMP_FILE_MB,
						LOG_FILE_MB,
						CONTROL_FILE_MB
					FROM
						DBF,
						TMPDBF,
						LGF,
						CTL;
		
	BEGIN
	
		-- Chamada do gráfico
		SIZE_DATABASE_GRAF;
			
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">DATA_FILE_MB</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">TEMP_FILE_MB</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">LOG_FILE_MB</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">CONTROL_FILE_MB</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.DATA_FILE_MB || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.TEMP_FILE_MB || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.LOG_FILE_MB || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.CONTROL_FILE_MB || '</td>' );
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		  DBMS_OUTPUT.PUT_LINE( '</table>' );
			 
	END;
	
	
	-- Gráfico por tablespace
	PROCEDURE SIZE_TABLESPACE_GRAF
	IS
		CURSOR c_SQL IS 
					SELECT
						TABLESPACE_NAME,
						REPLACE(TOTAL,',','.') TOTAL
					FROM
						(
							SELECT
								A.TABLESPACE_NAME TABLESPACE_NAME,
								TOTAL
							FROM
								(
									SELECT
										TABLESPACE_NAME,
										TRUNC((SUM(BYTES) / 1024 / 1024),2) TOTAL
									FROM
										DBA_DATA_FILES
									GROUP BY
										TABLESPACE_NAME
								) A
								LEFT OUTER JOIN (
									SELECT
										TABLESPACE_NAME,
										TRUNC((SUM(BYTES) / 1024 / 1024),2) FREE
									FROM
										DBA_FREE_SPACE
									GROUP BY
										TABLESPACE_NAME
								) B ON A.TABLESPACE_NAME = B.TABLESPACE_NAME
							ORDER BY
								TOTAL DESC
						)
					WHERE
						ROWNUM < 6;
		
	BEGIN
		
		DBMS_OUTPUT.PUT_LINE( '<script>' );
		
			DBMS_OUTPUT.PUT_LINE( 'function SIZE_TABLESPACE_GRAF(){' );

				DBMS_OUTPUT.PUT_LINE( 'var tabela = new google.visualization.DataTable();' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("string","TABLESPACE NAME"); ');
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("number","TOTAL");' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addRows([' );
			
				FOR I IN c_SQL
				LOOP
					
					DBMS_OUTPUT.PUT_LINE( '["' || I.TABLESPACE_NAME || '",' || I.TOTAL || '],' );		
				
				END LOOP;
			
			DBMS_OUTPUT.PUT_LINE( ']);' );

				DBMS_OUTPUT.PUT_LINE( 'var grafico = new google.visualization.ColumnChart(document.getElementById("graf_SIZE_TABLESPACE_GRAF"));' );
				DBMS_OUTPUT.PUT_LINE( 'grafico.draw(tabela);' );
			DBMS_OUTPUT.PUT_LINE( '}' );
			
		
		DBMS_OUTPUT.PUT_LINE( '</script>' );
		
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
			DBMS_OUTPUT.PUT_LINE( '<tr><th>Gráfico tamanho por tablespace, TOP 5</th></tr>' );
			DBMS_OUTPUT.PUT_LINE( '<tr><td><div id="graf_SIZE_TABLESPACE_GRAF"></div></td></tr>' );
		DBMS_OUTPUT.PUT_LINE( '<table>' );
				
		
	END;
	
	
	-- Tamanho por tablespace
	PROCEDURE SIZE_TABLESPACE
	IS
		CURSOR c_SQL IS 
					SELECT
						A.TABLESPACE_NAME TABLESPACE_NAME,
						NVL(B.FREE, 0.0) "MBS_LIVRES",
						A.TOTAL TOTAL,
						(100 - TRUNC(NVL(B.FREE, 0.0) / A.TOTAL * 1000) / 10) PRC
					FROM
						(
							SELECT
								TABLESPACE_NAME,
								SUM(BYTES) / 1024 / 1024 TOTAL
							FROM
								DBA_DATA_FILES
							GROUP BY
								TABLESPACE_NAME
						) A
						LEFT OUTER JOIN (
							SELECT
								TABLESPACE_NAME,
								SUM(BYTES) / 1024 / 1024 FREE
							FROM
								DBA_FREE_SPACE
							GROUP BY
								TABLESPACE_NAME
						) B ON A.TABLESPACE_NAME = B.TABLESPACE_NAME
					ORDER BY
						PRC DESC;
		
	BEGIN
	
		-- Chamada do gráfico
		SIZE_TABLESPACE_GRAF;
			
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">TABLESPACE_NAME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">MBS LIVRES</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">TOTAL</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">PORCENTAGEM</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.TABLESPACE_NAME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.MBS_LIVRES || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.TOTAL || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.PRC || '</td>' );
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		  DBMS_OUTPUT.PUT_LINE( '</table>' );
			 
	END;
	
	
	-- Gráfico por backup
	PROCEDURE BACKUP_FULL_GRAF
	IS
		CURSOR c_SQL IS 
					SELECT
						ROWNUM NUM,
						REPLACE((input_bytes/1024/1024/1024), ',', '.') INPUT_GBYTES
					FROM
						(
							SELECT
								session_key,
								input_type,
								status,
								TO_CHAR(start_time, 'dd/mm/yy hh24:mi') start_time,
								TO_CHAR(end_time, 'dd/mm/yy hh24:mi') end_time,
								elapsed_seconds / 3600 hrs,
								input_bytes
							FROM
								v$rman_backup_job_details
							WHERE
								input_type <> 'ARCHIVELOG'
							ORDER BY
								session_key DESC
						)
					WHERE
					ROWNUM < 11;
		
	BEGIN
		
		DBMS_OUTPUT.PUT_LINE( '<script>' );
		
			DBMS_OUTPUT.PUT_LINE( 'function BACKUP_FULL_GRAF(){' );

				DBMS_OUTPUT.PUT_LINE( 'var tabela = new google.visualization.DataTable();' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("string","NUM"); ');
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("number","INPUT_MBYTES");' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addRows([' );
			
				FOR I IN c_SQL
				LOOP
					
					DBMS_OUTPUT.PUT_LINE( '["N:' || I.NUM || '",' || I.INPUT_GBYTES || '],' );		
				
				END LOOP;
			
			DBMS_OUTPUT.PUT_LINE( ']);' );

				DBMS_OUTPUT.PUT_LINE( 'var grafico = new google.visualization.ColumnChart(document.getElementById("graf_BACKUP_FULL_GRAF"));' );
				DBMS_OUTPUT.PUT_LINE( 'grafico.draw(tabela);' );
			DBMS_OUTPUT.PUT_LINE( '}' );
			
		
		DBMS_OUTPUT.PUT_LINE( '</script>' );
		
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
			DBMS_OUTPUT.PUT_LINE( '<tr><th>Tamanho dos últimos 10 backups Full</th></tr>' );
			DBMS_OUTPUT.PUT_LINE( '<tr><td><div id="graf_BACKUP_FULL_GRAF"></div></td></tr>' );
		DBMS_OUTPUT.PUT_LINE( '<table>' );
				
		
	END;
	
	
	-- Backup FULL
	PROCEDURE BACKUP_FULL
	IS
		CURSOR c_SQL IS 
					SELECT
						ROWNUM NUM,
						SESSION_KEY,
						INPUT_TYPE,
						STATUS,
						START_TIME,
						END_TIME,
						HRS,
						(input_bytes/1024/1024/1024) INPUT_GBYTES
					FROM
						(
							SELECT
								session_key,
								input_type,
								status,
								TO_CHAR(start_time, 'dd/mm/yy hh24:mi') start_time,
								TO_CHAR(end_time, 'dd/mm/yy hh24:mi') end_time,
								elapsed_seconds / 3600 hrs,
								INPUT_BYTES
							FROM
								v$rman_backup_job_details
							WHERE
								input_type <> 'ARCHIVELOG'
							ORDER BY
								session_key DESC
						)
					WHERE
					ROWNUM < 11;
		
	BEGIN
	
		-- Chamada do gráfico
		BACKUP_FULL_GRAF;
			
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">NUM</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">SESSION_KEY</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">INPUT_TYPE</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">STATUS</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">START_TIME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">END_TIME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">HRS</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">INPUT_GBYTES</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.NUM || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.SESSION_KEY || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.INPUT_TYPE || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.STATUS || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.START_TIME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.END_TIME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.HRS || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.INPUT_GBYTES || '</td>' );
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		  DBMS_OUTPUT.PUT_LINE( '</table>' );
			 
	END;
	
	
	-- Gráfico por backup
	PROCEDURE BACKUP_ARCHIVE_GRAF
	IS
		CURSOR c_SQL IS 
					SELECT
						ROWNUM NUM,
						REPLACE((input_bytes/1024/1024), ',', '.') INPUT_MBYTES
					FROM
						(
							SELECT
								session_key,
								input_type,
								status,
								TO_CHAR(start_time, 'dd/mm/yy hh24:mi') start_time,
								TO_CHAR(end_time, 'dd/mm/yy hh24:mi') end_time,
								elapsed_seconds / 3600 hrs,
								input_bytes
							FROM
								v$rman_backup_job_details
							WHERE
								input_type = 'ARCHIVELOG'
							ORDER BY
								session_key DESC
						)
					WHERE
					ROWNUM < 51;
		
	BEGIN
		
		DBMS_OUTPUT.PUT_LINE( '<script>' );
		
			DBMS_OUTPUT.PUT_LINE( 'function BACKUP_ARCHIVE_GRAF(){' );

				DBMS_OUTPUT.PUT_LINE( 'var tabela = new google.visualization.DataTable();' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("string","NUM"); ');
				DBMS_OUTPUT.PUT_LINE( 'tabela.addColumn("number","INPUT_MBYTES");' );
				DBMS_OUTPUT.PUT_LINE( 'tabela.addRows([' );
			
				FOR I IN c_SQL
				LOOP
					
					DBMS_OUTPUT.PUT_LINE( '["N: ' || I.NUM || '",' || I.INPUT_MBYTES || '],' );		
				
				END LOOP;
			
			DBMS_OUTPUT.PUT_LINE( ']);' );

				DBMS_OUTPUT.PUT_LINE( 'var grafico = new google.visualization.ColumnChart(document.getElementById("graf_BACKUP_ARCHIVE_GRAF"));' );
				DBMS_OUTPUT.PUT_LINE( 'grafico.draw(tabela);' );
			DBMS_OUTPUT.PUT_LINE( '}' );
			
		
		DBMS_OUTPUT.PUT_LINE( '</script>' );
		
		
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
			DBMS_OUTPUT.PUT_LINE( '<tr><th>Tamanho dos últimos 50 backups Archive</th></tr>' );
			DBMS_OUTPUT.PUT_LINE( '<tr><td><div id="graf_BACKUP_ARCHIVE_GRAF"></div></td></tr>' );
		DBMS_OUTPUT.PUT_LINE( '<table>' );
				
		
	END;
	
	
	-- Backup Archive
	PROCEDURE BACKUP_ARCHIVE
	IS
		CURSOR c_SQL IS 
					SELECT
						ROWNUM NUM,
						SESSION_KEY,
						INPUT_TYPE,
						STATUS,
						START_TIME,
						END_TIME,
						HRS,
						(input_bytes/1024/1024) INPUT_MBYTES
					FROM
						(
							SELECT
								session_key,
								input_type,
								status,
								TO_CHAR(start_time, 'dd/mm/yy hh24:mi') start_time,
								TO_CHAR(end_time, 'dd/mm/yy hh24:mi') end_time,
								elapsed_seconds / 3600 hrs,
								INPUT_BYTES
							FROM
								v$rman_backup_job_details
							WHERE
								input_type = 'ARCHIVELOG'
							ORDER BY
								session_key DESC
						)
					WHERE
					ROWNUM < 51;
		
	BEGIN
	
		-- Chamada do gráfico
		BACKUP_ARCHIVE_GRAF;
			
		DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
		
		DBMS_OUTPUT.PUT_LINE( '<tr>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">NUM</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">SESSION_KEY</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">INPUT_TYPE</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">STATUS</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">START_TIME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">END_TIME</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">HRS</th>' );
			DBMS_OUTPUT.PUT_LINE( '<th align="left" class="header_result">INPUT_MBYTES</th>' );
		DBMS_OUTPUT.PUT_LINE( '</tr>' );
		
		
		FOR I IN c_SQL
		
        LOOP
			
			DBMS_OUTPUT.PUT_LINE( '<tr>' );			
				
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.NUM || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.SESSION_KEY || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.INPUT_TYPE || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.STATUS || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.START_TIME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.END_TIME || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.HRS || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '<td>' || I.INPUT_MBYTES || '</td>' );
				
			DBMS_OUTPUT.PUT_LINE( '</tr>' );			
		
		END LOOP;	

		  DBMS_OUTPUT.PUT_LINE( '</table>' );
			 
	END;
	
	-- Cabeçalho dos relatórios
	PROCEDURE HEADER_INF( p_div VARCHAR2, p_title VARCHAR2, p_call_procedure VARCHAR2)
	IS
	BEGIN
		
		DBMS_OUTPUT.PUT_LINE( '<div class="header_inf_report">' );
			DBMS_OUTPUT.PUT_LINE( '<table id="customers">' );
				DBMS_OUTPUT.PUT_LINE( '<tr>' );
					
					DBMS_OUTPUT.PUT_LINE( '<td class=' || chr(39) || 'btn' || chr(39) || ' >' );
						
						-- Verifica se tem chamado de gráfico
						CASE
						
							WHEN p_call_procedure = 'LIST_OBJECT_USER' THEN 
								DBMS_OUTPUT.PUT_LINE('<button class="myButton" id=' || chr(39) || 'btn_' || p_div || chr(39) || ' onclick=' || chr(39) || 'showObj("' || p_div || '");google.charts.setOnLoadCallback(LIST_OBJECT_USER_GRAF);' || chr(39) || '>MOSTRAR</button>' );
							
							WHEN p_call_procedure = 'LIST_JOB_FAILED' THEN 
								DBMS_OUTPUT.PUT_LINE('<button class="myButton" id=' || chr(39) || 'btn_' || p_div || chr(39) || ' onclick=' || chr(39) || 'showObj("' || p_div || '");google.charts.setOnLoadCallback(LIST_JOB_FAILED_GRAF);' || chr(39) || '>MOSTRAR</button>' );
								
							WHEN p_call_procedure = 'LIST_OBJECT_INVALID' THEN 
								DBMS_OUTPUT.PUT_LINE('<button class="myButton" id=' || chr(39) || 'btn_' || p_div || chr(39) || ' onclick=' || chr(39) || 'showObj("' || p_div || '");google.charts.setOnLoadCallback(LIST_OBJECT_INVALID_GRAF);' || chr(39) || '>MOSTRAR</button>' );
								
							WHEN p_call_procedure = 'LIST_COUNT_USER_STATUS' THEN 
								DBMS_OUTPUT.PUT_LINE('<button class="myButton" id=' || chr(39) || 'btn_' || p_div || chr(39) || ' onclick=' || chr(39) || 'showObj("' || p_div || '");google.charts.setOnLoadCallback(LIST_COUNT_USER_STATUS_GRAF);' || chr(39) || '>MOSTRAR</button>' );
								
							WHEN p_call_procedure = 'LIST_TRIGGER_DISABLED' THEN 
								DBMS_OUTPUT.PUT_LINE('<button class="myButton" id=' || chr(39) || 'btn_' || p_div || chr(39) || ' onclick=' || chr(39) || 'showObj("' || p_div || '");google.charts.setOnLoadCallback(LIST_TRIGGER_DISABLED_GRAF);' || chr(39) || '>MOSTRAR</button>' );
								
							WHEN p_call_procedure = 'SIZE_DATABASE' THEN 
								DBMS_OUTPUT.PUT_LINE('<button class="myButton" id=' || chr(39) || 'btn_' || p_div || chr(39) || ' onclick=' || chr(39) || 'showObj("' || p_div || '");google.charts.setOnLoadCallback(SIZE_DATABASE_GRAF);' || chr(39) || '>MOSTRAR</button>' );
								
							WHEN p_call_procedure = 'SIZE_TABLESPACE' THEN 
								DBMS_OUTPUT.PUT_LINE('<button class="myButton" id=' || chr(39) || 'btn_' || p_div || chr(39) || ' onclick=' || chr(39) || 'showObj("' || p_div || '");google.charts.setOnLoadCallback(SIZE_TABLESPACE_GRAF);' || chr(39) || '>MOSTRAR</button>' );
								
							WHEN p_call_procedure = 'BACKUP_FULL' THEN 
								DBMS_OUTPUT.PUT_LINE('<button class="myButton" id=' || chr(39) || 'btn_' || p_div || chr(39) || ' onclick=' || chr(39) || 'showObj("' || p_div || '");google.charts.setOnLoadCallback(BACKUP_FULL_GRAF);' || chr(39) || '>MOSTRAR</button>' );
								
							WHEN p_call_procedure = 'BACKUP_ARCHIVE' THEN 
								DBMS_OUTPUT.PUT_LINE('<button class="myButton" id=' || chr(39) || 'btn_' || p_div || chr(39) || ' onclick=' || chr(39) || 'showObj("' || p_div || '");google.charts.setOnLoadCallback(BACKUP_ARCHIVE_GRAF);' || chr(39) || '>MOSTRAR</button>' );							
							
							ELSE
								DBMS_OUTPUT.PUT_LINE('<button class="myButton" id=' || chr(39) || 'btn_' || p_div || chr(39) || ' onclick=' || chr(39) || 'showObj("' || p_div || '");' || chr(39) || '>MOSTRAR</button>' );
								
						END CASE;						
						
					DBMS_OUTPUT.PUT_LINE( '</td>' );
					
					DBMS_OUTPUT.PUT_LINE( '<td class="title" >' || p_title || '</td>' );
				DBMS_OUTPUT.PUT_LINE( '</tr>' );
			DBMS_OUTPUT.PUT_LINE( '</table>' );
		DBMS_OUTPUT.PUT_LINE( '</div>' );

		DBMS_OUTPUT.PUT_LINE( '<div id="' || p_div || '" style="display:none;">' );

			-- Chamada da procedure
			CASE
				WHEN p_call_procedure = 'LIST_OBJECT_USER' THEN LIST_OBJECT_USER;
				WHEN p_call_procedure = 'LIST_JOB_FAILED' THEN LIST_JOB_FAILED;
				WHEN p_call_procedure = 'LIST_OBJECT_INVALID' THEN LIST_OBJECT_INVALID;
				WHEN p_call_procedure = 'LIST_COUNT_USER_STATUS' THEN LIST_COUNT_USER_STATUS;
				WHEN p_call_procedure = 'LIST_USER_DBA' THEN LIST_USER_DBA;
				WHEN p_call_procedure = 'LIST_TRIGGER_DISABLED' THEN LIST_TRIGGER_DISABLED;
				WHEN p_call_procedure = 'LIST_RESOURCE_LIMIT' THEN LIST_RESOURCE_LIMIT;
				WHEN p_call_procedure = 'TOP_QUERY' THEN TOP_QUERY;
				WHEN p_call_procedure = 'SIZE_DATABASE' THEN SIZE_DATABASE;
				WHEN p_call_procedure = 'SIZE_TABLESPACE' THEN SIZE_TABLESPACE;
				WHEN p_call_procedure = 'BACKUP_FULL' THEN BACKUP_FULL;
				WHEN p_call_procedure = 'BACKUP_ARCHIVE' THEN BACKUP_ARCHIVE;
			END CASE;
			
		DBMS_OUTPUT.PUT_LINE( '<br /><br /><br />' );
		DBMS_OUTPUT.PUT_LINE( '</div>' );
	
	END;

BEGIN
	
	-- Data do dia atual
	SELECT TO_CHAR(sysdate, 'DD "de" fmMonth "de" YYYY','NLS_DATE_LANGUAGE=PORTUGUESE') || ' - ' || TO_CHAR(sysdate, 'HH24:MI:SS') INTO DATA_ATUAL FROM DUAL;
	
	-- Data do dia anterior
	SELECT TO_CHAR(sysdate-1, 'DD/MM/YYYY','NLS_DATE_LANGUAGE=PORTUGUESE') INTO DATE_YESTERDAY FROM DUAL;


	DBMS_OUTPUT.PUT_LINE( '<!DOCTYPE html>' );
	DBMS_OUTPUT.PUT_LINE( '<html>' );
	DBMS_OUTPUT.PUT_LINE( '<head>' );
	DBMS_OUTPUT.PUT_LINE( '<style> .myButton { display: inline-block; padding: 5px 15px; font-size: 12px; cursor: pointer; text-align: center; text-decoration: none; outline: none; color: #fff; background-color: #4CAF50; border: none;  border-radius: 15px; box-shadow: 0 5px #999; } .myButton:hover {background-color: #3e8e41} .myButton:active { background-color: #3e8e41; box-shadow: 0 3px #666; transform: translateY(4px); } #customers { font-family: "Trebuchet MS", Arial, Helvetica, sans-serif; border-collapse: collapse; width: 100%; } #customers td, #customers th { border: 1px solid #ddd; padding: 8px; } #customers tr:nth-child(even){background-color: #f2f2f2;} #customers tr:hover {background-color: #ddd;} #customers th { padding-top: 12px; padding-bottom: 12px; text-align: left; background-color: #4CAF50; color: white; } .header { padding: 60px; text-align: center; background: #1abc9c; color: white; font-size: 30px; } .header_result { background-color: #fff; color: #000; font-weight: bold; font-size: 12px; } .header_inf_report{ background-color: #F0FFFF; } .header_inf_report .btn { width: 100px; } .header_inf_report .title { color: #006400; font-weight: bold; font-size: 25px; } .developer{ font-size:12px; font-weight: bold; color: #A52A2A; } .footer_report{ color:#000; font-weight: bold; font-size:14px; } </style>' );
	DBMS_OUTPUT.PUT_LINE( '</head>' );
	
		DBMS_OUTPUT.PUT_LINE( '<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>' );
		
		DBMS_OUTPUT.PUT_LINE( '<script>google.charts.load("current", {"packages":["corechart"]});</script>');
	
	DBMS_OUTPUT.PUT_LINE( '<body>' );
	
	DBMS_OUTPUT.PUT_LINE( '<div class="header">' );
	  DBMS_OUTPUT.PUT_LINE( '<h1>Startup - Dados e Sistemas</h1>' );
	  DBMS_OUTPUT.PUT_LINE( '<h2>'|| NOME_CLIENTE ||'</h2>' );
	  DBMS_OUTPUT.PUT_LINE( '<h3>Relatório: '|| NOME_BANCO_DE_DADOS ||'('|| TIPO_BANCO_DE_DADOS ||') </h3>' );
	  DBMS_OUTPUT.PUT_LINE( '<p style="font-size: 20px;">DBA: '|| NOME_DBA ||'</p>' );
	DBMS_OUTPUT.PUT_LINE( '</div>' );
	
	
	-- Lista de objetos por OWNER
	HEADER_INF('list_job_failed', 'Lista de jobs com falhas do dia '||DATE_YESTERDAY, 'LIST_JOB_FAILED');
	
	
	-- Lista de objetos por OWNER
	HEADER_INF('list_object_owner', 'Lista de Objetos por Usuário', 'LIST_OBJECT_USER');
	
	
	-- Lista de objetos por OWNER
	HEADER_INF('list_object_invalid', 'Lista de Objetos Inváldos por Usuário', 'LIST_OBJECT_INVALID');
	
	
	-- Lista de usuários por status
	HEADER_INF('list_count_user_status', 'Lista de usuários por status', 'LIST_COUNT_USER_STATUS');
	
	
	-- Lista de usuários por status
	HEADER_INF('list_user_dba', 'Lista de usuários com privilégio de DBA', 'LIST_USER_DBA');
		
		
	-- Lista de trigger desabilitadas
	HEADER_INF('list_trigger_disabled', 'Lista de trigger desabilitadas por usuário', 'LIST_TRIGGER_DISABLED');
	
	
	-- Lista de trigger desabilitadas
	HEADER_INF('list_resource_limit', 'Total recursos utilizados', 'LIST_RESOURCE_LIMIT');
	
	
	-- Lista de trigger desabilitadas
	HEADER_INF('list_top_query', 'Top 50 querys com alto consumo', 'TOP_QUERY');	
	
	
	-- Tamanho do banco de dados
	HEADER_INF('size_database', 'Tamanho do banco de dados', 'SIZE_DATABASE');	
	
	-- Tamanho por tablespace
	HEADER_INF('size_tablespace', 'Tamanho por tablespace', 'SIZE_TABLESPACE');	
	
	
	-- Lista de backups
	HEADER_INF('backup_full', 'Lista dos últimos 10 backups Full', 'BACKUP_FULL');
	
	
	-- Lista de backups
	HEADER_INF('backup_archive', 'Lista dos últimos 50 backups de Archive', 'BACKUP_ARCHIVE');
		
		
	DBMS_OUTPUT.PUT_LINE( '<div>' );
		DBMS_OUTPUT.PUT_LINE( '<p>' );
			DBMS_OUTPUT.PUT_LINE( 'Belo Horizonte, ' );
			DBMS_OUTPUT.PUT_LINE( DATA_ATUAL );
		DBMS_OUTPUT.PUT_LINE( '</p>' );
	DBMS_OUTPUT.PUT_LINE( '</div>' );
	
	DBMS_OUTPUT.PUT_LINE( '<div class="developer">' );
		DBMS_OUTPUT.PUT_LINE( 'Developer: Wesley David Santos' );
	DBMS_OUTPUT.PUT_LINE( '</div>' );
	
	
	DBMS_OUTPUT.PUT_LINE( '</body>' );
	
		DBMS_OUTPUT.PUT_LINE( '<script>' );

		DBMS_OUTPUT.PUT_LINE( 'function showObj( name_obj ) {' );
		  DBMS_OUTPUT.PUT_LINE( 'var x = document.getElementById(name_obj);' );
		  DBMS_OUTPUT.PUT_LINE( 'var btn = document.getElementById("btn_"+name_obj);' );
		  
		  DBMS_OUTPUT.PUT_LINE( 'if (x.style.display === "none") {' );
			DBMS_OUTPUT.PUT_LINE( 'x.style.display = "block";' );
			DBMS_OUTPUT.PUT_LINE( 'btn.innerHTML ="ESCONDER";' );
		  DBMS_OUTPUT.PUT_LINE( '} else {' );
			DBMS_OUTPUT.PUT_LINE( 'x.style.display = "none";' );
			DBMS_OUTPUT.PUT_LINE( 'btn.innerHTML ="MOSTRAR";' );
		  DBMS_OUTPUT.PUT_LINE( '}' );
		DBMS_OUTPUT.PUT_LINE( '}' );
		DBMS_OUTPUT.PUT_LINE( '</script>' );
		
			
	DBMS_OUTPUT.PUT_LINE( '</html>' );	
	

END;
/

spool off
set serveroutput off;
set echo off;