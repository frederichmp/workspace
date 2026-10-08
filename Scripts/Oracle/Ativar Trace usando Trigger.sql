-- Script responsável por abrir trace no momento do logon do usuário, os traces abertos são salvos na tabela


-- Usar esse SELECT para parar o trace
select 'begin sys.dbms_system.set_sql_trace_in_session('||sid||','||serial||',false); end;' from startupadmin.file_trace_wds where file_trc like '%DBHMLERP1%';


-- Usar esse SELECT para montar o comando de conversão do trace
select 'tkprof '''||file_trc||''' ''/tmp/wds_trace/'||sid||'_'||serial||'.trc''' from startupadmin.file_trace_wds where file_trc like '%DBHMLERP1%';




-- Tabela para armazenar as informações dos trace abertos
CREATE TABLE startupadmin.file_trace_wds
( 
  file_trc varchar2(255),
  sid integer,
  serial integer,
  dt date
);


CREATE TABLE startupadmin.username_trace_wds
( 
  username varchar2(255)
);

-- Procedure para ativar o trace
CREATE OR REPLACE PROCEDURE sys.proc_active_trace_wds(v_sid in INTEGER, v_serial in INTEGER)
IS
	v_file_trc varchar2(255);
	
	BEGIN
		sys.dbms_system.set_sql_trace_in_session(v_sid, v_serial,TRUE);
	
		SELECT 
			p.tracefile into v_file_trc
		FROM
			v$session s
			JOIN v$process p ON s.paddr = p.addr
		WHERE
			s.sid in ( v_sid )
			and s.serial# = v_serial;
 
		insert into startupadmin.file_trace_wds (file_trc, sid, serial, dt) values (v_file_trc, v_sid, v_serial, sysdate);
		commit;
		
	END;
/



-- Trigger para capturar o logon do usuário
CREATE OR REPLACE TRIGGER sys.active_trace_wds
 AFTER LOGON ON database
 DECLARE
 PRAGMA AUTONOMOUS_TRANSACTION;
 
	 v_sid INTEGER;
	 v_serial INTEGER;
	 v_COUNT NUMBER;
 
 BEGIN
	BEGIN
			SELECT 
				COUNT(*) INTO v_COUNT
			FROM 
				v$session
			WHERE
				sid = SYS_CONTEXT('USERENV', 'SID')
				and username in (select username from startupadmin.username_trace_wds);
				
			IF v_COUNT >0 THEN
				
				SELECT 
					sid, serial# INTO v_sid, v_serial
				FROM 
					v$session
				WHERE
					sid = SYS_CONTEXT('USERENV', 'SID')
					and username in (select username from startupadmin.username_trace_wds);
				
				
				IF v_sid IS NOT NULL THEN		
				
					sys.proc_active_trace_wds(v_sid, v_serial);
					
				END IF;
					
				
			END IF;
			
		EXCEPTION
		WHEN OTHERS THEN
			DBMS_OUTPUT.PUT_LINE('ERROR');
			--raise_application_error(-20001, 'Erro ao coletar trace. Erro > ' || SQLERRM );
		
		end;
 END;
 /



alter trigger sys.active_trace_wds enable;
alter trigger sys.active_trace_wds disable;