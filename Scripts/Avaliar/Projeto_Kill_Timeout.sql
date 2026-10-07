
--///////////////////////////////////////////////////////////////////////////////////////--
--////////////////////////---- SISTEMA DE KILL SESSION LOCK ----/////////////////////////--
--///////////////////////////////////////////////////////////////////////////////////////--


-- Chamado autorizando a criação do sistema de Kill para usuários específicos causando lock
-- Chamado: 0422-000066 - Startup Dados e Sistemas
-- Autor: Wesley David Santos
-- Skype: wesleydavidsantos


--
--
-- Importante: É de obrigação do Cliente (VLI) realizar todos os testes necessários antes de realizar a implementação no ambiente de Produção.
-- Seguem neste arquivo, todos os Objetos que serão necessários para a implementação do sistema. Solicito que analise e valide o código fonte de cada objeto.


--
--
-- Escopo do Sistema
-- Criação de um sistema que funciona de forma automática para finalizar sessões especificas causando lock em um determinado tempo calculado em segundos
-- Tabela utilizada para identificar os locks : SYS.GV_$SESSION
-- Coluna utilizada para identificar o tempo em segundos: LAST_CALL_ET



--
--
-- Objetos pertencentes ao sistema de Kill


-- TABLE - ACTPP.CONFIG_TIMEOUT_KILL
-- Tabela responsável por armazenar o nome do usuário (USERNAME) e o tempo máximo em segundos que esse usuário pode causar lock antes que tenha a sessão finalizada através de um Kill
-- As informações nesta tabela devem ser manipuladas de forma manual através de ações de DML (SELECT - INSERT - UPDATE - DELETE )
-- A coluna USERNAME é tratada como Primary Key, desta forma não é possível repetir o nome
-- Utilize apenas USERNAME escrito em letras maiúsculas
-- A coluna TIMEOUT deve receber somente valores inteiros. O valor será considerado em segundos
-- Importante: Por motivos de segurança e integridade do banco de dados, NÃO adicione usuários que executam processos internos do ORACLE.
--  		   Exemplos de alguns usuários que NÃO devem ser adicionados: 'SYS', 'SYSTEM', 'DBSNMP', 'SYSBACKUP', 'SYSDG', 'SYSKM', 'SYSRAC', 'WMSYS', 'XDB', 'AUDSYS'
--			   O registro de quaisquer usuários nesta tabela é de responsabilidade do Cliente (VLI)


-- Exemplo de uso:
-- Novo usuário a ser validado.

INSERT INTO ACTPP.CONFIG_TIMEOUT_KILL ( USERNAME, TIMEOUT ) VALUES ( 'NOME_DO_USUARIO', 20 );
COMMIT;




-- TABLE - ACTPP.LOG_TIMEOUT_BD
-- Tabela responsável por criar um registro dos usuários que sofreram KILL por motivo de lock
-- A coluna ID é um identificador único preenchido através da Sequence ACTPP.SEQ_PK_LOG_TIMEOUT_BD
-- A coluna DATE_REGISTER armazena o dia e horário que a ação de Kill foi realizada
-- Existem mais 15 colunas que armazenam as informações dos usuários que sofreram Kill, algumas das colunas podem possuir o valor NULL
-- As informações desta tabela são preenchidas de forma automática através da PROCEDURE SYS.KILL_SESSION_TIMEOUT

-- Exemplo de uso:
-- Coletando os registros ordenando pelo ID

SELECT * FROM ACTPP.LOG_TIMEOUT_BD ORDER BY ID DESC;



-- SEQUENCE - ACTPP.SEQ_PK_LOG_TIMEOUT_BD
-- Sequence utilizada como identificador único a ser utilizado na tabela ACTPP.LOG_TIMEOUT_BD
-- A sequence é incrementada através da trigger ACTPP.LOG_TIMEOUT_BD_ON_INSERT



-- TRIGGER - ACTPP.LOG_TIMEOUT_BD_ON_INSERT
-- Trigger utilizada para gerar um novo valor de Sequence para registrar na coluna ID da tabela ACTPP.LOG_TIMEOUT_BD



-- PROCEDURE - SYS.KILL_SESSION_TIMEOUT
-- Procedure responsável por listar e finalizar as sessões que estão causando lock de acordo com as regras pré-estabelecidas
-- Somente as sessões que se encaixam em determinadas regras podem ser finalizadas
-- Importante: Por motivo de permissão sobre a ação de KILL SESSION essa procedure deve ser criada dentro do OWNER SYS
-- Os usuários causando lock são listados a partir da tabela SYS.GV_$SESSION e o tempo em segundos é verificado através da coluna LAST_CALL_ET
-- Somente os usuários que estiverem registrados na tabela ACTPP.CONFIG_TIMEOUT_KILL serão passíveis de sofrerem kill
-- É necessário dar o GRANT de execução ao usuário que vai relizar a chamada da procedure. O grant deve ser atribuído utilizando o usuário SYS
-- Essa procedure por ser executada de forma manual através do usuário que tem permissão para essa ação.

-- Exemplo de Grant:
-- Dar a permissão de execução para o usuário que deseja
GRANT EXECUTE ON SYS.KILL_SESSION_TIMEOUT TO ACTPP;


-- Exemplo de execução manual:
EXECUTE SYS.KILL_SESSION_TIMEOUT;




-- JOB DBMS_SCHEDULER - ACTPP.JOB_KILL_SESSION_TIMEOUT
-- Job responsável por realizar a chamada da procedure SYS.KILL_SESSION_TIMEOUT para verificar os locks existentes
-- Esse job está programado para executar a cada 10 Segundos
-- O Job deve ser criado no OWNER que tenha permissão de execução da procedure
-- O kill só vai ser realizado quando esse Job realizar a chamada da procedure, desta forma o tempo de lock pode ser maior que o limite de TIMEOUT registrado na tabela ACTPP.CONFIG_TIMEOUT_KILL
-- 		Exemplo: TIMEOUT definido como 30 segundos, se o lock estiver em 29 segundos quando o Job executou, o lock só será finalizado na próxima execução, tornando o tempo de lock superior ao limite 




--
--
-- Sugestão para realização de testes
--
-- Registre o usuário que deve ser monitorado e o tempo de lock que deve ser analisado
-- Realize conexões usando sessões diferentes no banco de dados
-- Realize uma ação DML (UPDATE) em uma tabela e em um registro específico
-- Realize a mesma ação de DML utilizando uma outra sessão, desta forma será criado um lock
-- Exemplo Update:
--
-- Execute o mesmo update em duas sessões diferentes
-- UPDATE OWER_TESTE.TABLE_TESTE SET COLUMN_TESTE = NEW_VALUE WHERE ID = ID_TESTE;
-- 







--//////////////////////////////////////////////////////////////////////////////////////////////////////--
--////////////////////////---- CÓDIGO FONTE DOS OBJETOS DO SISTEMA DE KILL ----/////////////////////////--
--//////////////////////////////////////////////////////////////////////////////////////////////////////--



--
--
--
-- Tabela responsável por armazenar as confirações de Timeout
CREATE TABLE ACTPP.CONFIG_TIMEOUT_KILL
(
  USERNAME VARCHAR2(45) NOT NULL
, TIMEOUT NUMBER  NOT NULL
, CONSTRAINT cons_CONFIG_TIMEOUT_KILL_USERNAME_PK PRIMARY KEY 
  (
    USERNAME 
  )
  ENABLE 
);

COMMENT ON TABLE ACTPP.CONFIG_TIMEOUT_KILL IS 'Tabela responsável por armazenar as confirações de Timeout para realizar Kill automático. Criado por Wesley Santos - Startup - Chamado: 0422-000066';





--
--
--
-- Sequence usada pela tabela KILL
CREATE SEQUENCE ACTPP.SEQ_PK_LOG_TIMEOUT_BD INCREMENT BY 1 START WITH 1 CACHE 20;



--
--
--
-- Tabela responsável por criar um registro dos usuários que sofreram KILL por motivo de lock
CREATE TABLE ACTPP.LOG_TIMEOUT_BD
(
  ID NUMBER(11) NOT NULL
, DATE_REGISTER DATE NOT NULL
, INST_ID NUMBER  NOT NULL
, SID NUMBER  NOT NULL
, SERIAL NUMBER NOT NULL
, USERNAME VARCHAR2(45) NOT NULL
, MACHINE VARCHAR2(250) NULL
, OSUSER VARCHAR2(250) NULL
, LAST_CALL_ET NUMBER NULL
, LAST_CALL_ET_FORMAT VARCHAR2(40) NULL
, MODULE VARCHAR2(250) NULL
, CLIENT_INFO VARCHAR2(250) NULL
, STATUS VARCHAR2(250) NULL
, BLOCKING_SESSION VARCHAR2(250) NULL
, SQL_ID VARCHAR2(250) NULL
, PREV_SQL_ID VARCHAR2(250) NULL
, EVENT VARCHAR2(250) NULL
, CONSTRAINT cons_LOG_TIMEOUT_BD_PK PRIMARY KEY 
  (
    ID 
  )
  ENABLE 
);

COMMENT ON TABLE ACTPP.LOG_TIMEOUT_BD IS 'Tabela responsável por criar um registro dos usuários que sofreram KILL por motivo de lock. Criado por Wesley Santos - Startup - Chamado: 0422-000066';



--
--
-- Trigger para inserir as primary key dentro da tabela KILL_LOG
CREATE OR REPLACE TRIGGER ACTPP.LOG_TIMEOUT_BD_ON_INSERT
--
-- Trigger para inserir as primary key dentro da tabela KILL_LOG
-- 
-- Autor: Wesley David Santos
-- Skype: wesleydavidsantos		
-- https://www.linkedin.com/in/wesleydavidsantos
--
  BEFORE INSERT ON ACTPP.LOG_TIMEOUT_BD
  FOR EACH ROW
BEGIN
  SELECT ACTPP.SEQ_PK_LOG_TIMEOUT_BD.NEXTVAL
  INTO :NEW.ID
  FROM DUAL;
END;
/





--
--
--
-- Procedure responsavel por listar e finalizar as sessoes que estao causando lock de acordo com as regras pre-estabelecidas
-- Somente as sessões que se encaixam em determinadas regras podem ser finalizadas
-- Criar com usuário SYS
--
CREATE OR REPLACE PROCEDURE SYS.KILL_SESSION_TIMEOUT IS 
--
--
-- Procedure responsavel por listar e finalizar as sessoes que estao causando lock de acordo com as regras pre-estabelecidas
-- Somente as sessões que se encaixam em determinadas regras podem ser finalizadas
-- Criar com usuário SYS
--
-- Startup Dados e Sistemas - Chamado: 0422-000066
--
-- Autor: Wesley David Santos
-- Skype: wesleydavidsantos		
-- https://www.linkedin.com/in/wesleydavidsantos
--

	-- Constante com o valor do insert
	v_STMT_INSERT CONSTANT VARCHAR2(4000) := 'INSERT INTO ACTPP.LOG_TIMEOUT_BD ( 
																					  DATE_REGISTER
																					, INST_ID
																					, SID
																					, SERIAL
																					, USERNAME
																					, MACHINE
																					, OSUSER
																					, LAST_CALL_ET
																					, LAST_CALL_ET_FORMAT
																					, MODULE
																					, CLIENT_INFO
																					, STATUS
																					, BLOCKING_SESSION
																					, SQL_ID
																					, PREV_SQL_ID
																					, EVENT
																				  ) 
																				VALUES 
																				  (
																					  :DATE_REGISTER
																					, :INST_ID
																					, :SID
																					, :SERIAL
																					, :USERNAME
																					, :MACHINE
																					, :OSUSER
																					, :LAST_CALL_ET
																					, :LAST_CALL_ET_FORMAT
																					, :MODULE
																					, :CLIENT_INFO
																					, :STATUS
																					, :BLOCKING_SESSION
																					, :SQL_ID
																					, :PREV_SQL_ID
																					, :EVENT																				  
																				  )';
																				  
	
	-- Lista as sessões que serão finalizadas
	CURSOR KILL_SESSIONS_TIMEOUT
	   IS
			SELECT
				 INST_ID
				,SID
				,SERIAL# SERIAL
				,USERNAME
				,MACHINE
				,OSUSER
				,LAST_CALL_ET
				,( TRUNC(MOD(LAST_CALL_ET / 3600, 60))
				  || 'H:'
				  || TRUNC(MOD((LAST_CALL_ET / 60), 60))
				  || 'MIM:'
				  || TRUNC(MOD(LAST_CALL_ET, 60))
				  || 'S' ) LAST_CALL_ET_FORMAT    
				,MODULE
				,CLIENT_INFO
				,STATUS
				,BLOCKING_SESSION
				,SQL_ID
				,PREV_SQL_ID
				,EVENT
			FROM
				SYS.GV_$SESSION LIST_SESSION
			WHERE
				TYPE != 'BACKGROUND'
				AND USERNAME NOT IN ( 'SYS', 'SYSTEM', 'DBSNMP', 'SYSBACKUP', 'SYSDG', 'SYSKM', 'SYSRAC', 'WMSYS', 'XDB', 'AUDSYS')
				AND ( SID, INST_ID ) IN (
											SELECT
												BLOCKING_SESSION, FINAL_BLOCKING_INSTANCE
											FROM
												GV$SESSION
											WHERE
												BLOCKING_SESSION IS NOT NULL
										)
				AND EXISTS (
							SELECT 
								1
							FROM 
								ACTPP.CONFIG_TIMEOUT_KILL CONFIG_KILL 
							WHERE 
								UPPER( CONFIG_KILL.USERNAME ) = UPPER( LIST_SESSION.USERNAME )
								AND LIST_SESSION.LAST_CALL_ET > CONFIG_KILL.TIMEOUT							
						  );	   
				
	
	-- Recebe o comando para finalizar a sessão
	v_COMMAND_KILL VARCHAR2 (255);	
	
BEGIN 
  
	BEGIN 
	
		DBMS_OUTPUT.PUT_LINE('INICIO KILL SESSION');
		DBMS_OUTPUT.PUT_LINE('');
		
		-- INÍCIO KILL SESSIONS
		FOR KILL_SESSION IN KILL_SESSIONS_TIMEOUT
			LOOP
			
				-- Registra no LOG
				EXECUTE IMMEDIATE v_STMT_INSERT USING 
														  SYSDATE
														, KILL_SESSION.INST_ID
														, KILL_SESSION.SID
														, KILL_SESSION.SERIAL
														, KILL_SESSION.USERNAME
														, KILL_SESSION.MACHINE
														, KILL_SESSION.OSUSER
														, KILL_SESSION.LAST_CALL_ET
														, KILL_SESSION.LAST_CALL_ET_FORMAT
														, KILL_SESSION.MODULE
														, KILL_SESSION.CLIENT_INFO
														, KILL_SESSION.STATUS
														, KILL_SESSION.BLOCKING_SESSION
														, KILL_SESSION.SQL_ID
														, KILL_SESSION.PREV_SQL_ID
														, KILL_SESSION.EVENT;
														
				COMMIT;				
				
				v_COMMAND_KILL := 'ALTER SYSTEM KILL SESSION ''' || KILL_SESSION.SID || ',' || KILL_SESSION.SERIAL || ',@' || KILL_SESSION.INST_ID || ''' IMMEDIATE';
				
				DBMS_OUTPUT.PUT_LINE('-- ' || v_COMMAND_KILL);

				EXECUTE IMMEDIATE v_COMMAND_KILL;
				-- KILL SESSION FINALIZADA			
		
		END LOOP;
		
		DBMS_OUTPUT.PUT_LINE('--Procedure kill_session is done');
		DBMS_OUTPUT.PUT_LINE('');
		
    EXCEPTION 
          WHEN OTHERS THEN
			DBMS_OUTPUT.put_line('- Session nAo foi finalizada ou marcada para morrer, provAvel que a sessão não estava mais ativa ao executar o comando de kill' ); 
			raise_application_error(-20001, 'Erro ao registrar o monitoramento. Erro > ' || SQLERRM );
    END; 
  
END; 
/ 


-- Dar a permissão de execução para o usuário que deseja
GRANT EXECUTE ON SYS.KILL_SESSION_TIMEOUT TO ACTPP;






--
-- Criação do JOB que vai verificar se existem locks
-- JOB programado para executar a cada 10 Segundos

BEGIN
    DBMS_SCHEDULER.CREATE_JOB (
            job_name => '"ACTPP"."JOB_KILL_SESSION_TIMEOUT"',
            job_type => 'STORED_PROCEDURE',
            job_action => 'SYS.KILL_SESSION_TIMEOUT',
            number_of_arguments => 0,
            start_date => TO_TIMESTAMP_TZ('2022-04-25 11:29:04.000000000 -03:00','YYYY-MM-DD HH24:MI:SS.FF TZR'),
            repeat_interval => 'FREQ=SECONDLY;INTERVAL=10',
            end_date => NULL,
            enabled => FALSE,
            auto_drop => FALSE,
            comments => 'Realiza a validacao se existem locks especificos. Criado por Wesley Santos - Startup - Chamado: 0422-000066');

         
     
 
    DBMS_SCHEDULER.SET_ATTRIBUTE( 
             name => '"ACTPP"."JOB_KILL_SESSION_TIMEOUT"', 
             attribute => 'store_output', value => TRUE);
    DBMS_SCHEDULER.SET_ATTRIBUTE( 
             name => '"ACTPP"."JOB_KILL_SESSION_TIMEOUT"', 
             attribute => 'logging_level', value => DBMS_SCHEDULER.LOGGING_OFF);
      
   
  
    
    DBMS_SCHEDULER.enable(
             name => '"ACTPP"."JOB_KILL_SESSION_TIMEOUT"');
END;
/















