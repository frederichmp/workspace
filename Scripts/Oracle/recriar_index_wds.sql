

------------------------
------------------------
---- Recriar Index -----
------------------------

-- Observação: Executar todo o código de uma vez (ctrl+a -> execute)

-- Arquivo onde será escrito os comandos
spool "C:\Users\wds\Downloads\create_index.sql"

set newpage 0; 
set echo off; 
set feedback off; 
set heading off; 

-- Habilitar o output dos resultados
SET SERVEROUTPUT ON;

-- Chamada usada para evitar o erro de buffer overflow, limit of 1000000 bytes    
exec DBMS_OUTPUT.ENABLE (buffer_size => NULL);


declare

 DLL_INDEX VARCHAR2(4000);

begin

    FOR x IN ( select owner, index_name from all_indexes where owner in ( 'WDS' ) and rownum < 5 ) LOOP
    
        
        DBMS_OUTPUT.put_line( '--' );
        DBMS_OUTPUT.put_line( '-- Index : ' || x.owner || '.' || x.index_name );
        select dbms_metadata.get_ddl('INDEX', x.index_name, x.owner) || ';' INTO DLL_INDEX from dual;
        DBMS_OUTPUT.put_line( DLL_INDEX );
        
    END LOOP;    




END;
/


-- Fecha o processo de escrita em arquivo
spool off
set serveroutput off;
set echo off;

