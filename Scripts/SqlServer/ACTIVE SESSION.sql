
            EXEC sp_whoisactive
                @filter = '',
                @filter_type = 'session',
                @not_filter = '',
                @not_filter_type = 'session',
                @show_own_spid = 0,
                @show_system_spids = 0,
                @show_sleeping_spids = 1,
                @get_full_inner_text = 0,
                @get_plans = 0,
                @get_outer_command = 0,
                @get_transaction_info = 0,
                @get_task_info = 2,
                @get_locks = 0,
                @get_avg_time = 0,
                @get_additional_info = 0,
                @find_block_leaders = 1,
                @delta_interval = 1,
                @output_column_list = '[dd%][block%][percent_complete][session_id][sql_text][sql_command][login_name][wait_info][tasks][tran_log%][cpu%][temp%][block%][reads%][writes%][context%][physical%][query_plan][locks][%]',
                @sort_order = '[blocked_session_count] desc',
                @format_output = 1,
                @destination_table = '',
                @return_schema = 0,
                @schema = NULL,
                @help = 0

            SELECT
                F.session_id,
                A.job_id,
                C.name AS job_name,
                F.login_name,
                F.[host_name],
                F.[program_name],
                A.start_execution_date,
                CONVERT(VARCHAR, CONVERT(VARCHAR, DATEADD(ms, ( DATEDIFF(SECOND, A.start_execution_date, GETDATE()) % 86400 ) * 1000, 0), 114)) AS time_elapsed,
                ISNULL(A.last_executed_step_id, 0) + 1 AS current_executed_step_id,
                D.step_name,
                H.[text]
            FROM
                msdb.dbo.sysjobactivity                     A   WITH(NOLOCK)
                LEFT JOIN msdb.dbo.sysjobhistory            B   WITH(NOLOCK)    ON A.job_history_id = B.instance_id
                JOIN msdb.dbo.sysjobs                       C   WITH(NOLOCK)    ON A.job_id = C.job_id
                JOIN msdb.dbo.sysjobsteps                   D   WITH(NOLOCK)    ON A.job_id = D.job_id AND ISNULL(A.last_executed_step_id, 0) + 1 = D.step_id
                JOIN (
                    SELECT CAST(CONVERT( BINARY(16), SUBSTRING([program_name], 30, 34), 1) AS UNIQUEIDENTIFIER) AS job_id, MAX(login_time) login_time
                    FROM sys.dm_exec_sessions WITH(NOLOCK)
                    WHERE [program_name] LIKE 'SQLAgent - TSQL JobStep (Job % : Step %)'
                    GROUP BY CAST(CONVERT( BINARY(16), SUBSTRING([program_name], 30, 34), 1) AS UNIQUEIDENTIFIER)
                )                                           E                   ON C.job_id = E.job_id
                LEFT JOIN sys.dm_exec_sessions              F   WITH(NOLOCK)    ON E.job_id = (CASE WHEN BINARY_CHECKSUM(SUBSTRING(F.[program_name], 30, 34)) > 0 THEN CAST(TRY_CONVERT( BINARY(16), SUBSTRING(F.[program_name], 30, 34), 1) AS UNIQUEIDENTIFIER) ELSE NULL END) AND E.login_time = F.login_time
                LEFT JOIN sys.dm_exec_connections           G   WITH(NOLOCK)    ON F.session_id = G.session_id
                OUTER APPLY sys.dm_exec_sql_text(most_recent_sql_handle) H
            WHERE
                A.session_id = ( SELECT TOP 1 session_id FROM msdb.dbo.syssessions	WITH(NOLOCK) ORDER BY agent_start_date DESC ) 
                AND A.start_execution_date IS NOT NULL 
                AND A.stop_execution_date IS NULL

                /*
            DECLARE @Username NVARCHAR(255) = 'linx_oms'; -- Substitua pelo nome do usuário desejado

            DECLARE @SessionId INT;
            DECLARE @KillStatement NVARCHAR(1000);

            DECLARE SessionCursor CURSOR FOR
            SELECT session_id
            FROM sys.dm_exec_sessions
            WHERE login_name = @Username;

            OPEN SessionCursor;

            FETCH NEXT FROM SessionCursor INTO @SessionId;

            WHILE @@FETCH_STATUS = 0
            BEGIN
                SET @KillStatement = 'KILL ' + CAST(@SessionId AS NVARCHAR(10));
                EXEC(@KillStatement);
                FETCH NEXT FROM SessionCursor INTO @SessionId;
            END;

            CLOSE SessionCursor;
            DEALLOCATE SessionCursor;
            */




            /*

            USE PS_BARCELOS_BMG;
            UPDATE STATISTICS PARCELAMENTO;
            UPDATE STATISTICS ITEMMOTIVOLANCAMENTO;
            UPDATE STATISTICS PRODUTO;
            UPDATE STATISTICS MOTIVOLANCAMENTO;
            UPDATE STATISTICS DIVIDA;
            UPDATE STATISTICS NEGOCIACAO;
            UPDATE STATISTICS RECEBIMENTO;
            UPDATE STATISTICS LOJA_PEDIDO;
            UPDATE STATISTICS PRODUTOS_BARRA;
            */
            /*
            EXEC sp_whoisactive
			--@filter_type = 'session',
                --@filter_type = 'program',
                @filter_type = 'database',
                --@filter_type = 'login',
                --@filter_type = 'host', 
                @filter = 'ReportServer_BI'
            */

    GO


        WITH
            AG_Stats AS
                    (
                    SELECT AR.replica_server_name,
                           HARS.role_desc,
                           Db_name(DRS.database_id) [DBName],
                           DRS.last_commit_time
                    FROM   sys.dm_hadr_database_replica_states DRS
                    INNER JOIN sys.availability_replicas AR ON DRS.replica_id = AR.replica_id
                    INNER JOIN sys.dm_hadr_availability_replica_states HARS ON AR.group_id = HARS.group_id
                        AND AR.replica_id = HARS.replica_id
                    ),
            Pri_CommitTime AS
                    (
                    SELECT    replica_server_name
                            , DBName
                            , last_commit_time
                    FROM    AG_Stats
                    WHERE    role_desc = 'PRIMARY'
                    ),
            Sec_CommitTime AS
            (
                    SELECT    replica_server_name
                            , DBName
                            , last_commit_time
                    FROM    AG_Stats
                    WHERE    role_desc = 'SECONDARY'
                    )
        SELECT p.replica_server_name [primary_replica]
            , p.[DBName] AS [DatabaseName]
            , s.replica_server_name [secondary_replica]
            , DATEDIFF(ss,s.last_commit_time,p.last_commit_time) AS [Sync_Lag_Secs]
        FROM Pri_CommitTime p
        LEFT JOIN Sec_CommitTime s ON [s].[DBName] = [p].[DBName]


    GO
    SELECT
        R.session_id,
        R.command AS Ds_Operacao,
        B.name AS Nm_Banco,
        R.start_time AS Dt_Inicio,
        CONVERT(VARCHAR(20), DATEADD(MS, R.estimated_completion_time, GETDATE()), 20) AS Dt_Previsao_Fim,
        CONVERT(NUMERIC(6, 2), R.percent_complete) AS Vl_Percentual_Concluido,
        CONVERT(NUMERIC(6, 2), R.total_elapsed_time / 1000.0 / 60.0) AS Qt_Minutos_Execucao,
        CONVERT(NUMERIC(6, 2), R.estimated_completion_time / 1000.0 / 60.0) AS Qt_Minutos_Restantes,
        CONVERT(NUMERIC(6, 2), R.estimated_completion_time / 1000.0 / 60.0 / 60.0) AS Qt_Horas_Restantes,
        CONVERT(VARCHAR(MAX), ( SELECT
                                    SUBSTRING(text, R.statement_start_offset / 2, CASE WHEN R.statement_end_offset = -1 THEN 1000 ELSE ( R.statement_end_offset - R.statement_start_offset ) / 2 END)
                                FROM
                                    sys.dm_exec_sql_text(sql_handle)
                                )) AS Ds_Comando
    FROM
        sys.dm_exec_requests	R	WITH(NOLOCK)
        JOIN sys.databases		B	WITH(NOLOCK)	 ON R.database_id = B.database_id
    WHERE
        R.command IN ( 
            'BACKUP DATABASE', 
            'RESTORE DATABASE', 
            'ALTER INDEX REORGANIZE', 
            'AUTO_SHRINK option with ALTER DATABASE', 
            'CREATE INDEX',
            'DBCC CHECKDB',
            'DBCC CHECKFILEGROUP',
            'DBCC CHECKTABLE',
            'DBCC INDEXDEFRAG',
            'DBCC SHRINKDATABASE',
            'DBCC SHRINKFILE',
            'KILL',
            'UPDATE STATISTICS',
            'DBCC'
        )
        AND R.estimated_completion_time > 0 