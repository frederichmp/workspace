#!/bin/bash

#write
#	- Função chamada por outras funções de log, 
#	- Args
#		$1 - Caminho completo do arquivo de log
#		$2 - Conteúdo a ser escrito
write()
{	
	local file_log="${1}"
	local content="${2}"
	
	local dt=$(LANG=en_us_88591;date "+%d/%m/%Y_%H:%M:%S_%N")

	local log="${dt} -> ${content}"
	
	echo -e "$log" >> "${file_log}"
	
	echo "${content}"
	echo ""
}

# Realiza o startup da base de dados
start_database()
{
${CMD_SQL} << EOF

startup

exit;

EOF
}


# Inicializa o banco de dados
valid_database()
{
	local db_sid="${1}"
	
	export ORACLE_HOME="${DB_HOME}"
	export ORACLE_SID="${db_sid}"
	
	# Verifica se o banco de dados está ativo
	if ps -ef | grep "${ORACLE_SID}" | grep -v grep | grep -v alert > /dev/null; then
		
		write "$LOG_EXECUTION" 'ALERT - Base já estava em execução > '"${ORACLE_SID}" 
		write "$LOG_EXECUTION" '	 Observação: Se algum processo estiver executando com o mesmo nome do SID o STARTUP não é realizado'
		write "$LOG_EXECUTION" '	 Teste: ps -ef | grep '"${ORACLE_SID}"' | grep -v grep | grep -v alert'
		
	else
		
		write "$LOG_EXECUTION" 'START - Iniciando startup database > '"${ORACLE_SID}"
		
		# Inicializa o banco de dados
		start_database
		
		# Verifica se a base de dados foi inicializada com sucesso
		if ps -ef | grep "${ORACLE_SID}" | grep -v grep > /dev/null; then
		
			write "$LOG_EXECUTION" 'STARTUP [SUCCESS] - Base de dados inicializada > '"${ORACLE_SID}"
			
		else
		
			write "$LOG_EXECUTION" 'STARTUP [ERROR] - Falha ao inicializar a base de dados > '"${ORACLE_SID}"
			
		fi
		
	fi
}


LOG_EXECUTION='wds_log_start_database.log'
DB_HOME='/u01/app/oracle/product/12.1.0.2/dbhome_1'
CMD_SQL="${DB_HOME}"'/bin/sqlplus -s / as sysdba '


# Lista de banco de dados a serem inicializadas
# Exemplo: LIST_DATABASE='prd orcl sml'
LIST_DATABASE='totvstmp pgscdsv pgschmg'


# Pecorre a lista de banco de dados a serem inicializados
for db in ${LIST_DATABASE}; do
	valid_database "${db}"
done


