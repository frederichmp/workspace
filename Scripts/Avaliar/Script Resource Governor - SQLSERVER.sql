----------------------------------------------------------------------------------------------
-- CONFIGURANDO O RESOURCE GOVERNOR PARA SQLSERVER
----------------------------------------------------------------------------------------------

USE [master]
GO

----------------------------------------------------------------------------------------------
-- "Limpeza" do Resource Governor
----------------------------------------------------------------------------------------------

ALTER RESOURCE GOVERNOR WITH (CLASSIFIER_FUNCTION=NULL)
GO

ALTER RESOURCE GOVERNOR RECONFIGURE
GO
ALTER RESOURCE GOVERNOR DISABLE
GO


----------------------------------------------------------------------------------------------
-- Criação do Pool de Recursos
----------------------------------------------------------------------------------------------
CREATE RESOURCE POOL alta_prioridade
WITH (MIN_CPU_PERCENT=50, 
    MAX_CPU_PERCENT=100, 
    CAP_CPU_PERCENT=100,
    MIN_MEMORY_PERCENT=50, 
    MAX_MEMORY_PERCENT=100)
GO

CREATE RESOURCE POOL baixa_prioridade
WITH (MIN_CPU_PERCENT=0, 
    MAX_CPU_PERCENT=10, 
    CAP_CPU_PERCENT=10,
    MIN_MEMORY_PERCENT=0, 
    MAX_MEMORY_PERCENT=10, 
    MIN_IOPS_PER_VOLUME=0, 
    MAX_IOPS_PER_VOLUME=300)
GO

----------------------------------------------------------------------------------------------
-- Criação do Workload Group
----------------------------------------------------------------------------------------------
CREATE WORKLOAD GROUP alta_prioridade
WITH (
    IMPORTANCE=HIGH, 
    MAX_DOP=8
)
USING [alta_prioridade] -- Alocação de recursos de alta prioridade
GO

CREATE WORKLOAD GROUP baixa_prioridade
WITH (
    GROUP_MAX_REQUESTS=0, 
    IMPORTANCE=LOW, 
    REQUEST_MAX_CPU_TIME_SEC=2, 
    REQUEST_MAX_MEMORY_GRANT_PERCENT=25, 
    REQUEST_MEMORY_GRANT_TIMEOUT_SEC=0, 
    MAX_DOP=0
)
USING [baixa_prioridade] -- Alocação de recursos de baixa prioridade
GO

----------------------------------------------------------------------------------------------
-- Criação da função de classificação
----------------------------------------------------------------------------------------------
CREATE FUNCTION dbo.classify_users_machines()
RETURNS sysname
WITH SCHEMABINDING
AS
BEGIN
	DECLARE @grp_name sysname;
    DECLARE @UserName VARCHAR(200) = ORIGINAL_LOGIN();

	IF (HOST_NAME() = 'MGDKP0251')
		SET @grp_name = 'alta_prioridade';
	ELSE IF (@UserName IN ('startupadmin'))
		SET @grp_name = 'alta_prioridade';
    ELSE
        SET @grp_name = 'baixa_prioridade';

		RETURN @grp_name;
END
GO

----------------------------------------------------------------------------------------------
-- Habilita o Resource Governor, aplica a função de classificação e confirma as alterações
----------------------------------------------------------------------------------------------

ALTER RESOURCE GOVERNOR WITH (CLASSIFIER_FUNCTION=dbo.classify_users_machines)
GO

ALTER RESOURCE GOVERNOR RECONFIGURE
GO

ALTER RESOURCE GOVERNOR ENABLE
GO

----------------------------------------------------------------------------------------------
-- Desabilita o Resource Governor / Com DROP do POOL e GRUPO
----------------------------------------------------------------------------------------------
ALTER RESOURCE GOVERNOR WITH (CLASSIFIER_FUNCTION = NULL)
GO

DECLARE @Query VARCHAR(MAX) = ''
SELECT @Query += 'DROP WORKLOAD GROUP ' + QUOTENAME(name) + ';' 
FROM sys.resource_governor_workload_groups
WHERE [name] not in ('internal','default'); 

EXEC(@Query)
--PRINT @Query

SET @Query = ''

SELECT @Query += 'DROP RESOURCE POOL ' + QUOTENAME([name]) + ';'
FROM sys.resource_governor_resource_pools
WHERE [name] NOT IN ('internal','DEFAULT'); 

EXEC(@Query)
--PRINT @Query

ALTER RESOURCE GOVERNOR RECONFIGURE;
GO
ALTER RESOURCE GOVERNOR DISABLE;
GO


----------------------------------------------------------------------------------------------
-- Monitorar o uso do RG
----------------------------------------------------------------------------------------------

--monitorar o uso de CPU do resource pool de forma resumida utilizando a consulta abaixo:
SELECT
    A.[name] AS resource_pool,
    COALESCE(SUM(B.total_request_count), 0) AS total_request_count,
    COALESCE(SUM(B.total_cpu_usage_ms), 0) AS total_cpu_usage_ms,
    (CASE WHEN SUM(B.total_request_count) > 0 THEN SUM(B.total_cpu_usage_ms) / SUM(B.total_request_count) ELSE 0 END) AS avg_cpu_usage_ms
FROM
    sys.dm_resource_governor_resource_pools AS A
    LEFT OUTER JOIN sys.dm_resource_governor_workload_groups AS B ON A.pool_id = B.pool_id
GROUP BY
    A.[name]
	
--monitorar todos os parâmetros de CPU dos pools e workload groups:
SELECT
    A.[name] AS resource_pool,
    B.[name] AS workload_group,
    A.total_cpu_usage_ms,
    A.min_cpu_percent,
    A.max_cpu_percent,
    A.cap_cpu_percent,
    A.total_cpu_delayed_ms,
    A.total_cpu_active_ms,
    A.total_cpu_violation_delay_ms,
    A.total_cpu_violation_sec,
    A.total_cpu_usage_preemptive_ms,
    B.total_cpu_limit_violation_count,
    B.total_cpu_usage_ms,
    B.max_request_cpu_time_ms,
    B.request_max_cpu_time_sec,
    B.total_cpu_usage_preemptive_ms
FROM
    sys.dm_resource_governor_resource_pools AS A
    LEFT OUTER JOIN sys.dm_resource_governor_workload_groups AS B ON A.pool_id = B.pool_id

--monitorar o uso de I/O dos resource pools utilizando a query abaixo:
SELECT
    pool_id,
    [name],
    min_iops_per_volume,
    max_iops_per_volume,
    read_io_queued_total,
    read_io_issued_total,
    read_io_completed_total,
    read_io_throttled_total,
    read_bytes_total,
    read_io_stall_total_ms,
    read_io_stall_queued_ms,
    io_issue_violations_total,
    io_issue_delay_total_ms
FROM
    sys.dm_resource_governor_resource_pools
	
--utilizar a query abaixo para verificar qual o workload group utilizado pelas sessões ativas em execução no momento:
SELECT
    B.[name],
    A.*
FROM 
    sys.dm_exec_sessions AS A WITH (NOLOCK)
    LEFT JOIN sys.dm_resource_governor_workload_groups B ON A.group_id = B.group_id
WHERE 
    A.session_id > 50
    AND A.session_id <> @@SPID
    AND (A.[status] != 'sleeping' OR (A.[status] = 'sleeping' AND A.open_transaction_count > 0))
	
--Identifica sessoes que estao utilizando os grupos criados
SELECT    session_id as 'Session ID',
              [host_name] as 'Host Name',
              [program_name] as 'Program Name',
              nt_user_name as 'User Name',
              SDRGWG.[Name] as 'Group Assigned',
              DRGRP.[name] as 'Pool Assigned',
			  CONCAT('KILL ',session_id) as CMD_KILL
FROM sys.dm_exec_sessions SDES
        INNER JOIN sys.dm_resource_governor_workload_groups SDRGWG
                ON SDES.group_id = SDRGWG.group_id
        INNER JOIN sys.dm_resource_governor_resource_pools DRGRP
                ON SDRGWG.pool_id = DRGRP.pool_id
WHERE SDRGWG.[Name] not in ('internal','default')