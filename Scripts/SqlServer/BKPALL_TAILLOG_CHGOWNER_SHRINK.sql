--- EXECUTA BACKUP FULL AMBIENTE 2005

DECLARE @name sysname
DECLARE @sql nvarchar(max)
DECLARE @datetime nvarchar(20)
DECLARE @baseDir nvarchar(max) 
DECLARE @instanceName nvarchar(max)
DECLARE @dir nvarchar(max)


SET @datetime  = REPLACE(REPLACE(REPLACE(CONVERT(nvarchar(20), GETDATE(), 120), '-', ''), ' ', '_'), ':', '')
SET @baseDir  = 'E:\BACKUPs\REFRESH_DTC\'
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
    PRINT(@sql)
	SET @sql = 'ALTER DATABASE ' + QUOTENAME(@name) + ' SET RECOVERY FULL;'
	PRINT(@sql)
    SET @sql = 'BACKUP DATABASE ' + QUOTENAME(@name) 
	+ CHAR(10) + ' TO DISK=''' + @dir + @name + '_full_001_' + @datetime + '.bak''' 
	+ CHAR(10) + ',DISK=''' + @dir + @name + '_full_002_' + @datetime + '.bak''' 
	+ CHAR(10) + ',DISK=''' + @dir + @name + '_full_003_' + @datetime + '.bak'' WITH INIT, CHECKSUM, COMPRESSION, STATS=5;'
    PRINT(@sql)
    FETCH NEXT FROM db_cursor INTO @name
END

CLOSE db_cursor
DEALLOCATE db_cursor

--- EXECUTA BACKUP DIFERENCIAL

DECLARE @name sysname
DECLARE @sql nvarchar(max)
DECLARE @datetime nvarchar(20) = REPLACE(REPLACE(REPLACE(CONVERT(nvarchar(20), GETDATE(), 120), '-', ''), ' ', '_'), ':', '')
DECLARE @baseDir nvarchar(max) = '\\agnet.local\backup\Dumps03\REFRESH_DTC\'
DECLARE @instanceName nvarchar(max) = @@SERVERNAME

DECLARE db_cursor CURSOR FOR
SELECT name
FROM sys.databases
WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb') AND state_desc = 'ONLINE'

OPEN db_cursor

FETCH NEXT FROM db_cursor INTO @name

WHILE @@FETCH_STATUS = 0
BEGIN
    DECLARE @dir nvarchar(max) = @baseDir + @instanceName + '\' + @name + '\'
    SET @sql = 'EXEC xp_create_subdir ''' + @dir + ''''
    EXEC(@sql)
	SET @sql = 'ALTER DATABASE ' + QUOTENAME(@name) + ' SET RECOVERY FULL;'
	EXEC(@sql)
    SET @sql = 'BACKUP DATABASE ' + QUOTENAME(@name) + ' TO DISK=''' + @dir + @name + '_diff_' + @datetime + '.bak'' WITH DIFFERENTIAL, COMPRESSION, CHECKSUM, STATS=5;'
    EXEC(@sql)
    FETCH NEXT FROM db_cursor INTO @name
END

CLOSE db_cursor
DEALLOCATE db_cursor


--- EXECUTA BACKUP DE LOG

DECLARE @name sysname
DECLARE @sql nvarchar(max)
DECLARE @datetime nvarchar(20) = REPLACE(REPLACE(REPLACE(CONVERT(nvarchar(20), GETDATE(), 120), '-', ''), ' ', '_'), ':', '')
DECLARE @baseDir nvarchar(max) = '\\agnet.local\backup\Dumps03\REFRESH_DTC\'
DECLARE @instanceName nvarchar(max) = @@SERVERNAME

DECLARE db_cursor CURSOR FOR
SELECT name
FROM sys.databases
WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb') AND state_desc = 'ONLINE'

OPEN db_cursor

FETCH NEXT FROM db_cursor INTO @name

WHILE @@FETCH_STATUS = 0
BEGIN
    DECLARE @dir nvarchar(max) = @baseDir + @instanceName + '\' + @name + '\'
    SET @sql = 'EXEC xp_create_subdir ''' + @dir + ''''
    EXEC(@sql)
    SET @sql = 'BACKUP LOG ' + QUOTENAME(@name) + ' TO DISK=''' + @dir + @name + '_tran_' + @datetime + '.bak'' WITH INIT, COMPRESSION, CHECKSUM, STATS=5;'
    EXEC(@sql)
    FETCH NEXT FROM db_cursor INTO @name
END

CLOSE db_cursor
DEALLOCATE db_cursor


--- EXECUTA O TAILLOG 

DECLARE @name sysname
DECLARE @sql nvarchar(max)
DECLARE @datetime nvarchar(20) = REPLACE(REPLACE(REPLACE(CONVERT(nvarchar(20), GETDATE(), 120), '-', ''), ' ', '_'), ':', '')
DECLARE @baseDir nvarchar(max) = '\\agnet.local\backup\Dumps03\REFRESH_DTC\'
DECLARE @instanceName nvarchar(max) = @@SERVERNAME

DECLARE db_cursor CURSOR FOR
SELECT name
FROM sys.databases
WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb') AND state_desc = 'ONLINE'

OPEN db_cursor

FETCH NEXT FROM db_cursor INTO @name

WHILE @@FETCH_STATUS = 0
BEGIN
    DECLARE @dir nvarchar(max) = @baseDir + @instanceName + '\' + @name + '\'
    SET @sql = 'EXEC xp_create_subdir ''' + @dir + ''''
    EXEC(@sql)
    SET @sql = 'ALTER DATABASE ' + QUOTENAME(@name) + ' SET OFFLINE WITH ROLLBACK IMMEDIATE;'
    EXEC(@sql)
    SET @sql = 'ALTER DATABASE ' + QUOTENAME(@name) + ' SET ONLINE;'
    EXEC(@sql)	
    SET @sql = 'BACKUP LOG ' + QUOTENAME(@name) + ' TO DISK=''' + @dir + @name + '__tail_tran_' + @datetime + '.bak'' WITH NORECOVERY, INIT, COMPRESSION, CHECKSUM, STATS=5;'
    EXEC(@sql)
    FETCH NEXT FROM db_cursor INTO @name
END

CLOSE db_cursor
DEALLOCATE db_cursor


--- TIRA A BASE DE RESTORING....  

DECLARE @name sysname
DECLARE @sql nvarchar(max)

DECLARE db_cursor CURSOR FOR
SELECT name
FROM sys.databases
WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')

OPEN db_cursor

FETCH NEXT FROM db_cursor INTO @name

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sql = 'RESTORE DATABASE ' + QUOTENAME(@name) + ' WITH RECOVERY;'
    EXEC(@sql)
    FETCH NEXT FROM db_cursor INTO @name
END

CLOSE db_cursor
DEALLOCATE db_cursor

--- COLOCA AS BASES EM OFFLINE (A BASE NAO PODE ESTAR EM RESTORING)

DECLARE @name sysname
DECLARE @sql nvarchar(max)

DECLARE db_cursor CURSOR FOR
SELECT name
FROM sys.databases
WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')

OPEN db_cursor

FETCH NEXT FROM db_cursor INTO @name

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sql = 'ALTER DATABASE ' + QUOTENAME(@name) + ' SET OFFLINE WITH ROLLBACK IMMEDIATE;'
    PRINT(@sql)
    FETCH NEXT FROM db_cursor INTO @name
END

CLOSE db_cursor
DEALLOCATE db_cursor

--- COLOCA AS BASES EM MODO SIMPLES

DECLARE @name sysname
DECLARE @sql nvarchar(max)

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
    FETCH NEXT FROM db_cursor INTO @name
END

CLOSE db_cursor
DEALLOCATE db_cursor

--- TROCA EM TODAS AS BASES O OWNER PARA O SA

USE master;  
DECLARE @dbname NVARCHAR(255);
DECLARE @sql NVARCHAR(MAX);  

DECLARE db_cursor CURSOR FOR
SELECT name
FROM sys.databases
WHERE owner_sid <> 0x01 
AND state = 0;  

OPEN db_cursor;
FETCH NEXT FROM db_cursor INTO @dbname;  

WHILE @@FETCH_STATUS = 0
BEGIN    
	SET @sql = N'ALTER AUTHORIZATION ON DATABASE::[' + @dbname + '] TO [sa];';    
	EXEC sp_executesql @sql;    
	
	FETCH NEXT FROM db_cursor INTO @dbname;
END;  

CLOSE db_cursor;
DEALLOCATE db_cursor;
