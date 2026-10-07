-- CONFIGURAÇÕES
DECLARE @LoginOrigem SYSNAME = 'usuario_origem'; -- Ex: 'sa' ou 'DOMINIO\\usuario'
DECLARE @LoginClone SYSNAME = 'usuario_clone';   -- Ex: 'sa_clone' ou 'DOMINIO\\usuario2'
DECLARE @Senha NVARCHAR(128) = 'SenhaForte#2024'; -- Só usada se for login SQL

-- DETECTAR TIPO DO LOGIN DE ORIGEM
DECLARE @TipoLoginOrigem NVARCHAR(60);
SELECT @TipoLoginOrigem = type_desc FROM sys.server_principals WHERE name = @LoginOrigem;

IF @TipoLoginOrigem IS NULL
BEGIN
    RAISERROR('Login de origem não encontrado.', 16, 1);
    RETURN;
END

-- CRIAR LOGIN CLONE
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = @LoginClone)
BEGIN
    IF @TipoLoginOrigem = 'WINDOWS_LOGIN'
        EXEC('CREATE LOGIN [' + @LoginClone + '] FROM WINDOWS;');
    ELSE IF @TipoLoginOrigem = 'SQL_LOGIN'
        EXEC('CREATE LOGIN [' + @LoginClone + '] WITH PASSWORD = N''' + @Senha + ''', CHECK_POLICY = OFF;');
    ELSE
        RAISERROR('Tipo de login não suportado.', 16, 1);
END

-- COPIAR PERMISSÕES DE SERVIDOR
DECLARE @PermissaoServidor NVARCHAR(MAX) = '';
SELECT @PermissaoServidor +=
    CASE 
        WHEN state_desc = 'GRANT_WITH_GRANT_OPTION' THEN 'GRANT ' + permission_name + ' TO [' + @LoginClone + '] WITH GRANT OPTION;' + CHAR(13)
        ELSE state_desc + ' ' + permission_name + ' TO [' + @LoginClone + '];' + CHAR(13)
    END
FROM sys.server_permissions
WHERE grantee_principal_id = SUSER_ID(@LoginOrigem);

EXEC sp_executesql @PermissaoServidor;

-- LOOP DE DATABASES PARA CRIAR USER E COPIAR PERMISSÕES
DECLARE @DBName SYSNAME;
DECLARE @SQLBase NVARCHAR(MAX);
DECLARE @SQL NVARCHAR(MAX);

DECLARE db_cursor CURSOR FOR
SELECT name FROM sys.databases WHERE state_desc = 'ONLINE' AND database_id > 4;

SET @SQLBase = '
USE [{DBNAME}];
BEGIN TRY
    IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name = ''{LOGINORIGEM}'')
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = ''{LOGINCLONE}'')
        BEGIN
            CREATE USER [{LOGINCLONE}] FOR LOGIN [{LOGINCLONE}];
            PRINT ''[OK] USER [{LOGINCLONE}] criado em [{DBNAME}]'';
        END
        ELSE
        BEGIN
            ALTER USER [{LOGINCLONE}] WITH LOGIN = [{LOGINCLONE}];
            PRINT ''[OK] USER [{LOGINCLONE}] remapeado em [{DBNAME}]'';
        END

        DECLARE @Permissoes NVARCHAR(MAX) = (
            SELECT STRING_AGG(
                CASE 
                    WHEN class = 1 AND OBJECT_NAME(major_id) IS NOT NULL THEN
                        CASE state_desc
                            WHEN ''GRANT_WITH_GRANT_OPTION'' THEN ''GRANT '' + permission_name + '' ON ['' + OBJECT_NAME(major_id) + ''] TO [{LOGINCLONE}] WITH GRANT OPTION;'' 
                            ELSE state_desc + '' '' + permission_name + '' ON ['' + OBJECT_NAME(major_id) + ''] TO [{LOGINCLONE}];''
                        END
                    WHEN class = 3 AND SCHEMA_NAME(major_id) IS NOT NULL THEN
                        CASE state_desc
                            WHEN ''GRANT_WITH_GRANT_OPTION'' THEN ''GRANT '' + permission_name + '' ON SCHEMA::['' + SCHEMA_NAME(major_id) + ''] TO [{LOGINCLONE}] WITH GRANT OPTION;'' 
                            ELSE state_desc + '' '' + permission_name + '' ON SCHEMA::['' + SCHEMA_NAME(major_id) + ''] TO [{LOGINCLONE}];''
                        END
                    ELSE NULL
                END, CHAR(13))
            FROM sys.database_permissions
            WHERE grantee_principal_id = USER_ID(''{LOGINORIGEM}'')
        );

        IF @Permissoes IS NOT NULL
            EXEC sp_executesql @Permissoes;
    END
    ELSE
    BEGIN
        PRINT ''[SKIP] Usuário origem não existe em [{DBNAME}]'';
    END
END TRY
BEGIN CATCH
    PRINT ''[ERRO] em [{DBNAME}]: '' + ERROR_MESSAGE();
END CATCH
';

-- EXECUTAR PARA CADA BASE
OPEN db_cursor;
FETCH NEXT FROM db_cursor INTO @DBName;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @SQL = REPLACE(@SQLBase, '{DBNAME}', @DBName);
    SET @SQL = REPLACE(@SQL, '{LOGINORIGEM}', @LoginOrigem);
    SET @SQL = REPLACE(@SQL, '{LOGINCLONE}', @LoginClone);

    EXEC (@SQL);

    FETCH NEXT FROM db_cursor INTO @DBName;
END

CLOSE db_cursor;
DEALLOCATE db_cursor;
