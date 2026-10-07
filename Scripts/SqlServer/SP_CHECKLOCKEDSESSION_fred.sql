--- SCRIPT PARA CAPTURAR E ENVIAR POR EMAIL
-- SESSOES QUE ESTAO TRAVANDO (LOCK)
-- MODIFIQUE O ASSUNTO NO CODIGO DE ENVIO DE EMAIL NA LINHA 173
-- MODO DE USO: OS VALORES SAO: LOGIN / QTD DE LOCKS / TEMPO DE ATIVIDADE
--EXEC auditoria.dbo.STR_CheckSessoesLocked 'login',0,'00 00:00:00.000'
--OU SEJA PARA MATAR SESSOES QUE ESTAO TRAVANDO MAIS DE 5 SESSOES A MAIS DE 5 MINUTOS USE A FORMA ABAIXO:
--exemplo: "EXEC auditoria.dbo.STR_CheckSessoesLocked 'sa',15,'00 00:05:00.000'"

USE [auditoria]
GO

/****** Object:  Table [dbo].[_temp_aud_locked_session_info_killed]    Script Date: 17/11/2023 19:53:14 ******/
IF  EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[_temp_aud_locked_session_info_killed]') AND type in (N'U'))
DROP TABLE [dbo].[_temp_aud_locked_session_info_killed]
GO

/****** Object:  Table [dbo].[_temp_aud_locked_session_info_killed]    Script Date: 17/11/2023 19:53:14 ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE TABLE [dbo].[_temp_aud_locked_session_info_killed](
	[dd hh:mm:ss.mss] [varchar](8000) NULL,
	[database_name] [nvarchar](128) NULL,
	[blocking_session_id] [smallint] NULL,
	[blocked_session_count] [varchar](30) NULL,
	[percent_complete] [varchar](30) NULL,
	[session_id] [smallint] NOT NULL,
	[sql_text] [xml] NULL,
	[wait_info] [nvarchar](4000) NULL,
	[status] [varchar](30) NOT NULL,
	[login_name] [nvarchar](128) NOT NULL,
	[host_name] [nvarchar](128) NULL,
	[program_name] [nvarchar](128) NULL,
	[start_time] [datetime] NOT NULL,
	[login_time] [datetime] NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

USE [auditoria]
GO

/****** Object:  Table [dbo].[aud_locked_session_info_killed]    Script Date: 17/11/2023 19:53:27 ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE TABLE [dbo].[aud_locked_session_info_killed](
	[ID] [int] IDENTITY(1,1) NOT NULL,
	[DATE_REGISTER] [datetime] NOT NULL,
	[dd hh:mm:ss.mss] [varchar](8000) NULL,
	[database_name] [nvarchar](128) NULL,
	[blocking_session_id] [smallint] NULL,
	[blocked_session_count] [varchar](30) NULL,
	[percent_complete] [varchar](30) NULL,
	[session_id] [smallint] NOT NULL,
	[sql_text] [xml] NULL,
	[wait_info] [nvarchar](4000) NULL,
	[status] [varchar](30) NOT NULL,
	[login_name] [nvarchar](128) NOT NULL,
	[host_name] [nvarchar](128) NULL,
	[program_name] [nvarchar](128) NULL,
	[start_time] [datetime] NOT NULL,
	[login_time] [datetime] NULL,
PRIMARY KEY CLUSTERED 
(
	[ID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

USE [auditoria]
GO

/****** Object:  StoredProcedure [dbo].[STR_CheckSessoesLocked]    Script Date: 17/11/2023 19:53:45 ******/
DROP PROCEDURE [dbo].[STR_CheckSessoesLocked]
GO

/****** Object:  StoredProcedure [dbo].[STR_CheckSessoesLocked]    Script Date: 17/11/2023 19:53:45 ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO


CREATE PROCEDURE [dbo].[STR_CheckSessoesLocked]
    @LOGINNAME NVARCHAR(100),
    @BlockedSessionCountThreshold INT,
	@TimeWaitThreshold NVARCHAR(100)
AS
BEGIN
	--MODEO DE USAR
	--------------------------------------------LOGIN,QTD_LOCK,TIME
	--EXEC auditoria.dbo.STR_CheckSessoesLocked 'sa',15,'00 00:05:00.000' 
    DECLARE @SPIDToKill INT,
            @HOSTNAME NVARCHAR(100),
            @PROGRAMNAME NVARCHAR(100),
            @KillCommand NVARCHAR(MAX);

    -- Trunca a tabela temporária
    TRUNCATE TABLE auditoria.dbo._temp_aud_locked_session_info_killed;

    -- Coleta todas as sessões para validar se existe lock
    EXEC sp_WhoIsActive
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
    @output_column_list = '[dd%][database_name][block%][percent_complete][session_id][sql_text][sql_command][wait_info][status][login_name][host_name][program_name][start_time][login_time]',
    @sort_order = '[blocked_session_count] desc',
    @format_output = 1,
    @destination_table = 'auditoria.dbo._temp_aud_locked_session_info_killed',
   -- @return_schema = 1,
   -- @schema = @s OUTPUT,
    @help = 0

    -- Valida se existe lock dentro das condições de estar bloqueando mais de X sessões e estar ativo por mais de 5 minutos.
    SELECT TOP 1 @SPIDToKill = session_id,
                @HOSTNAME = host_name,
                @PROGRAMNAME = program_name
    FROM auditoria.dbo._temp_aud_locked_session_info_killed
    WHERE blocked_session_count >= @BlockedSessionCountThreshold
        AND [dd hh:mm:ss.mss] > @TimeWaitThreshold
		AND login_name = @LOGINNAME;

	IF @SPIDToKill IS NOT NULL
	BEGIN
		SET @KillCommand = 'KILL ' + CAST(@SPIDToKill AS NVARCHAR(10));

		-- Captura detalhes da sessão bloqueadora e todos os bloqueados
		INSERT INTO auditoria.dbo.aud_locked_session_info_killed
		SELECT GETDATE(), * FROM auditoria.dbo._temp_aud_locked_session_info_killed;

		-- Cria o alerta de e-mail para matar a sessão, este é o primeiro passo
		BEGIN
			DECLARE @EmailBody NVARCHAR(MAX);

			SELECT @EmailBody = 'Há sessões bloqueadas com mais de ' + CAST(@BlockedSessionCountThreshold AS NVARCHAR(10)) + ' bloqueios e mais de 05 minutos de atividade.' + CHAR(13) + CHAR(10) +
								+ CHAR(13) + CHAR(10) +
								'COMANDO: ' + @KillCommand + CHAR(13) + CHAR(10) +
								+ CHAR(13) + CHAR(10) +
								'SESSAO: ' + CAST(@SPIDToKill AS NVARCHAR(10)) + CHAR(13) + CHAR(10) +
								'LOGIN: ' + @LOGINNAME + CHAR(13) + CHAR(10) +
								'HOST: ' + @HOSTNAME + CHAR(13) + CHAR(10) +
								'PROGRAMA: ' + @PROGRAMNAME + CHAR(13) + CHAR(10) +
								+ CHAR(13) + CHAR(10) +
								'Consulte a tabela: "select * from auditoria.dbo.aud_locked_session_info_killed" para mais informações'
								+ CHAR(13) + CHAR(10) +
								+ CHAR(13) + CHAR(10) +
								'Startup Dados e Sistemas - (31) 32417954 - www.startupnet.com.br';

			EXEC msdb.dbo.sp_send_dbmail
				@profile_name = 'StartupMail_Profile', -- Nome do perfil de e-mail configurado no SQL Server
				@recipients = 'fred.martins@startupnet.com.br', -- Endereço de e-mail do destinatário
				@subject = 'Alerta de Sessões Bloqueadas Luiza Barcelos',
				@body = @EmailBody;

			--SELECT @EmailBody
		END
	END
END

GO

