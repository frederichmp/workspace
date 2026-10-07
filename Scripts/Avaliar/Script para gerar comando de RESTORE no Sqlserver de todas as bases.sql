DECLARE @DataDir NVARCHAR(100) = 'DATA' -- Substitua pelo nome do diretório de dados
DECLARE @LogDir NVARCHAR(100) = 'LOG' -- Substitua pelo nome do diretório de logs
DECLARE @sql NVARCHAR(MAX)
DECLARE @sqlfull NVARCHAR(MAX)
DECLARE @sqltlog NVARCHAR(MAX)
DECLARE @dbName NVARCHAR(100)
DECLARE @mdasetid NVARCHAR(100)
DECLARE @count NVARCHAR(100) = (SELECT CHAR(13) + '--QUANTIDADE DE DATABASES ---> ' + CAST(COUNT(*) AS VARCHAR) FROM sys.databases WHERE name NOT IN ('master','model','msdb','tempdb'))
DECLARE @comp NVARCHAR(100)

DECLARE db_cursorFull CURSOR FOR
SELECT name FROM sys.databases WHERE name not in ('master','model','msdb','tempdb') and state_desc <> 'OFFLINE'

OPEN db_cursorFull
FETCH NEXT FROM db_cursorFull INTO @dbName

WHILE @@FETCH_STATUS = 0
BEGIN

	--- CRIA O COMANDO DE RESTORE FULL DA BASE POREM EM NORECOVERY
	SELECT @comp = compatibility_level from sys.databases where name = @dbName;
	
    SELECT @sqlfull = 'RESTORE DATABASE [' + @dbName + '] FROM ' + 
	STUFF((
		SELECT 'DISK = ''' + bm.BackupDirectory + bm.BackupFile + ''',' + CHAR(10)
		FROM (SELECT
                    LEFT(bmf.physical_device_name, LEN(bmf.physical_device_name) - CHARINDEX('\', REVERSE(bmf.physical_device_name)) + 1) AS BackupDirectory,
                    CASE WHEN CHARINDEX('\', REVERSE(bmf.physical_device_name)) > 0 
                        THEN RIGHT(bmf.physical_device_name, CHARINDEX('\', REVERSE(bmf.physical_device_name)) - 1) 
                        ELSE bmf.physical_device_name END AS BackupFile,
						backup_finish_date
                FROM msdb.dbo.backupmediafamily AS bmf
                INNER JOIN msdb.dbo.backupset AS bs ON bmf.media_set_id = bs.media_set_id
                WHERE bs.database_name = @dbName
				AND bmf.media_set_id = (select max(bmf.media_set_id) from msdb.dbo.backupmediafamily bmf INNER JOIN msdb.dbo.backupset AS bs ON									bmf.media_set_id = bs.media_set_id WHERE bs.database_name = @dbName 
										AND bs.type = 'D' )
                AND bs.type = 'D'
                AND bs.is_copy_only = 0
                ) bm
				ORDER BY bm.backup_finish_date DESC
		FOR XML PATH(''), TYPE
	).value('.', 'NVARCHAR(MAX)'), LEN((
		SELECT 'DISK = ''' + bm.BackupDirectory + bm.BackupFile + ''',' + CHAR(10)
		FROM (SELECT
                    LEFT(bmf.physical_device_name, LEN(bmf.physical_device_name) - CHARINDEX('\', REVERSE(bmf.physical_device_name)) + 1) AS BackupDirectory,
                    CASE WHEN CHARINDEX('\', REVERSE(bmf.physical_device_name)) > 0 
                        THEN RIGHT(bmf.physical_device_name, CHARINDEX('\', REVERSE(bmf.physical_device_name)) - 1) 
                        ELSE bmf.physical_device_name END AS BackupFile,
						backup_finish_date
                FROM msdb.dbo.backupmediafamily AS bmf
                INNER JOIN msdb.dbo.backupset AS bs ON bmf.media_set_id = bs.media_set_id
                WHERE bs.database_name = @dbName
				AND bmf.media_set_id = (select max(bmf.media_set_id) from msdb.dbo.backupmediafamily bmf INNER JOIN msdb.dbo.backupset AS bs ON									bmf.media_set_id = bs.media_set_id WHERE bs.database_name = @dbName 
										AND bs.type = 'D' )
                AND bs.type = 'D'
                AND bs.is_copy_only = 0
                ) bm
				ORDER BY bm.backup_finish_date DESC
		FOR XML PATH(''), TYPE
	).value('.', 'NVARCHAR(MAX)')) - 1, 1, '') + ' WITH REPLACE, NORECOVERY' + CHAR(10) +
	(
		SELECT
			CHAR(9) + ', MOVE ''' + name + ''' TO ''' + CASE type_desc WHEN 'ROWS' THEN @DataDir + '\' + RIGHT(physical_name, CHARINDEX('\', REVERSE(physical_name)) - 1)
																		WHEN 'LOG' THEN @LogDir + '\' + RIGHT(physical_name, CHARINDEX('\', REVERSE(physical_name)) - 1)
																		ELSE physical_name END + '''' + CHAR(10)
		FROM sys.master_files
		WHERE database_id = DB_ID(@dbName)
		FOR XML PATH(''), TYPE
	).value('.', 'NVARCHAR(MAX)') + ', NOUNLOAD, STATS=10, MAXTRANSFERSIZE = 1048576;' + CHAR(10)
    FROM sys.databases
	WHERE database_id = db_id(@dbName)

    PRINT (@sqlfull)
	---- FIM DO COMANDO RESTORE FULL

	--- GERA O COMANDO PARA RESTAURACAO DE LOGS SE HOUVER

	DECLARE db_cursorTlog CURSOR FOR
	SELECT distinct bmf.media_set_id
	FROM msdb.dbo.backupmediafamily AS bmf
	INNER JOIN msdb.dbo.backupset AS bs ON bmf.media_set_id = bs.media_set_id
	WHERE bs.database_name = @dbName
	AND bs.backup_finish_date > (select max(bs.backup_finish_date) 
								from msdb.dbo.backupmediafamily bmf 
								INNER JOIN msdb.dbo.backupset AS bs ON bmf.media_set_id = bs.media_set_id 
								WHERE bs.database_name = @dbName 
								AND bs.type = 'D' )
	AND bs.type = 'L'
	AND bs.is_copy_only = 0

	OPEN db_cursorTlog
	FETCH NEXT FROM db_cursorTlog INTO @mdasetid

	WHILE @@FETCH_STATUS = 0
	BEGIN
    SELECT @sqltlog = 'RESTORE LOG [' + @dbName + '] FROM ' + 
	STUFF((
		SELECT 'DISK = ''' + bm.BackupDirectory + bm.BackupFile + ''',' + CHAR(10)
		FROM (SELECT 
                    LEFT(bmf.physical_device_name, LEN(bmf.physical_device_name) - CHARINDEX('\', REVERSE(bmf.physical_device_name)) + 1) AS BackupDirectory,
                    CASE WHEN CHARINDEX('\', REVERSE(bmf.physical_device_name)) > 0 
                        THEN RIGHT(bmf.physical_device_name, CHARINDEX('\', REVERSE(bmf.physical_device_name)) - 1) 
                        ELSE bmf.physical_device_name END AS BackupFile,
						bs.backup_finish_date
                FROM msdb.dbo.backupmediafamily AS bmf
                INNER JOIN msdb.dbo.backupset AS bs ON bmf.media_set_id = bs.media_set_id
                WHERE bs.database_name = @dbName
				AND bs.backup_finish_date > (select max(bs.backup_finish_date) from msdb.dbo.backupmediafamily bmf INNER JOIN msdb.dbo.backupset AS bs ON									bmf.media_set_id = bs.media_set_id WHERE bs.database_name = @dbName 
										AND bs.type = 'D' )
				AND bmf.media_set_id = @mdasetid
                AND bs.type = 'L'
                AND bs.is_copy_only = 0
                ) bm
				ORDER BY bm.backup_finish_date DESC
		FOR XML PATH(''), TYPE
	).value('.', 'NVARCHAR(MAX)'), LEN((
		SELECT 'DISK = ''' + bm.BackupDirectory + bm.BackupFile + ''',' + CHAR(10)
		FROM (SELECT 
                    LEFT(bmf.physical_device_name, LEN(bmf.physical_device_name) - CHARINDEX('\', REVERSE(bmf.physical_device_name)) + 1) AS BackupDirectory,
                    CASE WHEN CHARINDEX('\', REVERSE(bmf.physical_device_name)) > 0 
                        THEN RIGHT(bmf.physical_device_name, CHARINDEX('\', REVERSE(bmf.physical_device_name)) - 1) 
                        ELSE bmf.physical_device_name END AS BackupFile,
						bs.backup_finish_date
                FROM msdb.dbo.backupmediafamily AS bmf
                INNER JOIN msdb.dbo.backupset AS bs ON bmf.media_set_id = bs.media_set_id
                WHERE bs.database_name = @dbName
				AND bs.backup_finish_date > (select max(bs.backup_finish_date) from msdb.dbo.backupmediafamily bmf INNER JOIN msdb.dbo.backupset AS bs ON									bmf.media_set_id = bs.media_set_id WHERE bs.database_name = @dbName 
										AND bs.type = 'D' )
				AND bmf.media_set_id = @mdasetid
                AND bs.type = 'L'
                AND bs.is_copy_only = 0
                ) bm
				ORDER BY bm.backup_finish_date DESC
		FOR XML PATH(''), TYPE
	).value('.', 'NVARCHAR(MAX)')) - 1, 1, '') + ' WITH REPLACE, NORECOVERY' + CHAR(10) + ', NOUNLOAD, STATS=10, MAXTRANSFERSIZE = 1048576;' + CHAR(10)
    FROM sys.databases
	WHERE database_id = db_id(@dbName)

	PRINT (@sqltlog)

	FETCH NEXT FROM db_cursorTlog INTO @mdasetid
	END

	CLOSE db_cursorTlog
	DEALLOCATE db_cursorTlog

/*
	BEGIN
		SET @sql = 'RESTORE DATABASE [' + @dbName + '] WITH RECOVERY;' + CHAR(10) + 'ALTER DATABASE [' + @dbName + '] SET COMPATIBILITY_LEVEL=' + @comp + ';' + CHAR(10) + CHAR(10)
	END

	PRINT (@sql)
    
 */
    FETCH NEXT FROM db_cursorFull INTO @dbName
	
END

CLOSE db_cursorFull
DEALLOCATE db_cursorFull



print (@count)