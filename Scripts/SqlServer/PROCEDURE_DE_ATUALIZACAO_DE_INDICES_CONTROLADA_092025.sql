/* ========= DB de monitoramento ========= */
USE startupmonitor;
GO

USE startupmonitor;
SET NOCOUNT ON;

/* 1) LOG */
IF OBJECT_ID('dbo.index_maint_log','U') IS NULL
BEGIN
  CREATE TABLE dbo.index_maint_log
  (
    id               bigint IDENTITY(1,1) PRIMARY KEY,
    dt               datetime2(0) NOT NULL DEFAULT SYSDATETIME(),
    db_name          sysname       NULL,
    status           nvarchar(20)  NULL,
    acao             nvarchar(50)  NULL,
    comando          nvarchar(MAX) NULL,
    erro             nvarchar(MAX) NULL,
    dt_inicio        datetime2(0)  NULL,
    dt_fim           datetime2(0)  NULL,
    schema_name      sysname       NULL,
    table_name       sysname       NULL,
    index_name       sysname       NULL,
    partition_number int           NULL,
    page_count       bigint        NULL,
    frag_before      float         NULL,
    frag_after       float         NULL,
    mod_pct          float         NULL,
    cancelado        bit           NULL
  );
END
ELSE
BEGIN
  IF COL_LENGTH('dbo.index_maint_log','db_name') IS NULL
    ALTER TABLE dbo.index_maint_log ADD db_name sysname NULL;
  ALTER TABLE dbo.index_maint_log ALTER COLUMN status      nvarchar(20)  NULL;
  ALTER TABLE dbo.index_maint_log ALTER COLUMN acao        nvarchar(50)  NULL;
  ALTER TABLE dbo.index_maint_log ALTER COLUMN schema_name nvarchar(128) NULL;
  ALTER TABLE dbo.index_maint_log ALTER COLUMN table_name  nvarchar(128) NULL;
  ALTER TABLE dbo.index_maint_log ALTER COLUMN index_name  nvarchar(128) NULL;
  ALTER TABLE dbo.index_maint_log ALTER COLUMN comando     nvarchar(MAX) NULL;
  ALTER TABLE dbo.index_maint_log ALTER COLUMN erro        nvarchar(MAX) NULL;
END;

/* 2) ALVOS (com db_name na PK) */
IF OBJECT_ID('dbo.IndexMaint_Alvo','U') IS NULL
BEGIN
  CREATE TABLE dbo.IndexMaint_Alvo
  (
    db_name     sysname NOT NULL,
    schema_name sysname NOT NULL,
    table_name  sysname NOT NULL,
    CONSTRAINT PK_IndexMaint_Alvo PRIMARY KEY (db_name, schema_name, table_name)
  );
END
ELSE
BEGIN
  IF COL_LENGTH('dbo.IndexMaint_Alvo','db_name') IS NULL
  BEGIN
    ALTER TABLE dbo.IndexMaint_Alvo ADD db_name sysname NULL;
    -- AJUSTE O DEFAULT ABAIXO, SE NECESSÁRIO
    UPDATE dbo.IndexMaint_Alvo SET db_name = N'UAU_DIRECIONAL' WHERE db_name IS NULL;

    DECLARE @pk sysname, @sql nvarchar(max);
    SELECT @pk = kc.name
    FROM sys.key_constraints kc
    WHERE kc.parent_object_id = OBJECT_ID(N'startupmonitor.dbo.IndexMaint_Alvo')
      AND kc.[type]='PK';
    IF @pk IS NOT NULL
    BEGIN
      SET @sql = N'ALTER TABLE startupmonitor.dbo.IndexMaint_Alvo DROP CONSTRAINT '+QUOTENAME(@pk)+';';
      EXEC (@sql);
    END

    ALTER TABLE dbo.IndexMaint_Alvo ALTER COLUMN db_name sysname NOT NULL;
    ALTER TABLE dbo.IndexMaint_Alvo
      ADD CONSTRAINT PK_IndexMaint_Alvo PRIMARY KEY (db_name, schema_name, table_name);
  END
END;

/* 3) CONFIG (perfís) */
IF OBJECT_ID('dbo.IndexMaint_Config','U') IS NULL
BEGIN
  CREATE TABLE dbo.IndexMaint_Config
  (
    profile_name         sysname      NOT NULL PRIMARY KEY,
    [Mode]               nvarchar(10) NOT NULL,   -- ALTER|STATS|HYBRID|LIST|REPORT
    [StatsMode]          nvarchar(10) NOT NULL,   -- SAMPLE|FULLSCAN
    [SamplePercent]      int          NULL,
    [WindowMinutes]      int          NOT NULL,
    [FragMin]            float        NOT NULL,
    [FragRebuild]        float        NOT NULL,
    [LargePages]         bigint       NOT NULL,
    [HotModPct]          float        NOT NULL,
    [MaxDOP]             int          NULL,
    [FillFactor]         int          NULL,
    [OnlineDesejado]     bit          NOT NULL,
    [UseWaitLowPriority] bit          NOT NULL,
    [UseResumable]       bit          NOT NULL,
    [OpMaxMinutes]       int          NULL,
    [AGMaxSendQueueMB]   int          NOT NULL,
    [AGMaxRedoQueueMB]   int          NOT NULL,
    [ResumableHandling]  nvarchar(10) NULL       -- ABORT|RESUME|IGNORE
  );
END
ELSE
BEGIN
  IF COL_LENGTH('dbo.IndexMaint_Config','ResumableHandling') IS NULL
    ALTER TABLE dbo.IndexMaint_Config ADD [ResumableHandling] nvarchar(10) NULL;
END;

/* 4) QUEUE (progresso/ETA) */
IF OBJECT_ID('dbo.IndexMaint_Queue','U') IS NULL
BEGIN
  CREATE TABLE dbo.IndexMaint_Queue
  (
    run_id           uniqueidentifier NOT NULL,
    db_name          sysname          NOT NULL,
    created_at       datetime2(0)     NOT NULL DEFAULT SYSDATETIME(),
    item_id          int              NOT NULL IDENTITY(1,1),
    schema_name      sysname          NOT NULL,
    table_name       sysname          NOT NULL,
    index_name       sysname          NOT NULL,
    partition_number int              NULL,
    action           nvarchar(12)     NOT NULL,   -- REBUILD|REORGANIZE|STATS
    page_count       bigint           NULL,
    frag_before      float            NULL,
    frag_after       float            NULL,
    mod_pct          float            NULL,
    state            nvarchar(12)     NOT NULL,   -- PENDING|RUNNING|DONE|ERRO|CANCELADO
    tini             datetime2(0)     NULL,
    tfim             datetime2(0)     NULL,
    erro             nvarchar(MAX)    NULL,
    cmd1             nvarchar(MAX)    NULL,
    cmd2             nvarchar(MAX)    NULL,
    CONSTRAINT PK_IndexMaint_Queue PRIMARY KEY (run_id, item_id)
  );
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_IndexMaint_Queue_State' AND object_id = OBJECT_ID('dbo.IndexMaint_Queue'))
  CREATE INDEX IX_IndexMaint_Queue_State ON dbo.IndexMaint_Queue(run_id, state);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_IndexMaint_Queue_Key' AND object_id = OBJECT_ID('dbo.IndexMaint_Queue'))
  CREATE INDEX IX_IndexMaint_Queue_Key ON dbo.IndexMaint_Queue(run_id, db_name, schema_name, table_name, index_name, partition_number);

PRINT 'DDL OK';



2) Inserts de exemplo (perfil + alvos)
USE startupmonitor;
SET NOCOUNT ON;

DECLARE @TargetDB sysname = N'UAU_DIRECIONAL';

------------------------------------------------------------
-- 2.1) Alvos (tabelas do banco @TargetDB)
--  -> repita/adapte conforme seu cenário
------------------------------------------------------------
INSERT INTO dbo.IndexMaint_Alvo(db_name,schema_name,table_name)
SELECT v.db_name, v.schema_name, v.table_name
FROM (VALUES
 (@TargetDB,N'dbo',N'Parc_Proc'),
 (@TargetDB,N'dbo',N'Dados_Proc'),
 (@TargetDB,N'dbo',N'ContasReceber'),
 (@TargetDB,N'dbo',N'ContasReceberHist'),
 (@TargetDB,N'dbo',N'Recebidas'),
 (@TargetDB,N'dbo',N'RecebePgto'),
 (@TargetDB,N'dbo',N'Vendas'),
 (@TargetDB,N'dbo',N'Pessoas'),
 (@TargetDB,N'dbo',N'ResumoFiscal')
) AS v(db_name,schema_name,table_name)
WHERE NOT EXISTS (
  SELECT 1 FROM dbo.IndexMaint_Alvo a
  WHERE a.db_name=v.db_name AND a.schema_name=v.schema_name AND a.table_name=v.table_name
);

------------------------------------------------------------
-- 2.2) Perfis de execução (IndexMaint_Config)
------------------------------------------------------------

-- Perfil diário (HYBRID + SAMPLE 20%)
IF NOT EXISTS (SELECT 1 FROM dbo.IndexMaint_Config WHERE profile_name=N'DIARIO')
INSERT dbo.IndexMaint_Config
(profile_name,[Mode],[StatsMode],[SamplePercent],[WindowMinutes],
 [FragMin],[FragRebuild],[LargePages],[HotModPct],
 [MaxDOP],[FillFactor],[OnlineDesejado],[UseWaitLowPriority],[UseResumable],
 [OpMaxMinutes],[AGMaxSendQueueMB],[AGMaxRedoQueueMB],[ResumableHandling])
VALUES
(N'DIARIO',N'HYBRID',N'SAMPLE',20,120,
 10,30,500000,10,
 2,NULL,1,1,1,
 20,512,512,N'ABORT');

-- Perfil semanal (STATS FULLSCAN)
IF NOT EXISTS (SELECT 1 FROM dbo.IndexMaint_Config WHERE profile_name=N'SEMANAL_FULLSCAN')
INSERT dbo.IndexMaint_Config
(profile_name,[Mode],[StatsMode],[SamplePercent],[WindowMinutes],
 [FragMin],[FragRebuild],[LargePages],[HotModPct],
 [MaxDOP],[FillFactor],[OnlineDesejado],[UseWaitLowPriority],[UseResumable],
 [OpMaxMinutes],[AGMaxSendQueueMB],[AGMaxRedoQueueMB],[ResumableHandling])
VALUES
(N'SEMANAL_FULLSCAN',N'STATS',N'FULLSCAN',NULL,90,
 10,30,500000,10,
 2,NULL,1,1,1,
 20,512,512,N'ABORT');

PRINT 'Inserts OK';



3) Procedure (com Abort → Coletas → Execução + REPORT)
/* File: startupmonitor.dbo.IndexMaint_Run.sql */
USE startupmonitor;
GO
CREATE OR ALTER PROC dbo.IndexMaint_Run
  @TargetDB           sysname      = N'UAU_DIRECIONAL',
  @Profile            sysname      = NULL,
  @Mode               nvarchar(10) = N'HYBRID',     -- ALTER|STATS|HYBRID|REPORT
  @Report             nvarchar(12) = N'ALL',        -- FRAG|RESUMABLE|LASTRUN|ALL
  @ReportScope        nvarchar(10) = N'ALVO',       -- ALVO|TODAS (p/ REPORT FRAG)
  @StatsMode          nvarchar(10) = N'SAMPLE',     -- SAMPLE|FULLSCAN
  @SamplePercent      int          = 20,
  @WindowMinutes      int          = 120,
  @FragMin            float        = 10.0,
  @FragRebuild        float        = 30.0,
  @LargePages         bigint       = 500000,
  @HotModPct          float        = 10.0,
  @MaxDOP             int          = 2,
  @FillFactor         int          = NULL,
  @OnlineDesejado     bit          = 1,
  @UseWaitLowPriority bit          = 1,            -- 2014+
  @UseResumable       bit          = 1,            -- 2017+
  @OpMaxMinutes       int          = 20,
  @AGMaxSendQueueMB   int          = 512,
  @AGMaxRedoQueueMB   int          = 512,
  @ResumableHandling  nvarchar(10) = N'ABORT',     -- ABORT|RESUME|IGNORE
  @FragScanMode       nvarchar(10) = N'LIMITED'    -- LIMITED|SAMPLED|DETAILED
AS
BEGIN
  SET NOCOUNT ON;

  DECLARE @tStart   datetime2(0) = SYSDATETIME();
  DECLARE @deadline datetime     = DATEADD(minute,@WindowMinutes,GETDATE());
  DECLARE @msg nvarchar(max), @sql nvarchar(max);

  /* Carregar perfil (se houver) */
  IF @Profile IS NOT NULL
  BEGIN
    IF COL_LENGTH('startupmonitor.dbo.IndexMaint_Config','ResumableHandling') IS NOT NULL
    BEGIN
      SELECT
        @Mode               = [Mode],
        @StatsMode          = [StatsMode],
        @SamplePercent      = ISNULL([SamplePercent],@SamplePercent),
        @WindowMinutes      = [WindowMinutes],
        @FragMin            = [FragMin],
        @FragRebuild        = [FragRebuild],
        @LargePages         = [LargePages],
        @HotModPct          = [HotModPct],
        @MaxDOP             = [MaxDOP],
        @FillFactor         = [FillFactor],
        @OnlineDesejado     = [OnlineDesejado],
        @UseWaitLowPriority = [UseWaitLowPriority],
        @UseResumable       = [UseResumable],
        @OpMaxMinutes       = ISNULL([OpMaxMinutes],@OpMaxMinutes),
        @AGMaxSendQueueMB   = [AGMaxSendQueueMB],
        @AGMaxRedoQueueMB   = [AGMaxRedoQueueMB],
        @ResumableHandling  = ISNULL([ResumableHandling],@ResumableHandling),
        @FragScanMode       = ISNULL([FragScanMode], @FragScanMode)
      FROM startupmonitor.dbo.IndexMaint_Config
      WHERE [profile_name]=@Profile;
    END
    ELSE
    BEGIN
      SELECT
        @Mode               = [Mode],
        @StatsMode          = [StatsMode],
        @SamplePercent      = ISNULL([SamplePercent],@SamplePercent),
        @WindowMinutes      = [WindowMinutes],
        @FragMin            = [FragMin],
        @FragRebuild        = [FragRebuild],
        @LargePages         = [LargePages],
        @HotModPct          = [HotModPct],
        @MaxDOP             = [MaxDOP],
        @FillFactor         = [FillFactor],
        @OnlineDesejado     = [OnlineDesejado],
        @UseWaitLowPriority = [UseWaitLowPriority],
        @UseResumable       = [UseResumable],
        @OpMaxMinutes       = ISNULL([OpMaxMinutes],@OpMaxMinutes),
        @AGMaxSendQueueMB   = [AGMaxSendQueueMB],
        @AGMaxRedoQueueMB   = [AGMaxRedoQueueMB]
      FROM startupmonitor.dbo.IndexMaint_Config
      WHERE [profile_name]=@Profile;
    END
    IF @@ROWCOUNT=0
    BEGIN
      INSERT dbo.index_maint_log(db_name,status,erro)
      VALUES(@TargetDB,N'ERRO',N'Profile não encontrado: '+ISNULL(@Profile,N'(null)'));
      RETURN;
    END
  END

  /* Alvo e versão */
  DECLARE @dbid smallint = DB_ID(@TargetDB);
  IF @dbid IS NULL
  BEGIN
    INSERT dbo.index_maint_log(db_name,status,erro)
    VALUES(@TargetDB,N'ERRO',N'Banco alvo não encontrado');
    RETURN;
  END

  DECLARE @Edition        nvarchar(128) = CAST(SERVERPROPERTY('Edition') AS nvarchar(128));
  DECLARE @ProductVersion nvarchar(128) = CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128));
  DECLARE @VerMajor       int           = CAST(LEFT(@ProductVersion, CHARINDEX('.', @ProductVersion + '.') - 1) AS int);
  DECLARE @Enterprise bit   = CASE WHEN @Edition LIKE '%Enterprise%' OR @Edition LIKE '%Developer%' THEN 1 ELSE 0 END;
  DECLARE @HasWaitLP bit    = CASE WHEN @VerMajor >= 12 THEN 1 ELSE 0 END;  -- 2014+
  DECLARE @HasResumable bit = CASE WHEN @VerMajor >= 14 THEN 1 ELSE 0 END;  -- 2017+
  DECLARE @db sysname = QUOTENAME(@TargetDB);

  /* LOG início + RunId */
  SET @msg = N'INICIO: DB='+@db+N', Mode='+@Mode+N', StatsMode='+@StatsMode+
             N', WindowMin='+CAST(@WindowMinutes AS nvarchar(10))+N', Profile='+ISNULL(@Profile,N'(NULL)')+
             N', FragScanMode='+@FragScanMode;
  INSERT dbo.index_maint_log(db_name,status,acao,erro) VALUES(@TargetDB,N'INFO',N'STAGE_BEGIN',@msg);

  DECLARE @RunId uniqueidentifier = NEWID();
  INSERT dbo.index_maint_log(db_name,status,acao,erro)
  VALUES(@TargetDB,N'INFO',N'RUN_ID',CONVERT(nvarchar(36),@RunId));

  /* =================== REPORT =================== */
  IF UPPER(@Mode)=N'REPORT'
  BEGIN
    DECLARE @Rpt nvarchar(12) = UPPER(@Report);

    -- FRAG
    IF @Rpt IN (N'FRAG',N'ALL')
    BEGIN
      DECLARE @filter nvarchar(max) = N'';
      IF UPPER(@ReportScope)=N'ALVO'
        SET @filter = N'
          AND EXISTS (
            SELECT 1
            FROM startupmonitor.dbo.IndexMaint_Alvo a
            WHERE a.db_name = N'''+REPLACE(@TargetDB,'''','''''')+N'''
              AND a.schema_name=s.name AND a.table_name=o.name
          )';

      DECLARE @extraSel nvarchar(max) = N'NULL AS insert_stmt';
      IF UPPER(@ReportScope)=N'TODAS'
        SET @extraSel = N'''INSERT startupmonitor.dbo.IndexMaint_Alvo(db_name,schema_name,table_name) VALUES (N''''' +
                        REPLACE(@TargetDB,'''','''''') + N''''',N''''''+s.name+N'''''',N''''''+o.name+N'''''' );'' AS insert_stmt';

      SET @sql = N'
        SELECT s.name AS schema_name, o.name AS table_name, i.name AS index_name,
               CASE i.type WHEN 1 THEN N''CLUSTERED'' WHEN 2 THEN N''NONCLUSTERED'' ELSE CONVERT(nvarchar(10),i.type) END AS index_type_desc,
               ps.partition_number, ps.page_count, ps.avg_fragmentation_in_percent AS frag,
               '+@extraSel+N'
        FROM '+@db+N'.sys.objects o
        JOIN '+@db+N'.sys.schemas s ON s.schema_id=o.schema_id
        JOIN '+@db+N'.sys.indexes i
             ON i.object_id=o.object_id
            AND i.index_id>0
            AND i.type IN (1,2)          -- somente B-Tree
            AND i.name IS NOT NULL
            AND i.is_hypothetical = 0
            AND i.is_disabled     = 0
        CROSS APPLY sys.dm_db_index_physical_stats(DB_ID(N'''+REPLACE(@TargetDB,'''','''''')+N'''),
                                                   o.object_id, i.index_id, NULL, @ScanMode) ps
        WHERE o.type=''U''
          AND ps.page_count>25
          AND ps.avg_fragmentation_in_percent >= @FragMin
        '+@filter+N'
        ORDER BY ps.avg_fragmentation_in_percent DESC, ps.page_count DESC;';
      EXEC sp_executesql @sql, N'@FragMin float, @ScanMode nvarchar(10)', @FragMin=@FragMin, @ScanMode=@FragScanMode;
    END

    -- RESUMABLE
    IF @Rpt IN (N'RESUMABLE',N'ALL')
    BEGIN
      SET @sql = N'
        SELECT
          OBJECT_SCHEMA_NAME(ro.object_id, DB_ID(N'''+REPLACE(@TargetDB,'''','''''')+N''')) AS schema_name,
          OBJECT_NAME      (ro.object_id, DB_ID(N'''+REPLACE(@TargetDB,'''','''''')+N''')) AS table_name,
          i.name AS index_name,
          ro.state_desc, ro.percent_complete, ro.start_time, ro.last_pause_time
        FROM '+@db+N'.sys.index_resumable_operations ro
        JOIN '+@db+N'.sys.indexes i
          ON i.object_id=ro.object_id AND i.index_id=ro.index_id;';
      EXEC sp_executesql @sql;
    END

    -- LASTRUN
    IF @Rpt IN (N'LASTRUN',N'ALL')
    BEGIN
      DECLARE @start_dt datetime2(0), @end_dt datetime2(0);
      SELECT TOP (1) @start_dt = dt
        FROM dbo.index_maint_log
       WHERE db_name=@TargetDB AND status=N'INFO' AND acao=N'STAGE_BEGIN'
       ORDER BY dt DESC;

      SELECT TOP (1) @end_dt = dt
        FROM dbo.index_maint_log
       WHERE db_name=@TargetDB AND status=N'INFO' AND acao=N'STAGE_END'
         AND dt >= ISNULL(@start_dt,'19000101')
       ORDER BY dt DESC;

      SELECT @start_dt AS last_start, @end_dt AS last_end,
             CASE WHEN @start_dt IS NOT NULL AND @end_dt IS NOT NULL
                  THEN DATEDIFF(SECOND, @start_dt, @end_dt) END AS duration_seconds;
    END

    INSERT dbo.index_maint_log(db_name,status,acao,erro)
    VALUES (@TargetDB,N'INFO',N'STAGE_REPORT_END',N'REPORT finalizado');
    RETURN;
  END
  /* =============== FIM REPORT =============== */

  /* ===== FASE 1: RESUMABLES (ABORT/RESUME) ===== */
  IF @HasResumable = 1 AND UPPER(@ResumableHandling) <> N'IGNORE'
  BEGIN
    INSERT dbo.index_maint_log(db_name,status,acao,erro) VALUES(@TargetDB,N'INFO',N'STAGE_ABORT_START',N'Varredura resumables');

    IF OBJECT_ID('tempdb..#resumable_ops') IS NOT NULL DROP TABLE #resumable_ops;
    CREATE TABLE #resumable_ops(schema_name sysname, table_name sysname, index_name sysname);

    SET @sql = N'
      INSERT #resumable_ops(schema_name,table_name,index_name)
      SELECT OBJECT_SCHEMA_NAME(ro.object_id, DB_ID(N'''+REPLACE(@TargetDB,'''','''''')+N''')),
             OBJECT_NAME      (ro.object_id, DB_ID(N'''+REPLACE(@TargetDB,'''','''''')+N''')),
             i.name
      FROM '+@db+N'.sys.index_resumable_operations ro
      JOIN '+@db+N'.sys.indexes i
        ON i.object_id=ro.object_id AND i.index_id=ro.index_id;';
    EXEC sp_executesql @sql;

    DECLARE @sch_r sysname, @tab_r sysname, @idx_r sysname;
    DECLARE cur_r CURSOR LOCAL FAST_FORWARD FOR
      SELECT schema_name, table_name, index_name FROM #resumable_ops;
    OPEN cur_r;
    FETCH NEXT FROM cur_r INTO @sch_r,@tab_r,@idx_r;
    WHILE @@FETCH_STATUS = 0
    BEGIN
      IF UPPER(@ResumableHandling)=N'ABORT'
        SET @sql = N'ALTER INDEX '+QUOTENAME(@idx_r)+N' ON '+@db+N'.'+QUOTENAME(@sch_r)+N'.'+QUOTENAME(@tab_r)+N' ABORT;';
      ELSE
        SET @sql = N'ALTER INDEX '+QUOTENAME(@idx_r)+N' ON '+@db+N'.'+QUOTENAME(@sch_r)+N'.'+QUOTENAME(@tab_r)+
                   N' RESUME WITH (MAX_DURATION = '+CAST(@OpMaxMinutes AS nvarchar(10))+N' MINUTES);';

      BEGIN TRY
        EXEC (@sql);
        INSERT dbo.index_maint_log(db_name,status,acao,comando,erro)
          VALUES(@TargetDB,N'INFO',CASE WHEN UPPER(@ResumableHandling)=N'ABORT' THEN N'ABORT' ELSE N'RESUME' END,@sql,N'RESUMABLE tratado');
      END TRY
      BEGIN CATCH
        INSERT dbo.index_maint_log(db_name,status,acao,comando,erro)
          VALUES(@TargetDB,N'ERRO',CASE WHEN UPPER(@ResumableHandling)=N'ABORT' THEN N'ABORT' ELSE N'RESUME' END,@sql,ERROR_MESSAGE());
      END CATCH;

      FETCH NEXT FROM cur_r INTO @sch_r,@tab_r,@idx_r;
    END
    CLOSE cur_r; DEALLOCATE cur_r;

    INSERT dbo.index_maint_log(db_name,status,acao,erro) VALUES(@TargetDB,N'INFO',N'STAGE_ABORT_END',N'Concluído');
  END

  /* ===== Metadados do alvo ===== */
  IF OBJECT_ID('tempdb..#db_objects') IS NOT NULL DROP TABLE #db_objects;
  CREATE TABLE #db_objects(object_id int PRIMARY KEY, schema_name sysname, table_name sysname);

  IF OBJECT_ID('tempdb..#db_indexes') IS NOT NULL DROP TABLE #db_indexes;
  CREATE TABLE #db_indexes(
    object_id     int,
    index_id      int,
    name          nvarchar(128) NULL,
    type          int,
    is_hypothetical bit,
    is_disabled   bit,
    data_space_id int
  );

  IF OBJECT_ID('tempdb..#db_ps') IS NOT NULL DROP TABLE #db_ps;
  CREATE TABLE #db_ps(data_space_id int PRIMARY KEY);

  SET @sql = N'
    INSERT #db_objects(object_id,schema_name,table_name)
    SELECT o.object_id, s.name, o.name
    FROM '+@db+N'.sys.objects o
    JOIN '+@db+N'.sys.schemas s ON s.schema_id=o.schema_id
    WHERE o.type=''U'';

    INSERT #db_indexes(object_id,index_id,name,type,is_hypothetical,is_disabled,data_space_id)
    SELECT object_id,index_id,name,type,is_hypothetical,is_disabled,data_space_id
    FROM '+@db+N'.sys.indexes
    WHERE index_id > 0 AND type IN (1,2) AND name IS NOT NULL
      AND is_hypothetical = 0 AND is_disabled = 0;

    INSERT #db_ps(data_space_id)
    SELECT data_space_id FROM '+@db+N'.sys.partition_schemes;';
  EXEC sp_executesql @sql;

  /* ===== FASE 2: COLETAS ===== */
  INSERT dbo.index_maint_log(db_name,status,acao,erro) VALUES(@TargetDB,N'INFO',N'STAGE_COLLECT_START',N'Coletas');

  IF OBJECT_ID('tempdb..#alvo') IS NOT NULL DROP TABLE #alvo;
  CREATE TABLE #alvo(object_id int PRIMARY KEY, schema_name sysname, table_name sysname);

  INSERT #alvo(object_id,schema_name,table_name)
  SELECT o.object_id, o.schema_name, o.table_name
  FROM startupmonitor.dbo.IndexMaint_Alvo a
  JOIN #db_objects o
    ON o.schema_name=a.schema_name AND o.table_name=a.table_name
  WHERE a.db_name = @TargetDB;

  IF NOT EXISTS(SELECT 1 FROM #alvo)
  BEGIN
    INSERT dbo.index_maint_log(db_name,status,acao,erro)
    VALUES(@TargetDB,N'IGNORADO',N'STAGE_COLLECT_END',N'Whitelist vazia');
    RETURN;
  END

  IF OBJECT_ID('tempdb..#frag') IS NOT NULL DROP TABLE #frag;
  CREATE TABLE #frag(
    schema_name sysname, table_name sysname, object_id int, index_id int, index_name sysname,
    partition_number int, page_count bigint, frag float, is_partitioned bit
  );

  /* Coleta de fragmentação — alinhada ao REPORT e ignorando disabled/hypothetical */
  SET @sql = N'
    INSERT #frag
    SELECT
      s.name  AS schema_name,
      o.name  AS table_name,
      ps.object_id,
      ps.index_id,
      i.name  AS index_name,
      ps.partition_number,
      ps.page_count,
      ps.avg_fragmentation_in_percent AS frag,
      CASE WHEN i.data_space_id IN (SELECT data_space_id FROM '+@db+N'.sys.partition_schemes) THEN 1 ELSE 0 END AS is_partitioned
    FROM '+@db+N'.sys.objects o
    JOIN '+@db+N'.sys.schemas s ON s.schema_id = o.schema_id
    JOIN '+@db+N'.sys.indexes i
      ON i.object_id = o.object_id
     AND i.index_id  > 0
     AND i.type      IN (1,2)
     AND i.name IS NOT NULL
     AND i.is_hypothetical = 0
     AND i.is_disabled     = 0
    JOIN #alvo a
      ON a.object_id = o.object_id
    CROSS APPLY sys.dm_db_index_physical_stats(DB_ID(N'''+REPLACE(@TargetDB,'''','''''')+N'''),
                                               o.object_id, i.index_id, NULL, @ScanMode) ps
    WHERE o.type = ''U''
      AND ps.page_count > 25
      AND ps.avg_fragmentation_in_percent >= @FragMin;';
  EXEC sp_executesql @sql, N'@FragMin float, @ScanMode nvarchar(10)', @FragMin=@FragMin, @ScanMode=@FragScanMode;

  /* Modificações/estatísticas */
  IF OBJECT_ID('tempdb..#mods') IS NOT NULL DROP TABLE #mods;
  CREATE TABLE #mods(object_id int, index_id int, mod_pct float, is_incremental bit);

  BEGIN TRY
    SET @sql = N'
      INSERT #mods(object_id,index_id,mod_pct,is_incremental)
      SELECT st.object_id, ix.index_id,
             CASE WHEN ISNULL(dp.[rows],0)=0 THEN 0.0 ELSE (dp.modification_counter*100.0/dp.[rows]) END,
             st.is_incremental
      FROM '+@db+N'.sys.stats st
      JOIN '+@db+N'.sys.indexes ix ON ix.object_id=st.object_id AND ix.name=st.name
      OUTER APPLY sys.dm_db_stats_properties(st.object_id, st.stats_id) dp;';
    EXEC sp_executesql @sql;
  END TRY
  BEGIN CATCH
    SET @sql = N'
      INSERT #mods(object_id,index_id,mod_pct,is_incremental)
      SELECT ix.object_id, ix.index_id,
             CASE WHEN ISNULL(si.rowcnt,0)=0 THEN 0.0 ELSE (si.rowmodctr*100.0/si.rowcnt) END,
             0
      FROM '+@db+N'.sys.indexes ix
      LEFT JOIN '+@db+N'.sys.sysindexes si ON si.id=ix.object_id AND si.indid=ix.index_id
      WHERE ix.index_id>0;';
    EXEC sp_executesql @sql;
  END CATCH;

  IF OBJECT_ID('tempdb..#todo') IS NOT NULL DROP TABLE #todo;
  CREATE TABLE #todo(
    id int IDENTITY(1,1) PRIMARY KEY,
    schema_name sysname, table_name sysname, object_id int, index_id int, index_name sysname,
    partition_number int, page_count bigint, frag float, mod_pct float, is_partitioned bit,
    is_incremental bit, action nvarchar(12), cmd1 nvarchar(MAX), cmd2 nvarchar(MAX), done bit DEFAULT 0
  );

  ;WITH base AS(
    SELECT f.*, ISNULL(m.mod_pct,0) AS mod_pct, ISNULL(m.is_incremental,0) AS is_incremental
    FROM #frag f LEFT JOIN #mods m
      ON m.object_id=f.object_id AND m.index_id=f.index_id
  )
  INSERT #todo(schema_name,table_name,object_id,index_id,index_name,partition_number,page_count,frag,mod_pct,is_partitioned,is_incremental,action)
  SELECT b.schema_name,b.table_name,b.object_id,b.index_id,b.index_name,b.partition_number,b.page_count,b.frag,b.mod_pct,b.is_partitioned,b.is_incremental,
         CASE WHEN @Mode=N'STATS' THEN N'STATS'
              WHEN @Mode=N'ALTER' THEN CASE WHEN b.frag<@FragRebuild THEN N'REORGANIZE' ELSE N'REBUILD' END
              ELSE CASE
                     WHEN b.mod_pct>=@HotModPct AND b.frag<@FragRebuild THEN N'STATS'
                     WHEN b.frag BETWEEN @FragMin AND @FragRebuild THEN N'REORGANIZE'
                     WHEN b.frag>=@FragRebuild AND (b.page_count>=@LargePages OR b.mod_pct>=@HotModPct) THEN N'REORGANIZE'
                     ELSE N'REBUILD'
                   END
         END
  FROM base b;

  DECLARE @tot int, @cReb int, @cReo int, @cSta int;
  SELECT @tot=COUNT(*),
         @cReb=SUM(CASE WHEN action=N'REBUILD'    THEN 1 ELSE 0 END),
         @cReo=SUM(CASE WHEN action=N'REORGANIZE' THEN 1 ELSE 0 END),
         @cSta=SUM(CASE WHEN action=N'STATS'      THEN 1 ELSE 0 END)
  FROM #todo;

  INSERT dbo.index_maint_log(db_name,status,acao,erro)
  VALUES (@TargetDB,N'INFO',N'STAGE_COLLECT_END',
          N'Candidatos='+CAST(@tot AS nvarchar(20))+N' | REBUILD='+CAST(@cReb AS nvarchar(20))+
          N' REORG='+CAST(@cReo AS nvarchar(20))+N' STATS='+CAST(@cSta AS nvarchar(20)));

  /* Montagem dos comandos */
  UPDATE t
  SET
    cmd1 =
      CASE
        WHEN action=N'REORGANIZE' THEN
          N'ALTER INDEX '+QUOTENAME(index_name)+N' ON '+@db+N'.'+QUOTENAME(schema_name)+N'.'+QUOTENAME(table_name)+
          N' REORGANIZE'+CASE WHEN is_partitioned=1 THEN N' PARTITION = '+CAST(partition_number AS nvarchar(10)) ELSE N'' END+N';'
        WHEN action=N'REBUILD' THEN
          N'ALTER INDEX '+QUOTENAME(index_name)+N' ON '+@db+N'.'+QUOTENAME(schema_name)+N'.'+QUOTENAME(table_name)+
          N' REBUILD '+CASE WHEN is_partitioned=1 THEN N'PARTITION = '+CAST(partition_number AS nvarchar(10))+N' ' ELSE N'' END+
          CASE
            WHEN (@HasResumable=1 AND @UseResumable=1 AND @Enterprise=1 AND @OnlineDesejado=1) THEN
                N'WITH (ONLINE = ON' +
                  CASE WHEN @HasWaitLP=1 AND @UseWaitLowPriority=1
                       THEN N' (WAIT_AT_LOW_PRIORITY (MAX_DURATION = 30 MINUTES, ABORT_AFTER_WAIT = SELF))' ELSE N'' END +
                  N', RESUMABLE = ON, MAX_DURATION = '+CAST(@OpMaxMinutes AS nvarchar(10))+N' MINUTES' +
                  CASE WHEN @MaxDOP IS NOT NULL THEN N', MAXDOP = '+CAST(@MaxDOP AS nvarchar(10)) ELSE N'' END +
                  CASE WHEN @FillFactor IS NOT NULL THEN N', FILLFACTOR = '+CAST(@FillFactor AS nvarchar(10)) ELSE N'' END +
                N');'
            ELSE
                N'WITH (' +
                  N'SORT_IN_TEMPDB = ON' +
                  CASE WHEN @Enterprise=1 AND @OnlineDesejado=1 THEN N', ONLINE = ON' ELSE N', ONLINE = OFF' END +
                  CASE WHEN @MaxDOP IS NOT NULL THEN N', MAXDOP = '+CAST(@MaxDOP AS nvarchar(10)) ELSE N'' END +
                  CASE WHEN @FillFactor IS NOT NULL THEN N', FILLFACTOR = '+CAST(@FillFactor AS nvarchar(10)) ELSE N'' END +
                N');'
          END
        ELSE NULL
      END,
    cmd2 =
      CASE
        WHEN (@Mode IN (N'STATS',N'HYBRID')) AND action IN (N'STATS',N'REORGANIZE') THEN
          N'UPDATE STATISTICS '+@db+N'.'+QUOTENAME(schema_name)+N'.'+QUOTENAME(table_name)+
          N' ('+QUOTENAME(index_name)+N') WITH '+
          CASE WHEN @StatsMode=N'FULLSCAN' THEN N'FULLSCAN' ELSE N'SAMPLE '+CAST(@SamplePercent AS nvarchar(10))+N' PERCENT' END+
          CASE WHEN is_partitioned=1 AND is_incremental=1
               THEN N' ON PARTITIONS ('+CAST(partition_number AS nvarchar(10))+N')' ELSE N'' END+N';'
        ELSE NULL
      END
  FROM #todo t;

  /* Snapshot da fila */
  DELETE FROM dbo.IndexMaint_Queue WHERE db_name=@TargetDB AND created_at < DATEADD(day,-7,SYSDATETIME());
  INSERT dbo.IndexMaint_Queue
         (run_id, db_name, schema_name, table_name, index_name, partition_number,
          action, page_count, frag_before, mod_pct, state, cmd1, cmd2)
  SELECT @RunId, @TargetDB, schema_name, table_name, index_name, partition_number,
         action, page_count, frag, mod_pct, N'PENDING', cmd1, cmd2
  FROM #todo;

  /* ===== FASE 3: EXECUÇÃO ===== */
  INSERT dbo.index_maint_log(db_name,status,acao,erro)
  VALUES (@TargetDB,N'INFO',N'STAGE_EXEC_START',N'Execução (deadline '+CONVERT(nvarchar(19),@deadline,120)+N')');

  DECLARE @id int, @action nvarchar(12), @cmd nvarchar(MAX),
          @schema sysname, @table sysname, @idx sysname, @part int,
          @frag_before float, @frag_after float, @tini datetime2(0), @tfim datetime2(0),
          @sendKB bigint, @redoKB bigint, @status nvarchar(20), @erro nvarchar(MAX);

  WHILE GETDATE() < @deadline
  BEGIN
    SELECT TOP(1) @id = id
    FROM #todo WHERE done=0
    ORDER BY CASE action WHEN N'REBUILD' THEN 1 WHEN N'REORGANIZE' THEN 2 ELSE 3 END,
             page_count ASC, frag DESC;

    IF @id IS NULL BREAK;

    SELECT @action=action, @cmd=cmd1, @schema=schema_name, @table=table_name, @idx=index_name,
           @part=partition_number, @frag_before=frag
    FROM #todo WHERE id=@id;

    /* Guard-rail AlwaysOn: rebaixar REBUILD se filas grandes */
    IF @action=N'REBUILD'
    BEGIN
      SELECT @sendKB=NULL,@redoKB=NULL;
      IF OBJECT_ID('sys.dm_hadr_database_replica_states') IS NOT NULL
        SELECT @sendKB=log_send_queue_size, @redoKB=redo_queue_size
        FROM sys.dm_hadr_database_replica_states
        WHERE is_local=1 AND database_id=@dbid;

      IF ISNULL(@sendKB,0) > (@AGMaxSendQueueMB*1024) OR ISNULL(@redoKB,0) > (@AGMaxRedoQueueMB*1024)
      BEGIN
        UPDATE #todo SET action=N'REORGANIZE',
                         cmd1 = N'ALTER INDEX '+QUOTENAME(index_name)+N' ON '+@db+N'.'+QUOTENAME(schema_name)+N'.'+QUOTENAME(table_name)+
                                N' REORGANIZE'+CASE WHEN is_partitioned=1 THEN N' PARTITION = '+CAST(partition_number AS nvarchar(10)) ELSE N'' END+N';',
                         cmd2 = COALESCE(cmd2, N'UPDATE STATISTICS '+@db+N'.'+QUOTENAME(schema_name)+N'.'+QUOTENAME(table_name)+
                                N' ('+QUOTENAME(index_name)+N') WITH '+
                                CASE WHEN @StatsMode=N'FULLSCAN' THEN N'FULLSCAN' ELSE N'SAMPLE '+CAST(@SamplePercent AS nvarchar(10))+N' PERCENT' END+N';')
        WHERE id=@id;
        SELECT @action=action, @cmd=cmd1 FROM #todo WHERE id=@id;
      END
    END

    /* Guard: ignorar índice desabilitado (corrida) */
    IF EXISTS (
      SELECT 1
      FROM #db_indexes di
      WHERE di.object_id = (SELECT object_id FROM #db_objects WHERE schema_name=@schema AND table_name=@table)
        AND di.name = @idx
        AND di.is_disabled = 1
    )
    BEGIN
      SET @status = N'IGNORADO';
      SET @erro   = N'Índice desabilitado — ignorado';

      INSERT dbo.index_maint_log
        (db_name,dt_inicio,dt_fim,schema_name,table_name,index_name,partition_number,
         page_count,frag_before,frag_after,mod_pct,acao,comando,status,erro,cancelado)
      SELECT @TargetDB,SYSDATETIME(),SYSDATETIME(),@schema,@table,@idx,@part,
             t.page_count,@frag_before,NULL,t.mod_pct,@action,@cmd,@status,@erro,0
      FROM #todo t WHERE t.id=@id;

      UPDATE dbo.IndexMaint_Queue
         SET state=N'CANCELADO', tfim=SYSDATETIME(),
             erro = COALESCE(erro,N'')+N' | Índice disabled'
      WHERE run_id=@RunId AND db_name=@TargetDB
        AND schema_name=@schema AND table_name=@table AND index_name=@idx
        AND ((partition_number IS NULL AND @part IS NULL) OR (partition_number=@part))
        AND state IN (N'RUNNING',N'PENDING');

      UPDATE #todo SET done=1 WHERE id=@id;
      CONTINUE;
    END

    /* Marcar RUNNING na fila */
    UPDATE TOP (1) dbo.IndexMaint_Queue
       SET state=N'RUNNING', tini=SYSDATETIME()
    WHERE run_id=@RunId AND db_name=@TargetDB
      AND schema_name=@schema AND table_name=@table AND index_name=@idx
      AND ((partition_number IS NULL AND @part IS NULL) OR (partition_number=@part))
      AND state=N'PENDING';

    IF GETDATE() >= @deadline
    BEGIN
      INSERT dbo.index_maint_log
        (db_name,dt_inicio,dt_fim,schema_name,table_name,index_name,partition_number,page_count,frag_before,frag_after,mod_pct,acao,comando,status,erro,cancelado)
      SELECT @TargetDB,NULL,NULL,schema_name,table_name,index_name,partition_number,page_count,frag,NULL,mod_pct,action,cmd1,N'CANCELADO',N'Janela esgotada',1
      FROM #todo WHERE id=@id;

      UPDATE dbo.IndexMaint_Queue
         SET state=N'CANCELADO', tfim=SYSDATETIME(),
             erro = COALESCE(erro,N'')+N' | Janela esgotada'
      WHERE run_id=@RunId AND db_name=@TargetDB
        AND schema_name=@schema AND table_name=@table AND index_name=@idx
        AND ((partition_number IS NULL AND @part IS NULL) OR (partition_number=@part))
        AND state IN (N'RUNNING',N'PENDING');

      UPDATE #todo SET done=1 WHERE id=@id;
      BREAK;
    END

    /* Execução do cmd1 */
    SET @tini = SYSDATETIME(); SET @status='OK'; SET @erro=NULL;
    IF @cmd IS NOT NULL
    BEGIN
      BEGIN TRY
        EXEC (@cmd);
      END TRY
      BEGIN CATCH
        SET @status='ERRO'; SET @erro = ERROR_MESSAGE();
      END CATCH;
    END
    SET @tfim = SYSDATETIME();

    SELECT @frag_after = ps.avg_fragmentation_in_percent
    FROM sys.dm_db_index_physical_stats(@dbid,
      (SELECT object_id FROM #db_objects WHERE schema_name=@schema AND table_name=@table),
      (SELECT index_id  FROM #db_indexes WHERE object_id=(SELECT object_id FROM #db_objects WHERE schema_name=@schema AND table_name=@table) AND name=@idx),
      @part, N'LIMITED') ps;

    INSERT dbo.index_maint_log
      (db_name,dt_inicio,dt_fim,schema_name,table_name,index_name,partition_number,page_count,frag_before,frag_after,mod_pct,acao,comando,status,erro,cancelado)
    SELECT @TargetDB,@tini,@tfim,@schema,@table,@idx,@part,t.page_count,@frag_before,@frag_after,t.mod_pct,@action,@cmd,@status,@erro,0
    FROM #todo t WHERE t.id=@id;

    UPDATE dbo.IndexMaint_Queue
       SET state = CASE WHEN @status=N'ERRO' THEN N'ERRO' ELSE N'DONE' END,
           tfim  = SYSDATETIME(),
           frag_after = @frag_after,
           erro = CASE WHEN @status=N'ERRO' THEN COALESCE(@erro,erro) ELSE erro END
    WHERE run_id=@RunId AND db_name=@TargetDB
      AND schema_name=@schema AND table_name=@table AND index_name=@idx
      AND ((partition_number IS NULL AND @part IS NULL) OR (partition_number=@part))
      AND state IN (N'RUNNING',N'PENDING');

    /* STATS (cmd2), se houver e ainda dentro da janela */
    SELECT @cmd = cmd2 FROM #todo WHERE id=@id;
    IF @cmd IS NOT NULL AND GETDATE() < @deadline
    BEGIN
      SET @tini = SYSDATETIME(); SET @status='OK'; SET @erro=NULL;
      BEGIN TRY
        EXEC (@cmd);
      END TRY
      BEGIN CATCH
        SET @status='ERRO'; SET @erro = ERROR_MESSAGE();
      END CATCH;
      SET @tfim = SYSDATETIME();

      SELECT @frag_after = ps.avg_fragmentation_in_percent
      FROM sys.dm_db_index_physical_stats(@dbid,
        (SELECT object_id FROM #db_objects WHERE schema_name=@schema AND table_name=@table),
        (SELECT index_id  FROM #db_indexes WHERE object_id=(SELECT object_id FROM #db_objects WHERE schema_name=@schema AND table_name=@table) AND name=@idx),
        @part, N'LIMITED') ps;

      INSERT dbo.index_maint_log
        (db_name,dt_inicio,dt_fim,schema_name,table_name,index_name,partition_number,page_count,frag_before,frag_after,mod_pct,acao,comando,status,erro,cancelado)
      SELECT @TargetDB,@tini,@tfim,@schema,@table,@idx,@part,t.page_count,@frag_after,@frag_after,t.mod_pct,N'STATS',@cmd,@status,@erro,0
      FROM #todo t WHERE t.id=@id;

      UPDATE dbo.IndexMaint_Queue
         SET tfim = SYSDATETIME(),
             frag_after = @frag_after,
             erro = CASE WHEN @status=N'ERRO' THEN COALESCE(@erro,erro) ELSE erro END
      WHERE run_id=@RunId AND db_name=@TargetDB
        AND schema_name=@schema AND table_name=@table AND index_name=@idx
        AND ((partition_number IS NULL AND @part IS NULL) OR (partition_number=@part));
    END

    UPDATE #todo SET done=1 WHERE id=@id;
    SET @id = NULL;
  END

  INSERT dbo.index_maint_log(db_name,status,acao,erro)
  VALUES (@TargetDB,N'INFO',N'STAGE_EXEC_END',N'Execução concluída');

  INSERT dbo.index_maint_log(db_name,status,acao,erro)
  VALUES (@TargetDB,N'INFO',N'STAGE_END',
          N'FINALIZADO para '+@db+N' — duração(s): '+CAST(DATEDIFF(SECOND,@tStart,SYSDATETIME()) AS nvarchar(20)));
END
GO




4) JOB (SQL Agent)
USE msdb;
GO

-- Remove o job se já existir
IF EXISTS (SELECT 1 FROM msdb.dbo.sysjobs WHERE name = N'IDX_Maint_UAU_DIRECIONAL')
BEGIN
  EXEC msdb.dbo.sp_delete_job @job_name = N'IDX_Maint_UAU_DIRECIONAL';
END
GO

-- Cria o job
EXEC msdb.dbo.sp_add_job
  @job_name = N'IDX_Maint_UAU_DIRECIONAL',
  @enabled = 1,
  @description = N'Manutenção de índices/estatísticas via startupmonitor.dbo.IndexMaint_Run',
  @category_name = N'Database Maintenance',
  @owner_login_name = N'sa';
GO

-- Passo único: executa a procedure com o perfil DIARIO
EXEC msdb.dbo.sp_add_jobstep
  @job_name = N'IDX_Maint_UAU_DIRECIONAL',
  @step_name = N'Executar IndexMaint_Run (perfil DIARIO)',
  @subsystem = N'TSQL',
  @database_name = N'startupmonitor',
  @command = N'
EXEC startupmonitor.dbo.IndexMaint_Run
  @TargetDB = N''UAU_DIRECIONAL'',
  @Profile  = N''DIARIO'';
',
  @on_success_action = 1, -- Quit with success
  @on_fail_action = 2;    -- Quit with failure
GO

-- Agenda diária às 02:00
EXEC msdb.dbo.sp_add_schedule
  @schedule_name = N'Diario_02h',
  @freq_type = 4,           -- daily
  @freq_interval = 1,       -- every 1 day
  @active_start_time = 20000; -- 02:00:00
GO

-- Anexa o schedule ao job
EXEC msdb.dbo.sp_attach_schedule
  @job_name = N'IDX_Maint_UAU_DIRECIONAL',
  @schedule_name = N'Diario_02h';
GO

-- Vincula o job ao servidor local
EXEC msdb.dbo.sp_add_jobserver
  @job_name = N'IDX_Maint_UAU_DIRECIONAL',
  @server_name = N'(LOCAL)';
GO


5) Execução manual (exemplos rápidos)
/* 5.1) Somente relatório de fragmentação (ALVOs cadastrados) */
EXEC startupmonitor.dbo.IndexMaint_Run
  @TargetDB    = N'UAU_DIRECIONAL',
  @Mode        = N'REPORT',
  @Report      = N'FRAG',         -- FRAG|RESUMABLE|LASTRUN|ALL
  @ReportScope = N'ALVO',         -- ALVO|TODAS
  @FragMin     = 10;

/* 5.2) Relatório FRAG de TODAS as tabelas (gera coluna insert_stmt p/ IndexMaint_Alvo) */
EXEC startupmonitor.dbo.IndexMaint_Run
  @TargetDB    = N'UAU_DIRECIONAL',
  @Mode        = N'REPORT',
  @Report      = N'FRAG',
  @ReportScope = N'TODAS',
  @FragMin     = 10;

/* 5.3) Execução padrão (perfil DIARIO) */
EXEC startupmonitor.dbo.IndexMaint_Run
  @TargetDB = N'UAU_DIRECIONAL',
  @Profile  = N'DIARIO';

/* 5.4) HYBRID com janela curta (smoke test) */
EXEC startupmonitor.dbo.IndexMaint_Run
  @TargetDB      = N'UAU_DIRECIONAL',
  @Mode          = N'HYBRID',
  @WindowMinutes = 15,
  @MaxDOP        = 2;

/* 5.5) Apenas UPDATE STATISTICS (FULLSCAN) */
EXEC startupmonitor.dbo.IndexMaint_Run
  @TargetDB   = N'UAU_DIRECIONAL',
  @Mode       = N'STATS',
  @StatsMode  = N'FULLSCAN',
  @WindowMinutes = 60;

/* 5.6) Apenas ALTER (Reorg < FragRebuild; Rebuild >= FragRebuild), sem resumable */
EXEC startupmonitor.dbo.IndexMaint_Run
  @TargetDB           = N'UAU_DIRECIONAL',
  @Mode               = N'ALTER',
  @UseResumable       = 0,
  @OnlineDesejado     = 1,
  @UseWaitLowPriority = 1,
  @FragMin            = 10,
  @FragRebuild        = 30,
  @MaxDOP             = 2;

/* 5.7) Reportar resumables ativos e última execução */
EXEC startupmonitor.dbo.IndexMaint_Run
  @TargetDB = N'UAU_DIRECIONAL',
  @Mode     = N'REPORT',
  @Report   = N'ALL';


6) Diagnósticos & Consultas úteis
/* 6.1) Últimos 200 logs */
SELECT TOP (200)
  log_id, dt, db_name, status, acao, schema_name, table_name, index_name,
  partition_number, page_count, frag_before, frag_after, mod_pct,
  comando, erro
FROM dbo.index_maint_log
ORDER BY log_id DESC;

/* 6.2) Somente erros recentes */
SELECT TOP (200)
  dt, db_name, schema_name, table_name, index_name, acao, erro, comando
FROM dbo.index_maint_log
WHERE status = N'ERRO'
ORDER BY dt DESC;

/* 6.3) Duração média/máxima por ação (com dt_inicio/dt_fim) */
SELECT acao,
       COUNT(*)            AS qtd,
       AVG(DATEDIFF(SECOND, dt_inicio, dt_fim)) AS avg_sec,
       MAX(DATEDIFF(SECOND, dt_inicio, dt_fim)) AS max_sec
FROM dbo.index_maint_log
WHERE dt_inicio IS NOT NULL AND dt_fim IS NOT NULL
GROUP BY acao
ORDER BY acao;

/* 6.4) Última execução (start/end/duração) por DB */
DECLARE @DB sysname = N'UAU_DIRECIONAL';

WITH starts AS (
  SELECT TOP (1) dt AS last_start
  FROM dbo.index_maint_log
  WHERE db_name=@DB AND status=N'INFO' AND acao=N'STAGE_BEGIN'
  ORDER BY dt DESC
),
ends AS (
  SELECT TOP (1) dt AS last_end
  FROM dbo.index_maint_log
  WHERE db_name=@DB AND status=N'INFO' AND acao=N'STAGE_END'
  ORDER BY dt DESC
)
SELECT s.last_start, e.last_end,
       CASE WHEN s.last_start IS NOT NULL AND e.last_end IS NOT NULL
            THEN DATEDIFF(SECOND, s.last_start, e.last_end) END AS duration_seconds
FROM starts s CROSS JOIN ends e;

/* 6.5) Alvos cadastrados (multi-DB) */
SELECT db_name, schema_name, table_name
FROM dbo.IndexMaint_Alvo
ORDER BY db_name, schema_name, table_name;

/* 6.6) Pendências/Progresso da Fila (último run) */
DECLARE @DB sysname = N'UAU_DIRECIONAL';
DECLARE @RunId uniqueidentifier =
 (SELECT TOP (1) run_id FROM dbo.IndexMaint_Queue WHERE db_name=@DB ORDER BY created_at DESC);

SELECT @RunId AS RunId;

SELECT state, COUNT(*) AS qtd
FROM dbo.IndexMaint_Queue
WHERE run_id=@RunId
GROUP BY state;

SELECT item_id, schema_name, table_name, index_name, partition_number,
       action, page_count, frag_before, mod_pct, state, tini, tfim, erro
FROM dbo.IndexMaint_Queue
WHERE run_id=@RunId AND state IN (N'PENDING',N'RUNNING')
ORDER BY state, page_count DESC, frag_before DESC;

/* 6.7) ETA simples (média por item) do último run */
DECLARE @DB sysname = N'UAU_DIRECIONAL';
DECLARE @RunId uniqueidentifier =
 (SELECT TOP (1) run_id FROM dbo.IndexMaint_Queue WHERE db_name=@DB ORDER BY created_at DESC);

;WITH stats AS (
  SELECT DATEDIFF(SECOND, tini, tfim) AS sec
  FROM dbo.IndexMaint_Queue
  WHERE run_id=@RunId AND state=N'DONE' AND tini IS NOT NULL AND tfim IS NOT NULL
        AND DATEDIFF(SECOND, tini, tfim) > 0
)
SELECT
  total      = (SELECT COUNT(*) FROM dbo.IndexMaint_Queue WHERE run_id=@RunId),
  done       = (SELECT COUNT(*) FROM dbo.IndexMaint_Queue WHERE run_id=@RunId AND state=N'DONE'),
  running    = (SELECT COUNT(*) FROM dbo.IndexMaint_Queue WHERE run_id=@RunId AND state=N'RUNNING'),
  pending    = (SELECT COUNT(*) FROM dbo.IndexMaint_Queue WHERE run_id=@RunId AND state=N'PENDING'),
  erros      = (SELECT COUNT(*) FROM dbo.IndexMaint_Queue WHERE run_id=@RunId AND state=N'ERRO'),
  cancelados = (SELECT COUNT(*) FROM dbo.IndexMaint_Queue WHERE run_id=@RunId AND state=N'CANCELADO'),
  avg_sec_per_item = (SELECT AVG(1.0*sec) FROM stats),
  est_remaining_sec = (SELECT AVG(1.0*sec) FROM stats) *
                      (SELECT COUNT(*) FROM dbo.IndexMaint_Queue WHERE run_id=@RunId AND state=N'PENDING');

/* 6.8) ETA ponderado por tamanho (page_count) do último run */
DECLARE @DB sysname = N'UAU_DIRECIONAL';
DECLARE @RunId uniqueidentifier =
 (SELECT TOP (1) run_id FROM dbo.IndexMaint_Queue WHERE db_name=@DB ORDER BY created_at DESC);

;WITH done AS (
  SELECT NULLIF(page_count,0) AS page_count, DATEDIFF(SECOND,tini,tfim) AS sec
  FROM dbo.IndexMaint_Queue
  WHERE run_id=@RunId AND state=N'DONE' AND tini IS NOT NULL AND tfim IS NOT NULL
),
coef AS (
  SELECT NULLIF(AVG(1.0*sec/page_count),0) AS sec_per_page
  FROM done WHERE page_count IS NOT NULL
)
SELECT est_remaining_sec =
  (SELECT SUM(CASE WHEN p.page_count>0 THEN p.page_count * c.sec_per_page END)
   FROM dbo.IndexMaint_Queue p
   CROSS JOIN coef c
   WHERE p.run_id=@RunId AND p.state=N'PENDING');

/* 6.9) Resumables ativos no alvo (use na master/startupmonitor) */
DECLARE @DB sysname = N'UAU_DIRECIONAL';
DECLARE @db sysname = QUOTENAME(@DB);

DECLARE @sql nvarchar(max) = N'
SELECT
  OBJECT_SCHEMA_NAME(ro.object_id, DB_ID(N'''+REPLACE(@DB,'''','''''')+N''')) AS schema_name,
  OBJECT_NAME      (ro.object_id, DB_ID(N'''+REPLACE(@DB,'''','''''')+N''')) AS table_name,
  i.name AS index_name,
  ro.state_desc, ro.percent_complete, ro.start_time, ro.last_pause_time
FROM '+@db+N'.sys.index_resumable_operations ro
JOIN '+@db+N'.sys.indexes i
  ON i.object_id=ro.object_id AND i.index_id=ro.index_id;';
EXEC sp_executesql @sql;

/* 6.10) Fragmentação atual (rápido) — ALVOs cadastrados */
DECLARE @DB sysname = N'UAU_DIRECIONAL';
DECLARE @dbid int = DB_ID(@DB);

SELECT a.schema_name, a.table_name, i.name AS index_name,
       ps.partition_number, ps.page_count, ps.avg_fragmentation_in_percent AS frag
FROM startupmonitor.dbo.IndexMaint_Alvo a
JOIN (SELECT o.object_id, s.name AS schema_name, o.name AS table_name
      FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id
      WHERE 1=0) z ON 1=0;  -- dummy p/ IntelliSense

CROSS APPLY sys.dm_db_index_physical_stats(@dbid,
    OBJECT_ID(QUOTENAME(@DB)+N'.'+QUOTENAME(a.schema_name)+N'.'+QUOTENAME(a.table_name)),
    NULL, NULL, N'LIMITED') ps
JOIN (SELECT * FROM sys.indexes) i
  ON i.object_id = ps.object_id AND i.index_id = ps.index_id
WHERE a.db_name=@DB AND ps.index_id>0 AND ps.page_count>25
ORDER BY frag DESC, ps.page_count DESC;

/* 6.11) Gerar INSERTs de alvos por tamanho (para popular IndexMaint_Alvo) */
DECLARE @DB sysname = N'startupmonitor';
DECLARE @sql nvarchar(max) = N'
;WITH tab AS (
  SELECT s.name schema_name, o.name table_name,
         SUM(a.total_pages)*8.0/1024.0 AS total_mb
  FROM '+QUOTENAME(@DB)+N'.sys.objects o
  JOIN '+QUOTENAME(@DB)+N'.sys.schemas s ON s.schema_id=o.schema_id
  JOIN '+QUOTENAME(@DB)+N'.sys.partitions p ON p.object_id=o.object_id
  JOIN '+QUOTENAME(@DB)+N'.sys.allocation_units a
    ON a.container_id = CASE WHEN a.type IN (1,3) THEN p.hobt_id ELSE p.partition_id END
  WHERE o.type=''U''
  GROUP BY s.name,o.name
)
  SELECT ''INSERT startupmonitor.dbo.IndexMaint_Alvo(db_name,schema_name,table_name) VALUES (N'''+ REPLACE(N''''+@DB+N'''','''','''')+N''',N''+SCHEMA_NAME+N'',N''+table_name+N'' );'' AS insert_stmt
FROM tab
WHERE total_mb >= 1000
ORDER BY total_mb DESC;';
PRINT (@sql);

/* 6.12) AlwaysOn (se houver) — filas atuais do banco alvo */
SELECT DB_NAME(drs.database_id) AS db_name,
       drs.is_primary_replica, drs.synchronization_state_desc,
       drs.log_send_queue_size, drs.redo_queue_size
FROM sys.dm_hadr_database_replica_states drs
WHERE DB_NAME(drs.database_id) = N'UAU_DIRECIONAL';

/* 6.13) Limpeza (opcional) — logs/filas antigos */
-- logs com mais de 60 dias
DELETE FROM dbo.index_maint_log
WHERE dt < DATEADD(day,-60,SYSDATETIME());

-- filas com mais de 7 dias
DELETE FROM dbo.IndexMaint_Queue
WHERE created_at < DATEADD(day,-7,SYSDATETIME());

/* 6.14) Abort/resume em massa (cautela!) — resumables do alvo */
DECLARE @DB sysname = N'UAU_DIRECIONAL';
DECLARE @Action nvarchar(10) = N'ABORT'; -- ou 'RESUME'
DECLARE @OpMin int = 20;

DECLARE @cmd nvarchar(max) = N'';
SELECT @cmd = @cmd +
  CASE WHEN @Action=N'ABORT' THEN
    N'ALTER INDEX '+QUOTENAME(i.name)+N' ON '+QUOTENAME(@DB)+N'.'+
      QUOTENAME(OBJECT_SCHEMA_NAME(ro.object_id,DB_ID(@DB)))+N'.'+
      QUOTENAME(OBJECT_NAME(ro.object_id,DB_ID(@DB)))+N' ABORT;'+CHAR(10)
  ELSE
    N'ALTER INDEX '+QUOTENAME(i.name)+N' ON '+QUOTENAME(@DB)+N'.'+
      QUOTENAME(OBJECT_SCHEMA_NAME(ro.object_id,DB_ID(@DB)))+N'.'+
      QUOTENAME(OBJECT_NAME(ro.object_id,DB_ID(@DB)))+N' RESUME WITH (MAX_DURATION = '+CAST(@OpMin AS nvarchar(10))+N' MINUTES);'+CHAR(10)
  END
FROM  (SELECT * FROM sys.index_resumable_operations) ro
JOIN  (SELECT * FROM sys.indexes) i
  ON i.object_id=ro.object_id AND i.index_id=ro.index_id
WHERE DB_ID(@DB) IS NOT NULL;

PRINT @cmd; -- revise
--EXEC (@cmd); -- descomente para executar



