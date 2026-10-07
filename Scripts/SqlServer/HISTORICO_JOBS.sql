USE msdb;
GO

SELECT j.name AS 'Nome do Job',
       js.step_name AS 'Nome do Step',
       js.command AS 'Comando do Step',
       js.step_id AS 'ID do Step',
       js.subsystem AS 'Subsystem',
       js.on_success_action AS 'Ação em caso de Sucesso',
       js.on_fail_action AS 'Ação em caso de Falha',
       js.last_run_date AS 'Data da Última Execução',
       js.last_run_time AS 'Hora da Última Execução',
       js.last_run_duration AS 'Duração da Última Execução',
       js.last_run_outcome AS 'Resultado da Última Execução',
       js.last_run_retries AS 'Tentativas na Última Execução',
       js.server AS 'Servidor da Última Execução',
       j.enabled AS 'Habilitado',
       j.description AS 'Descrição do Job'
FROM dbo.sysjobs j
INNER JOIN dbo.sysjobsteps js ON j.job_id = js.job_id
WHERE j.name not like '%STR%'
and j.name not like '%Startup%'
ORDER BY j.name, js.step_id;



