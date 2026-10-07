--- COLOCA AS BASES EM MODO SIMPLES FAZ SHRINK E TROCA OWNER

DECLARE @name sysname
DECLARE @sql nvarchar(max)
DECLARE @use_template nvarchar(max)


DECLARE db_cursor CURSOR FOR
SELECT name
FROM sys.databases
WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')

OPEN db_cursor

FETCH NEXT FROM db_cursor INTO @name

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sql = 'ALTER DATABASE ' + QUOTENAME(@name) + ' SET RECOVERY SIMPLE;'
    EXEC(@sql)
	SET @sql = N'ALTER AUTHORIZATION ON DATABASE::[' + @name + '] TO [sa];';    
	EXEC sp_executesql @sql;
    
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
