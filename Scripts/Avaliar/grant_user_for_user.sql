-- Cria grant de um usuário para outro usuário

DEFINE NAME_USER_RECEIVE='USERNAME_RECEBE_GRANT'
DEFINE NAME_USER_DELIVERY='USERNAME_ENTREGA_GRANT';


WITH 
    TBL_LIST_PRIVILEGE_OBJECT AS (
          SELECT
               o.OWNER OWNER,
               o.object_type as object_type,
               o.object_name as object_name,
               g object_privilege,
               NVL2(p.privilege, 'Yes', 'No') granted
          FROM dba_objects o
              JOIN (SELECT 'SELECT' g FROM DUAL
                    UNION ALL
                    SELECT 'INSERT' FROM DUAL
                    UNION ALL
                    SELECT 'UPDATE' FROM DUAL
                    UNION ALL
                    SELECT 'DELETE' FROM DUAL
                    UNION ALL
                    SELECT 'EXECUTE' FROM DUAL)
                  ON (o.object_type = 'TABLE' AND g != 'EXECUTE')
                  OR (o.object_type = 'SEQUENCE' AND g = 'SELECT')
                  OR (o.object_type IN ('PACKAGE', 'FUNCTION', 'PROCEDURE', 'TYPE') AND g = 'EXECUTE')
              LEFT OUTER JOIN dba_tab_privs p
                  ON p.table_name = o.object_name
                  AND p.owner = o.owner
                 --AND p.grantee = 'SCHEMA_B'
                 AND p.privilege = g
         WHERE 
             o.owner = '&&NAME_USER_DELIVERY' AND
             o.object_type IN ('TABLE', 'PACKAGE', 'FUNCTION', 'PROCEDURE', 'TYPE', 'SEQUENCE')
    ),
    TBL_GRANT AS (
            SELECT
                OWNER,
                OBJECT_TYPE, 
                OBJECT_NAME, 
                LISTAGG(object_privilege, ', ') WITHIN GROUP (ORDER BY object_privilege) "PRIVILEGE"
            FROM
                TBL_LIST_PRIVILEGE_OBJECT
            GROUP BY
                OWNER, object_type, object_name         
    ),
    TBL_LIST_PRIVILEGE_USER AS (
        select * from (
            select 'GRANT '||privilege||' TO "' || UPPER( '&&NAME_USER_RECEIVE' ) || '";' AS GRANT_USER from dba_sys_privs
            where grantee = UPPER( '&&NAME_USER_DELIVERY' )
        union all
            select 'GRANT '||privilege||' ON '||grantor||'.'||table_name||' TO "' || UPPER( '&&NAME_USER_RECEIVE' ) || '";' from dba_tab_privs
            where grantee = UPPER( '&&NAME_USER_DELIVERY' )
        union all
            select 'GRANT '||GRANTED_ROLE||' TO "' || UPPER( '&&NAME_USER_RECEIVE' ) || '";' from dba_role_privs
            where grantee = UPPER( '&&NAME_USER_DELIVERY' ))
    ),
    TBL_UNION_GRANT AS (
        SELECT
            GRANT_USER
        FROM
            TBL_LIST_PRIVILEGE_USER
        UNION ALL
        SELECT
            'GRANT '|| PRIVILEGE ||' ON '|| OWNER ||'.'|| OBJECT_NAME ||' TO "'|| UPPER( '&&NAME_USER_RECEIVE' ) ||'";' SET_GRANT
        FROM
            TBL_GRANT
    )
SELECT
    GRANT_USER
FROM
    TBL_UNION_GRANT;
	
	
	