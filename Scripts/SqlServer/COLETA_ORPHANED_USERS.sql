-- Variável temporária para armazenar o resultado do comando 'sp_change_users_login Report'
DECLARE @UserList TABLE (UserName NVARCHAR(255),UserSID NVARCHAR(255))

-- Executar o comando 'sp_change_users_login Report' e armazenar o resultado na variável
INSERT INTO @UserList (UserName,UserSID)
EXEC sp_change_users_login 'Report'

-- Loop através da lista de usuários órfãos e gerar comandos Auto_Fix
DECLARE @UserName NVARCHAR(255)
DECLARE @AutoFixCommand NVARCHAR(MAX)

DECLARE UserCursor CURSOR FOR
SELECT UserName FROM @UserList

OPEN UserCursor

FETCH NEXT FROM UserCursor INTO @UserName

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @AutoFixCommand = 'EXEC sp_change_users_login ''Auto_Fix'', ''' + @UserName + ''''
    PRINT @AutoFixCommand -- Exibir o comando gerado (opcional)
    -- Executar o comando Auto_Fix
    -- EXEC sp_executesql @AutoFixCommand
    
    FETCH NEXT FROM UserCursor INTO @UserName
END

CLOSE UserCursor
DEALLOCATE UserCursor