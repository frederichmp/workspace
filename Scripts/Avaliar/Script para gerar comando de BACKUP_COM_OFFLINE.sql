--- EXECUTA BACKUP FULL AMBIENTE 2005+

DECLARE @name sysname
DECLARE @sql nvarchar(max)
DECLARE @datetime nvarchar(20)
DECLARE @baseDir nvarchar(max) 
DECLARE @instanceName nvarchar(max)
DECLARE @dir nvarchar(max)


SET @datetime  = REPLACE(REPLACE(REPLACE(CONVERT(nvarchar(20), GETDATE(), 120), '-', ''), ' ', '_'), ':', '')
SET @baseDir  = 'DIRETORIO DE DESTINO DOS BACKUPS'
SET @instanceName = @@SERVERNAME


DECLARE db_cursor CURSOR FOR
SELECT name
FROM sys.databases
WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb') AND state_desc = 'ONLINE'
ORDER BY name

OPEN db_cursor

FETCH NEXT FROM db_cursor INTO @name

WHILE @@FETCH_STATUS = 0
BEGIN

	SET @sql = 'SCRIPT PARA BASE --> ' + @name + CHAR(10)
	PRINT(@sql)
	
	-- COMANDO PARA MONTAR A ESTRUTURA DE DIRETORIO + NOME DO ARQUIVO
    SET @dir = @baseDir + @instanceName + '\' + @name + '\'
	-- COMANDO PARA CRIAR O DIRETORIO SE POSSIVEL
    SET @sql = 'EXEC xp_create_subdir ''' + @dir + ''''
    PRINT(@sql)
	
	-- COMANDO PARA ALTERAR A BASE DE OFFLINE PARA ONLINE
	SET @sql = 'ALTER DATABASE ' + QUOTENAME(@name) + ' SET ONLINE;'
	PRINT(@sql)
	
	-- COMANDO PARA GERAR O BACKUP MULTIPLEXADO EM 3 ARQUIVOS (ISSO GERA PERFORMANCE)
    SET @sql = 'BACKUP DATABASE ' + QUOTENAME(@name) 
				+ CHAR(10) + ' TO DISK=''' + @dir + @name + '_full_001_' + @datetime + '.bak''' 
				+ CHAR(10) + ',DISK=''' + @dir + @name + '_full_002_' + @datetime + '.bak''' 
				+ CHAR(10) + ',DISK=''' + @dir + @name + '_full_003_' + @datetime + '.bak'' 
				WITH INIT, CHECKSUM, STATS=5;'
    PRINT(@sql)
	
		-- COMANDO PARA ALTERAR A BASE DE OFFLINE PARA OFFLINE DESCONECTANDO TODOS OS USUARIOS
	SET @sql = 'ALTER DATABASE ' + QUOTENAME(@name) + ' SET OFFLINE WITH ROLLBACK IMMEDIATE;'
	PRINT(@sql)
	
	SET @sql = CHAR(10)
	PRINT(@sql)
    FETCH NEXT FROM db_cursor INTO @name
END

CLOSE db_cursor
DEALLOCATE db_cursor