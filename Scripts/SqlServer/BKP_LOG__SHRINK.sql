--- EXECUTA BACKUP LOG COM SHRINK AMBIENTE 2005

DECLARE @name sysname
DECLARE @sql nvarchar(max)
DECLARE @datetime nvarchar(20)
DECLARE @baseDir nvarchar(max) 
DECLARE @instanceName nvarchar(max)
DECLARE @dir nvarchar(max)
DECLARE @nomebanco nvarchar(100)
DECLARE @nomelog nvarchar(100)
DECLARE @use_template varchar(max)


SET @datetime  = REPLACE(REPLACE(REPLACE(CONVERT(nvarchar(20), GETDATE(), 120), '-', ''), ' ', '_'), ':', '')
SET @baseDir  = '\\agnet.local\backup\Dumps03\REFRESH_DTC\'
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
    SET @dir = @baseDir + @instanceName + '\' + @name + '\'
    SET @sql = 'EXEC xp_create_subdir ''' + @dir + ''''
    EXEC(@sql)
	SET @sql = 'ALTER DATABASE ' + QUOTENAME(@name) + ' SET RECOVERY FULL;'
	EXEC(@sql)
    SET @sql = 'BACKUP LOG ' + QUOTENAME(@name) + ' TO DISK=''' + @dir + @name + '_tran_' + @datetime + '.bak'' WITH INIT, CHECKSUM, STATS=10;'    
	EXEC(@sql)
	
	-- SHRINNK DO ARQUIVO DE LOG
	SET @use_template = 'USE ' + QUOTENAME(@name) + '
	DECLARE @nomelog nvarchar(100)
	SELECT @nomelog = name FROM sys.database_files WHERE type_desc = ''LOG''
	SELECT @nomelog
	DBCC SHRINKFILE (@nomelog, 1)'
	
	DECLARE @sql_script nvarchar(MAX)
	SET @sql_script = REPLACE(@use_template, '{@name}', @name)
	EXEC(@sql_script)
	
	
    FETCH NEXT FROM db_cursor INTO @name
END

CLOSE db_cursor
DEALLOCATE db_cursor