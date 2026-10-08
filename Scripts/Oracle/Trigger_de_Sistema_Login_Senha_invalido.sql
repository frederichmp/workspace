
--
-- SISTEMA DE CAPTURA DE ERROS DE LOGIN/SENHA INVÁLIDOS
--

--
-- Script testado no ambiente
-- Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production

--
-- Após criar os objetos use a consulta abaixo para listar os LOGs
SELECT * FROM STARTUPADMIN.WDS_LOG_FAILED_LOGON ORDER BY DATE_REGISTER;




--
--
-- Tabela responsável por armazenar as tentativas de login com usuário e senha inválidos
CREATE TABLE STARTUPADMIN.WDS_LOG_FAILED_LOGON
(
	  DATE_REGISTER DATE NULL 
	, ORA_ERROR NUMBER NULL
	, INSTANCE_ID NUMBER NULL
	, OSUSER VARCHAR2(200) NULL
	, HOST VARCHAR2(200) NULL
	, TERMINAL VARCHAR2(200) NULL
	, IP_ADDRESS VARCHAR2(200) NULL
	, NETWORK_PROTOCOL VARCHAR2(200) NULL
);



--
--
-- Trigger que caputra os erros de login/senha inválidos
-- OBS.: Criar com o usuário SYS
CREATE OR REPLACE TRIGGER SYS.WDS_FAILED_LOGON 
	AFTER SERVERERROR ON DATABASE

	DECLARE
		
		v_DATE_REGISTER DATE;
		v_ORA_ERROR NUMBER;
		v_INST_ID NUMBER;
		v_OSUSER VARCHAR2(200);
		v_HOST VARCHAR2(200);
		v_TERMINAL VARCHAR2(200);
		v_IP_ADDRESS VARCHAR2(200);
		v_NETWORK_PROTOCOL VARCHAR2(200);
		
	BEGIN
	  
		-- Verifica falha de Login
		IF ora_is_servererror( 28000 ) OR ora_is_servererror( 01017 ) THEN
			
			-- Informações do usuário
			v_DATE_REGISTER := SYSDATE;
			v_ORA_ERROR := CASE WHEN ora_is_servererror( 28000 ) THEN 28000 ELSE 01017 END;
			v_INST_ID := ora_instance_num;
			v_OSUSER := SYS_CONTEXT( 'USERENV', 'OS_USER' );
			v_HOST := SYS_CONTEXT( 'USERENV', 'HOST' );
			v_TERMINAL := SYS_CONTEXT( 'USERENV', 'TERMINAL' );
			v_IP_ADDRESS := SYS_CONTEXT( 'USERENV', 'IP_ADDRESS' );
			v_NETWORK_PROTOCOL := SYS_CONTEXT( 'USERENV', 'NETWORK_PROTOCOL' );
			

		BEGIN
		  
			INSERT INTO STARTUPADMIN.WDS_LOG_FAILED_LOGON ( DATE_REGISTER, ORA_ERROR, INSTANCE_ID, OSUSER, HOST, TERMINAL, IP_ADDRESS, NETWORK_PROTOCOL ) VALUES ( v_DATE_REGISTER, v_ORA_ERROR, v_INST_ID, v_OSUSER, v_HOST, v_TERMINAL, v_IP_ADDRESS, v_NETWORK_PROTOCOL );
			
			COMMIT;

		EXCEPTION
		  WHEN others THEN
			
			dbms_output.put_line('Erro registrar tentativa de login');

		END;
	  
    END IF;
	  
END WDS_FAILED_LOGON;
/









