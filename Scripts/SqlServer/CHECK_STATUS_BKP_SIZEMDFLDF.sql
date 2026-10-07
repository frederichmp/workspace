--- STATUS BACKUP

SELECT bs.database_name AS DatabaseName
, CAST(bs.backup_size/1024.0/1024/1024 AS DECIMAL(10, 2)) AS BackupSizeGB
, CAST(bs.backup_size/1024.0/1024 AS DECIMAL(10, 2)) AS BackupSizeMB
--, CAST(bs.compressed_backup_size/1024.0/1024/1024 AS DECIMAL(10, 2)) AS CompressedSizeGB   
--, CAST(bs.compressed_backup_size/1024.0/1024 AS DECIMAL(10, 2)) AS CompressedSizeMB
, bs.backup_start_date AS BackupStartDate
, bs.backup_finish_date AS BackupEndDate
, CAST(bs.backup_finish_date - bs.backup_start_date AS dateTIME) AS AmtTimeToBkup
, bmf.physical_device_name AS BackupDeviceName
FROM msdb.dbo.backupset bs JOIN msdb.dbo.backupmediafamily bmf
ON bs.media_set_id = bmf.media_set_id
WHERE
--bs.database_name = 'MyDatabase' and
bs.backup_start_date > DATEADD(dd, -1, GETDATE())
and bs.type = 'D' -- change to L for transaction logs
and bmf.physical_device_name like '%REFRESH_DTC%'
ORDER BY BackupSizeGB desc


--- TAMANHO MDF LDF
USE master;
GO
SELECT DB_NAME(database_id) AS DatabaseName,
CAST(SUM(CASE WHEN type_desc = 'ROWS' THEN size END) * 8 / 1024.00 AS DECIMAL(18,2)) AS DataFileSizeMB,
CAST(SUM(CASE WHEN type_desc = 'LOG' THEN size END) * 8 / 1024.00 AS DECIMAL(18,2)) AS LogFileSizeMB
FROM sys.master_files
WHERE DB_NAME(database_id) NOT IN ('master', 'tempdb', 'model', 'msdb') AND state_desc = 'ONLINE'
GROUP BY database_id
ORDER BY DataFileSizeMB desc;