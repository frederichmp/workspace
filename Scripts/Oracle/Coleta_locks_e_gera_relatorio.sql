
--##
-- Lista usuários com bloqueios de linha
-- Usar com SQLDeveloper
-- Obrigatório executar essas 3 linhas abaixo pelo menos uma vez
SET SERVEROUTPUT ON;
EXEC DBMS_OUTPUT.ENABLE (buffer_size => NULL);
SET TIMING ON;


DECLARE

    flag_user_locked NUMBER(1);
    SQL_LOCK CLOB;
    SQL_LOCK_PREV CLOB;    
    count_blocked  NUMBER(10);
    
BEGIN
    
    FOR loop_LOCK in (
        
        SELECT DISTINCT 
            LOCK_INST_ID, 
            LOCK_SESSION_ID,
            LOCK_XIDSQN, 
            LOCK_ORACLE_USERNAME, 
            LOCK_OS_USER_NAME, 
            LISTAGG( LOCK_OBJECT_NAME || ' / LOCK_LOCKED_MODE: ' || LOCK_LOCKED_MODE , '  /---/   ' ) WITHIN GROUP (ORDER BY ROWNUM) LOCK_OBJECT_NAME,
            LOCK_SQL_ID,
            LOCK_PREV_SQL_ID,
            LOCK_MODULE
        FROM
            (
        
                SELECT DISTINCT 
                    A.INST_ID             LOCK_INST_ID, 
                    A.SESSION_ID         LOCK_SESSION_ID, 
                    A.OBJECT_ID         LOCK_OBJECT_ID,
                    A.XIDSQN             LOCK_XIDSQN, 
                    A.ORACLE_USERNAME     LOCK_ORACLE_USERNAME, 
                    A.OS_USER_NAME         LOCK_OS_USER_NAME, 
                    ( 'LOCK_OWNER: ' || B.OWNER || ' / LOCK_OBJECT_ID: ' || A.OBJECT_ID || ' / OBJECT_NAME: ' || B.OBJECT_NAME || ' / OBJECT_TYPE: ' || B.OBJECT_TYPE || ' / ACTION: ' || S.ACTION || ' / EVENT: ' || S.EVENT ) LOCK_OBJECT_NAME,
                    S.SQL_ID             LOCK_SQL_ID,
                    S.PREV_SQL_ID        LOCK_PREV_SQL_ID,
                    --SQL.SQL_FULLTEXT     LOCK_SQL_FULLTEXT,
                    SQL.MODULE             LOCK_MODULE,
                    decode(A.LOCKED_MODE,
                           1, NULL,
                           2, 'Row Share',
                           3, 'Row Exclusive',
                           4, 'Share',
                           5, 'Share Row Exclusive',
                           6, 'Exclusive', 'None') LOCK_LOCKED_MODE        
                FROM 
                    GV$LOCKED_OBJECT A
                    INNER JOIN DBA_OBJECTS B     ON XIDSQN != 0 AND B.OBJECT_ID = A.OBJECT_ID
                    INNER JOIN GV$SESSION S     ON S.SID = A.SESSION_ID AND S.INST_ID = A.INST_ID
                    INNER JOIN GV$SQLAREA SQL     ON S.INST_ID = SQL.INST_ID AND SQL.ADDRESS = S.SQL_ADDRESS AND SQL.HASH_VALUE = S.SQL_HASH_VALUE
                WHERE
                    A.SESSION_ID IN ( SELECT DISTINCT BLOCKING_SESSION FROM GV$SESSION WHERE BLOCKING_SESSION IS NOT NULL )
            )            
        GROUP BY
            LOCK_INST_ID, 
            LOCK_SESSION_ID,
            LOCK_XIDSQN, 
            LOCK_ORACLE_USERNAME, 
            LOCK_OS_USER_NAME, 
            LOCK_SQL_ID,
            LOCK_PREV_SQL_ID,
            LOCK_MODULE
            
            			
    )
    LOOP
            
            -- Libera escrita do usuário que está bloqueando
            flag_user_locked:=1;
        
            -- Quantidade de bloqueios por sessão
            count_blocked:=0;
            
            FOR loop_BLOCKED in (
                SELECT
                        -- Usuários bloqueados
                        S.INST_ID             BLOCKED_INST_ID,
                        S.SID                 BLOCKED_SID,
                        S.USERNAME             BLOCKED_USERNAME,
                        S.OSUSER             BLOCKED_OSUSER,
                        S.ACTION             BLOCKED_ACTION,
                        S.EVENT             BLOCKED_EVENT,
                        SQL.SQL_ID             BLOCKED_SQL_ID,
                        SQL.SQL_FULLTEXT     BLOCKED_SQL_FULLTEXT,
                        SQL.MODULE             BLOCKED_MODULE,                        
                        DECODE(L.LMODE,
                               1, NULL,
                               2, 'Row Share',
                               3, 'Row Exclusive',
                               4, 'Share',
                               5, 'Share Row Exclusive',
                               6, 'Exclusive', 'None') BLOCKED_MODE_HELD,
                         DECODE(L.REQUEST,
                               1, NULL,
                               2, 'Row Share',
                               3, 'Row Exclusive',
                               4, 'Share',
                               5, 'Share Row Exclusive',
                               6, 'Exclusive', 'None') BLOCKED_MODE_REQUESTED,
                         DECODE(L.TYPE,
                               'MR', 'Media Recovery',
                               'RT', 'Redo Thread',
                               'UN', 'User Name',
                               'TX', 'Transaction',
                               'TM', 'DML',
                               'UL', 'PL/SQL User Lock',
                               'DX', 'Distributed Xaction',
                               'CF', 'Control File',
                               'IS', 'Instance State',
                               'FS', 'File Set',
                               'IR', 'Instance Recovery',
                               'ST', 'Disk Space Transaction',
                               'TS', 'Temp Segment',
                               'IV', 'Library Cache Invalidation',
                               'LS', 'Log Start or Log Switch',
                               'RW', 'Row Wait',
                               'SQ', 'Sequence Number',
                               'TE', 'Extend Table',
                               'TT', 'Temp Table',
                               L.TYPE) BLOCKED_TYPE,
                           ROUND( L.CTIME/60, 2 ) BLOCKED_TIME_IN_MINUTES
                               
                    FROM 
                        GV$LOCK L
                        INNER JOIN GV$SESSION S     ON S.INST_ID = L.INST_ID AND S.SID = L.SID
                        INNER JOIN GV$SQLAREA SQL     ON S.INST_ID = SQL.INST_ID AND SQL.ADDRESS = S.SQL_ADDRESS AND SQL.HASH_VALUE = S.SQL_HASH_VALUE
                    WHERE
                        L.ID2 = loop_LOCK.LOCK_XIDSQN 
                        AND L.INST_ID = loop_LOCK.LOCK_INST_ID 
                        AND L.SID != loop_LOCK.LOCK_SESSION_ID
                    ORDER BY ROUND( L.CTIME/60, 2 ) DESC
                    
            )LOOP
            
                count_blocked:= count_blocked + 1;
                
                IF flag_user_locked = 1 THEN
                
                    SELECT SQL_FULLTEXT INTO SQL_LOCK FROM GV$SQLAREA WHERE SQL_ID = loop_LOCK.LOCK_SQL_ID AND INST_ID = loop_LOCK.LOCK_INST_ID;
                    
                    SELECT SQL_FULLTEXT INTO SQL_LOCK_PREV FROM GV$SQLAREA WHERE SQL_ID = loop_LOCK.LOCK_PREV_SQL_ID AND INST_ID = loop_LOCK.LOCK_INST_ID;
                    
                    
                    dbms_output.put_line('.');
                    dbms_output.put_line('.');
                    dbms_output.put_line('--');
                    dbms_output.put_line('------------------------------------------------------------------');
                    dbms_output.put_line('-- USUÁRIO QUE ESTÁ CAUSANDO LOCK');
                    dbms_output.put_line('--');
                    dbms_output.put_line('Inst : '||loop_LOCK.LOCK_INST_ID);
                    dbms_output.put_line('Sid : '||loop_LOCK.LOCK_SESSION_ID);
                    dbms_output.put_line('Username : '||loop_LOCK.LOCK_ORACLE_USERNAME);
                    dbms_output.put_line('OS Username : '||loop_LOCK.LOCK_OS_USER_NAME);
                    dbms_output.put_line('Objetos com lock: ' || loop_LOCK.LOCK_OBJECT_NAME);
                    dbms_output.put_line('Module : '||loop_LOCK.LOCK_MODULE);
                    dbms_output.put_line('SQL ID : '||loop_LOCK.LOCK_SQL_ID);
                    dbms_output.put_line('SQL ID : '||loop_LOCK.LOCK_PREV_SQL_ID);
                    dbms_output.put_line('');
                    dbms_output.put_line('Sql Full Text : '||SQL_LOCK);
                    dbms_output.put_line('');
                    dbms_output.put_line('Prev Sql Full Text : '||SQL_LOCK_PREV);
                    dbms_output.put_line('');
                    dbms_output.put_line('Objetos com lock');
                    dbms_output.put_line('');
                    
                    
                    dbms_output.put_line('LISTA Bind Variable SQL_ID');
                    dbms_output.put_line('');
                    dbms_output.put_line('SQL_ID: ' || loop_LOCK.LOCK_SQL_ID );
                    
                    FOR loop_BIND in ( SELECT NAME,TO_CHAR(LAST_CAPTURED,'DD/MM/YYYY HH24:MI:SS') LAST_CAPTURED, VALUE_STRING FROM V$SQL_BIND_CAPTURE WHERE SQL_ID= loop_LOCK.LOCK_SQL_ID )
                    LOOP
                        
                        dbms_output.put_line('NAME BIND: ' || loop_BIND.NAME );
                        dbms_output.put_line('LAST_CAPTURED: ' || loop_BIND.LAST_CAPTURED );
                        dbms_output.put_line('VALUE_STRING: ' || loop_BIND.VALUE_STRING );
                        dbms_output.put_line('');
                    
                    END LOOP;
                    
                    
                    dbms_output.put_line('');
                    dbms_output.put_line('');
                    dbms_output.put_line('LISTA Bind Variable PREV_SQL_ID');
                    dbms_output.put_line('');
                    dbms_output.put_line('PREV_SQL_ID: ' || loop_LOCK.LOCK_PREV_SQL_ID );
                    
                    FOR loop_BIND in ( SELECT NAME,TO_CHAR(LAST_CAPTURED,'DD/MM/YYYY HH24:MI:SS') LAST_CAPTURED, VALUE_STRING FROM V$SQL_BIND_CAPTURE WHERE SQL_ID = loop_LOCK.LOCK_PREV_SQL_ID )
                    LOOP
                        
                        dbms_output.put_line('NAME BIND: ' || loop_BIND.NAME );
                        dbms_output.put_line('LAST_CAPTURED: ' || loop_BIND.LAST_CAPTURED );
                        dbms_output.put_line('VALUE_STRING: ' || loop_BIND.VALUE_STRING );
                        dbms_output.put_line('');
                    
                    END LOOP;
                    
                    dbms_output.put_line('');
                    dbms_output.put_line('');
                    
                    -- Desativa a flag para escrever apenas uma vez
                    flag_user_locked:= 0;
                    
                END IF;
                
                
                dbms_output.put_line('        --');
                dbms_output.put_line('        ------------------------------------------------------------------');
                dbms_output.put_line('        -- USUÁRIO SOFRENDO LOCK');
                dbms_output.put_line('        --');
                dbms_output.put_line('        Inst : '||loop_BLOCKED.BLOCKED_INST_ID);
                dbms_output.put_line('        Sid : '||loop_BLOCKED.BLOCKED_SID);
                dbms_output.put_line('        Username : '||loop_BLOCKED.BLOCKED_USERNAME);
                dbms_output.put_line('        OS Username : '||loop_BLOCKED.BLOCKED_OSUSER);
                dbms_output.put_line('        Module : '||loop_BLOCKED.BLOCKED_MODULE);
                dbms_output.put_line('        Action : '||loop_BLOCKED.BLOCKED_ACTION);
                dbms_output.put_line('        Event : '||loop_BLOCKED.BLOCKED_EVENT);
                dbms_output.put_line('        Locked Mode : '||loop_BLOCKED.BLOCKED_MODE_HELD);
                dbms_output.put_line('        Locked Mode Request : '||loop_BLOCKED.BLOCKED_MODE_REQUESTED);
                dbms_output.put_line('        Locked Mode Type : '||loop_BLOCKED.BLOCKED_TYPE);
                dbms_output.put_line('        Blocked Minutes : '||loop_BLOCKED.BLOCKED_TIME_IN_MINUTES);
                dbms_output.put_line('        SQL ID : '||loop_BLOCKED.BLOCKED_SQL_ID);
                dbms_output.put_line('        Sql Full Text : '||loop_BLOCKED.BLOCKED_SQL_FULLTEXT);
                dbms_output.put_line('');
                dbms_output.put_line('        LISTA Bind Variable');
                dbms_output.put_line('');
                dbms_output.put_line('              SQL_ID: ' || loop_BLOCKED.BLOCKED_SQL_ID );
                
                
                FOR loop_BIND in ( SELECT NAME,TO_CHAR(LAST_CAPTURED,'DD/MM/YYYY HH24:MI:SS') LAST_CAPTURED, VALUE_STRING FROM V$SQL_BIND_CAPTURE WHERE SQL_ID= loop_BLOCKED.BLOCKED_SQL_ID )
                LOOP
                    
                    dbms_output.put_line('              NAME BIND: ' || loop_BIND.NAME );
                    dbms_output.put_line('              LAST_CAPTURED: ' || loop_BIND.LAST_CAPTURED );
                    dbms_output.put_line('              VALUE_STRING: ' || loop_BIND.VALUE_STRING );
                    dbms_output.put_line('');
                
                END LOOP;
                
                
                dbms_output.put_line('');
                dbms_output.put_line('');
                
                
            END LOOP;
            
			IF flag_user_locked = 0 THEN
			
				dbms_output.put_line('');
                dbms_output.put_line('');
                dbms_output.put_line('------------------------------------------------------------------');
				dbms_output.put_line('.. Quantidade usuários bloqueados por esta sessão');
				dbms_output.put_line('............ Users SOFRENDO LOCK ' || count_blocked);
				dbms_output.put_line('');
				dbms_output.put_line('');
			
			END IF;
			
    END LOOP;
    
END;
-- Executar todo essa procedure anônima
-- FIM
/





