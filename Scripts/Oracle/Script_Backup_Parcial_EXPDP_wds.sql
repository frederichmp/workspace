---------------------------------------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------
------------ WDS - SCRIPT PARA GERAR BACKUP PARCIAL VIA EXPDP -------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------
---- Autor: Wesley David Santos -------------------------------------------------------------------------------------------------------------------------------------
---- Skype: wesleydavidsantos   -------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------
---- Esse script tem como funcionalidade, gerar um expdp parcial dos dados, a quantidade de dados é de acordo com a quantidade de dias retroativos 		         ----
----																																					         ----
---- A listagem das tabelas é realizada de acordo com as seguintes regras:                                                                                       ----
----																																					         ----
---- As tabelas PAI que não seja FILHA de ninguém são consideradas tabelas primárias, desta forma elas são exportados no formato FULL.                           ----
---- As tabelas FILHAS que possuem colunas DATE ou TIMESTAMP em sua estrutura e onde essas colunas não podem ser NULL e que possuem mais de um milhão de         ----
---- linhas registradas, são as tabelas que serão filtradas pela quantidade de dias informados.														             ----
---- O restante das tabelas pertencentes aos OWNERS informados mas que não se encaixam nas categorias anteriores são exportados no formato FULL.                 ----
----																																					         ----	
---- Existem 3 variáveis de parâmetros:																												             ----	
---- Usando no SqlDeveloper será aberto uma caixa de diálogo onde devem ser informados os valores para cada uma. 										         ---- 	
----																																					         ----	
---- VAR_QTD_DIAS   >> Informe a quantidade de dias retroativos que deseja 																			             ----	
---- VAR_DIRECTORY  >> Informe o nome do diretório onde será armazenado o backup, este diretório é o usado pelo EXPDP 								             ----
---- VAR_OWNER_LIST >> Lista de OWNERS que serão exportados, separe cada um apenas por vírgula 														             ----
---- VAR_COMPRESSION_EXPDP >> Tipos de compressão, compressao de backup normal (ALL/DATA_ONLY/METADATA_ONLY/NONE). Banco Standard válido somente NONE            ----
---- VAR_FILESIZE_EXPDP >> Informa se cada arquivo de backup tem um tamanho máximo fixado, somente para EXPDP. Ex.: FILESIZE_EXPDP=500M [OFF->sem valor fixo]
---- VAR_PARALLEL_EXPDP >> Paralelismo do backup numero de canais. Somente números inteiros
----																																					         ----
---- Execução:																																		             ----	
---- Ao executar a QUERY serão retornados 9 colunas, os valores destas colunas devem ser usados para preencher o arquivo de parâmetro que será usado pelo EXPDP  ----
----																																					         ----	
---- Modelo de chamada do arquivo de parâmetro:																												     ----	
----																																					         ----	
----		expdp strbackup/senha parfile=NOME_ARQUIVO_PARAMETRO.par                                                                                             ---- 
----																																					         ----	
---- Modelo do arquivo de parâmetro: Crie um arquivo de parâmetro no formato abaixo, uma linha abaixo da outra												     ----	
----																																					         ----	
---- 		directory=NOME_DIRETORIO_BACKUP																														 ----		
---- 		dumpfile=NOME_FILE_BKP.dmp                                                                                                                           ----
---- 		logfile=NOME_LOG_FILE_BKP.log                                                                                                                        ----
----		exclude=OBJECT_EXCLUDE                                                                                                                               ----
---- 		tables=NOME_TABELAS_EXPORT                                                                                                                           ----
----		query=TABELAS_QUE_SERAO_FILTRADAS                                                                                                                    ----
---------------------------------------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------


-- Execute esse comando para desativar a chamada de variáveis atraves do símbolo "&"
SET DEFINE OFF;

-- OWNERS usados na Lojas Rede
-- SIRIUS,TELE,LRESTOQUE,BDCOMUM,INTEGRACAOMASTER,INTBDCOMUM,CEP,ECONNECT,INTFISCAL,MGR_BD,MKP,TOTEM,VTEX

-- Criando o diretório para backup do EXPDP
-- Obs: Primeiro verifique se o diretório já existe atraves da consulta: select * from all_directories;
CREATE OR REPLACE DIRECTORY BACKUP_PARCIAL AS '/backup/startup/bkp_parcial/';

-- Dando permissão para o usuário acessar o diretório de backup
GRANT READ, WRITE ON DIRECTORY BACKUP_PARCIAL TO strbackup;



--*******************************************************************
--*******************************************************************
--*******************************************************************
-- Gera as informações para realizar o backup
SELECT
	'compression=' || :VAR_COMPRESSION_EXPDP COMPRESSION_EXPDP,
	
	CASE WHEN :VAR_FILESIZE_EXPDP = 'OFF' THEN
		' '
	ELSE
		'filesize=' || :VAR_FILESIZE_EXPDP
	END FILESIZE_EXPDP,
	
	'parallel=' || :VAR_PARALLEL_EXPDP PARALLEL_EXPDP,
	'directory=' || :VAR_DIRECTORY DIRECTORY,
	'exclude=' ||'CONSTRAINT,REF_CONSTRAINT,INDEX' EXCLUDE,
	
	CASE WHEN :VAR_PARALLEL_EXPDP > 1 THEN
		'dumpfile=' || ('expdp_wds_parcial_' || TO_CHAR(sysdate, 'ddmmyy') || '_' || TO_CHAR(sysdate, 'HH24') || 'h' || TO_CHAR(sysdate, 'MI') || 'm' || TO_CHAR(sysdate, 'SS') || 's_%U_bkp.dmp')
	ELSE	
		'dumpfile=' || ('expdp_wds_parcial_' || TO_CHAR(sysdate, 'ddmmyy') || '_' || TO_CHAR(sysdate, 'HH24') || 'h' || TO_CHAR(sysdate, 'MI') || 'm' || TO_CHAR(sysdate, 'SS') || 's_bkp.dmp')
	END DUMPFILE,
	
	'logfile=' || ('expdp_wds_parcial_' || TO_CHAR(sysdate, 'ddmmyy') || '_' || TO_CHAR(sysdate, 'HH24') || 'h' || TO_CHAR(sysdate, 'MI') || 'm' || TO_CHAR(sysdate, 'SS') || 's_bkp.log') LOGFILE,
	LIST_TBL,
	QUERY_EXPDP
FROM
	(
		WITH
			LIST_TBLS AS ( -- Lista de todas as tabelas filhas que possuem colunas de DATE e TIMESTAMP
				SELECT
					TBL,
					COLUMN_NAME
				FROM
					(
						SELECT DISTINCT
							TBL.OWNER_TABLE TBL,
							(
								SELECT
									C.COLUMN_NAME
								FROM
									ALL_TAB_COLUMNS C
								WHERE
									ROWNUM = 1
									AND TBL.OWNER_TABLE = ( C.OWNER || '.' || C.TABLE_NAME)
									and num_nulls = 0 and (data_type = 'DATE' or data_type like 'TIMESTAMP%')
							) COLUMN_NAME
						FROM
						(
						
							SELECT
								DISTINCT
								( filha.owner || '.' || filha.table_name ) OWNER_TABLE
							FROM 
								sys.all_constraints filha,
								sys.all_cons_columns cols_filha,
								sys.all_constraints pai,
								sys.all_cons_columns cols_pai
							WHERE
								filha.owner in ( SELECT UPPER(REGEXP_SUBSTR (:VAR_OWNER_LIST, '[^,]+', 1, LEVEL)) SET_OWNER FROM DUAL CONNECT BY REGEXP_SUBSTR (:VAR_OWNER_LIST, '[^,]+', 1, LEVEL) IS NOT NULL )
								and pai.owner in ( SELECT UPPER(REGEXP_SUBSTR (:VAR_OWNER_LIST, '[^,]+', 1, LEVEL)) SET_OWNER FROM DUAL CONNECT BY REGEXP_SUBSTR (:VAR_OWNER_LIST, '[^,]+', 1, LEVEL) IS NOT NULL )
								
								and filha.constraint_name not like 'SYS_%'
								
								and filha.constraint_type = 'R'    
								and pai.constraint_type = 'P'
								
								and filha.constraint_name = cols_filha.constraint_name
								AND filha.owner = cols_filha.owner
								
								and pai.constraint_name = cols_pai.constraint_name
								AND pai.owner = cols_pai.owner
								
								AND filha.R_CONSTRAINT_NAME = pai.CONSTRAINT_NAME
								and pai.table_name in (
									-- ###
														SELECT 
															TABLE_NAME
														FROM 
															ALL_TABLES 
														WHERE 
															TABLE_NAME IN (     
																			SELECT
																				table_name
																			FROM
																				all_constraints
																			WHERE
																				owner in ( SELECT UPPER(REGEXP_SUBSTR(:VAR_OWNER_LIST, '[^,]+', 1, LEVEL)) SET_OWNER FROM DUAL CONNECT BY REGEXP_SUBSTR (:VAR_OWNER_LIST, '[^,]+', 1, LEVEL) IS NOT NULL )
																				AND constraint_type = 'P'
																				AND table_name IN (
																										SELECT 
																											DISTINCT SEGMENT_NAME
																										FROM
																											DBA_SEGMENTS
																										WHERE
																											OWNER in ( SELECT UPPER(REGEXP_SUBSTR(:VAR_OWNER_LIST, '[^,]+', 1, LEVEL)) SET_OWNER FROM DUAL CONNECT BY REGEXP_SUBSTR (:VAR_OWNER_LIST, '[^,]+', 1, LEVEL) IS NOT NULL )
																											AND SEGMENT_TYPE IN ('TABLE', 'TABLE PARTITION')
																											AND TABLESPACE_NAME NOT IN ('SYSTEM', 'SYSAUX', 'UNDOTBS02', 'UNDOTBS01', 'MGR_BD')
																											AND SEGMENT_NAME NOT LIKE '%SYS_%' 
																											AND SEGMENT_NAME NOT LIKE '%$%'
																											AND NOT REGEXP_LIKE(SEGMENT_NAME, '[0-9]')
																											AND NOT REGEXP_LIKE(SEGMENT_NAME, 'LOG')
																											AND NOT REGEXP_LIKE(SEGMENT_NAME, 'BACKUP')
																											AND NOT REGEXP_LIKE(SEGMENT_NAME, 'BKP')
																											AND NOT REGEXP_LIKE(SEGMENT_NAME, 'LIXO')
																											AND NOT REGEXP_LIKE(SEGMENT_NAME, 'TESTE')
																											AND NOT REGEXP_LIKE(SEGMENT_NAME, 'COPIA')
																										GROUP BY
																											SEGMENT_NAME
																									)                                                      
															)
															AND owner in ( SELECT UPPER(REGEXP_SUBSTR(:VAR_OWNER_LIST, '[^,]+', 1, LEVEL)) SET_OWNER FROM DUAL CONNECT BY REGEXP_SUBSTR (:VAR_OWNER_LIST, '[^,]+', 1, LEVEL) IS NOT NULL )
								)
							GROUP BY
								filha.owner,
								filha.table_name
								
						) TBL
						ORDER BY
							TBL.OWNER_TABLE
					)
				WHERE
					COLUMN_NAME IS NOT NULL
			),
			MOUNT_QUERY_EXPDP_PARAM_FILTER AS ( -- Monta o filtro limitando os registros cadastrados a partir de uma data X de todas as tabelas filhas que possuem colunas de DATE e TIMESTAMP possuem mais de X números de linhas registradas
				SELECT
					'query=' || RTRIM(REPLACE(xmlagg(XMLELEMENT(e,QUERY_TBL_EXPDP,',').EXTRACT('//text()') ).GetClobVal(), '&quot;', '"' ), ',')  QUERY_EXPDP
				FROM
					(
						SELECT
							TBL || ':' || '"where TRUNC('|| COLUMN_NAME ||') BETWEEN TRUNC(sysdate - ' || :VAR_QTD_DIAS || ') AND TRUNC(sysdate)"' QUERY_TBL_EXPDP		
						FROM
							LIST_TBLS
					)
			),
			MOUNT_TBL AS (
				
				SELECT
					'tables=' || RTRIM(xmlagg(XMLELEMENT(e,TBL,',').EXTRACT('//text()') ).GetClobVal(), ',') LIST_TBL
				FROM
				(
					SELECT
						DISTINCT
						(OWNER || '.' || TABLE_NAME) TBL
					FROM
					(
						SELECT 
							DISTINCT 
							TABLE_NAME TABLE_NAME,
							OWNER OWNER
						FROM 
							ALL_TABLES
						WHERE 
							OWNER IN ( SELECT UPPER(REGEXP_SUBSTR(:VAR_OWNER_LIST, '[^,]+', 1, LEVEL)) SET_OWNER FROM DUAL CONNECT BY REGEXP_SUBSTR (:VAR_OWNER_LIST, '[^,]+', 1, LEVEL) IS NOT NULL )
							AND table_name NOT LIKE '%$%'
							AND NOT REGEXP_LIKE(table_name, '[0-9]')
							AND NOT REGEXP_LIKE(table_name, 'BACKUP')
							AND NOT REGEXP_LIKE(table_name, 'BKP')
							AND NOT REGEXP_LIKE(table_name, 'LOG')
							AND NOT REGEXP_LIKE(table_name, 'LIXO')
							AND NOT REGEXP_LIKE(table_name, 'TESTE')
							AND NOT REGEXP_LIKE(table_name, 'COPIA')
							AND (OWNER || '.' || TABLE_NAME) NOT IN ( SELECT TBL FROM LIST_TBLS)
					)
					
					UNION ALL
					
					-- União das tabelas do filtro
					SELECT
						DISTINCT
						TBL
					FROM
						LIST_TBLS
				)    
			)	
		SELECT
			LIST_TBL,
			QUERY_EXPDP
		FROM
			MOUNT_TBL,
			MOUNT_QUERY_EXPDP_PARAM_FILTER
			
	);
    
	
	
    


    
---------------------------------------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------
----------- INICIANDO O PROCESSO DE IMPORT --------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------

	

* Após o backup ser finalizado, transferir via SCP os arquivos para o diretório "/backup/startup" no servidor de homologação.


## Criar a Base de Dados de Desenvolvimento ##

Database: DEVERP - 11G
Criar usuários: STRBACKUP - STARTUPADMIN

CREATE USER STARTUPADMIN IDENTIFIED BY ORACLE;
CREATE USER STRBACKUP IDENTIFIED BY ORACLE;

GRANT DBA TO STARTUPADMIN;
GRANT DBA TO STRBACKUP;

GRANT CONNECT, RESOURCE TO STARTUPADMIN;
GRANT CONNECT, RESOURCE TO STRBACKUP;


-- Usuários do Import
CREATE USER SIRIUS           IDENTIFIED BY SIRIUS;  
CREATE USER TELE             IDENTIFIED BY TELE;
CREATE USER LRESTOQUE        IDENTIFIED BY LRESTOQUE;
CREATE USER BDCOMUM          IDENTIFIED BY BDCOMUM;
CREATE USER INTEGRACAOMASTER IDENTIFIED BY INTEGRACAOMASTER;
CREATE USER INTBDCOMUM       IDENTIFIED BY INTBDCOMUM;
CREATE USER CEP              IDENTIFIED BY CEP;
CREATE USER ECONNECT         IDENTIFIED BY ECONNECT;
CREATE USER INTFISCAL        IDENTIFIED BY INTFISCAL;
CREATE USER MGR_BD           IDENTIFIED BY MGR_BD;
CREATE USER MKP              IDENTIFIED BY MKP;
CREATE USER TOTEM            IDENTIFIED BY TOTEM;
CREATE USER VTEX             IDENTIFIED BY VTEX;


-- Permissões para os OWNERS do Import
GRANT CREATE SESSION, RESOURCE TO SIRIUS;
GRANT UNLIMITED TABLESPACE TO SIRIUS;
GRANT DBA TO SIRIUS;

GRANT CREATE SESSION, RESOURCE TO TELE;
GRANT UNLIMITED TABLESPACE TO TELE;
GRANT DBA TO TELE;

GRANT CREATE SESSION, RESOURCE TO LRESTOQUE;
GRANT UNLIMITED TABLESPACE TO LRESTOQUE;
GRANT DBA TO LRESTOQUE;

GRANT CREATE SESSION, RESOURCE TO BDCOMUM;
GRANT UNLIMITED TABLESPACE TO BDCOMUM;
GRANT DBA TO BDCOMUM;

GRANT CREATE SESSION, RESOURCE TO INTEGRACAOMASTER;
GRANT UNLIMITED TABLESPACE TO INTEGRACAOMASTER;
GRANT DBA TO INTEGRACAOMASTER;

GRANT CREATE SESSION, RESOURCE TO INTBDCOMUM;
GRANT UNLIMITED TABLESPACE TO INTBDCOMUM;
GRANT DBA TO INTBDCOMUM;

GRANT CREATE SESSION, RESOURCE TO CEP;
GRANT UNLIMITED TABLESPACE TO CEP;
GRANT DBA TO CEP;

GRANT CREATE SESSION, RESOURCE TO ECONNECT;
GRANT UNLIMITED TABLESPACE TO ECONNECT;
GRANT DBA TO ECONNECT;

GRANT CREATE SESSION, RESOURCE TO INTFISCAL;
GRANT UNLIMITED TABLESPACE TO INTFISCAL;
GRANT DBA TO INTFISCAL;

GRANT CREATE SESSION, RESOURCE TO MGR_BD;
GRANT UNLIMITED TABLESPACE TO MGR_BD;
GRANT DBA TO MGR_BD;

GRANT CREATE SESSION, RESOURCE TO MKP;
GRANT UNLIMITED TABLESPACE TO MKP;
GRANT DBA TO MKP;

GRANT CREATE SESSION, RESOURCE TO TOTEM;
GRANT UNLIMITED TABLESPACE TO TOTEM;
GRANT DBA TO TOTEM;

GRANT CREATE SESSION, RESOURCE TO VTEX;
GRANT UNLIMITED TABLESPACE TO VTEX;
GRANT DBA TO VTEX;




## Início Importação ##


-- Antes de realizar o import, crie as seguintes tablespaces:

CREATE TABLESPACE APURACAO_DATA          DATAFILE '+DATAC2';
CREATE TABLESPACE APURACAO_IDX           DATAFILE '+DATAC2';
CREATE TABLESPACE BDCOMUM_DT             DATAFILE '+DATAC2';
CREATE TABLESPACE BDCOMUM_IX             DATAFILE '+DATAC2';
CREATE TABLESPACE CEP                    DATAFILE '+DATAC2';
CREATE TABLESPACE ESTOQUE_DT             DATAFILE '+DATAC2';
CREATE TABLESPACE INTBDCOMUM_DT          DATAFILE '+DATAC2';
CREATE TABLESPACE INTBDCOMUM_IX          DATAFILE '+DATAC2';
CREATE TABLESPACE INTEGRACAOJI           DATAFILE '+DATAC2';
CREATE TABLESPACE INTEGRACAOJI_IDX       DATAFILE '+DATAC2';
CREATE TABLESPACE INTEGRACAOMASTER       DATAFILE '+DATAC2';
CREATE TABLESPACE INTEGRACAOMASTER_IDX   DATAFILE '+DATAC2';
CREATE TABLESPACE INTFISCAL_DT           DATAFILE '+DATAC2';
CREATE TABLESPACE INTFISCAL_IX           DATAFILE '+DATAC2';
CREATE TABLESPACE LRDADOS                DATAFILE '+DATAC2';
CREATE TABLESPACE LRDADOS_RETBANCO01     DATAFILE '+DATAC2';
CREATE TABLESPACE LRDADOS_RETBANCO02     DATAFILE '+DATAC2';
CREATE TABLESPACE LRINDEXES              DATAFILE '+DATAC2';
CREATE TABLESPACE MDADADOS               DATAFILE '+DATAC2';
CREATE TABLESPACE MGR_BD                 DATAFILE '+DATAC2';
CREATE TABLESPACE SMARTADMIN             DATAFILE '+DATAC2';
CREATE TABLESPACE TELE                   DATAFILE '+DATAC2';
CREATE TABLESPACE TELE_IDX               DATAFILE '+DATAC2';
CREATE TABLESPACE TOTEM_DATA             DATAFILE '+DATAC2';
CREATE TABLESPACE VTEX_DATA              DATAFILE '+DATAC2';


-- O maior tablespace é o "LRDADOS", então é necessário adicionar mais 25 datafiles, se a porcentagem de exportação for de 10% de produção.
ALTER TABLESPACE LRDADOS ADD DATAFILE '+DATAC2' SIZE 10G AUTOEXTEND ON NEXT 5G MAXSIZE 31G;


-- Criação de ao menos 2 datafiles para os demais tablespaces
ALTER TABLESPACE APURACAO_DATA ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE APURACAO_DATA ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE APURACAO_IDX ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE APURACAO_IDX ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE BDCOMUM_DT ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE BDCOMUM_DT ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE CEP ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE CEP ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE ESTOQUE_DT ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE ESTOQUE_DT ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE INTBDCOMUM_DT ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE INTBDCOMUM_DT ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE INTBDCOMUM_IX ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE INTBDCOMUM_IX ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE INTEGRACAOJI ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE INTEGRACAOJI ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE INTEGRACAOJI_IDX ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE INTEGRACAOJI_IDX ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE INTEGRACAOMASTER ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE INTEGRACAOMASTER ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE INTEGRACAOMASTER_IDX ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE INTEGRACAOMASTER_IDX ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE INTFISCAL_DT ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE INTFISCAL_DT ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE LRDADOS_RETBANCO01 ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE LRDADOS_RETBANCO01 ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE LRDADOS_RETBANCO02 ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE LRDADOS_RETBANCO02 ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE LRINDEXES ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE LRINDEXES ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE MDADADOS ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE MDADADOS ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE MGR_BD ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE MGR_BD ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE TELE ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE TELE ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE TELE_IDX ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE TELE_IDX ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE TOTEM_DATA ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE TOTEM_DATA ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;

ALTER TABLESPACE VTEX_DATA ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;
ALTER TABLESPACE VTEX_DATA ADD DATAFILE '+DATAC2' SIZE 100M AUTOEXTEND ON NEXT 5G MAXSIZE 31G;





-- Criar o diretório de backup e a permissão para o usuário que irá efetuar o import
CREATE OR REPLACE DIRECTORY BACKUP_PARCIAL AS '/backup/startup/bkp_parcial/';
GRANT READ, WRITE ON DIRECTORY BACKUP_PARCIAL TO STRBACKUP;



-- Comando de import, observe que o "%U" no nome do arquivo "DMP" é usado como curinga para usar todos os arquivos de backup existentes.
impdp STRBACKUP/ORACLE DIRECTORY=BACKUP_PARCIAL DUMPFILE=expdp_wds_parcial_120719_13h26m34s_%U_bkp.dmp logfile=impdp_parcial_15072019.log



---------------------------------------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------
-------------------- ## Pós Importação ## ---------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------------------------------------------------------------------------------------------------------------------


* Após a importação com sucesso, realize os seguintes procedimentos:


-- Desabilitar todos os JOBS

-- Listar todos os JOBs broken, esses JOBS são desativados somente com o usuário SYS
SELECT 'EXEC dbms_ijob.broken(' || job || ',TRUE);' FROM dba_jobs WHERE broken = 'N';


-- Listar JOBS do SCHEDULER
SELECT 'EXEC dbms_scheduler.disable (''' || owner || '.' || job_name || ''');' 
FROM 
    dba_scheduler_jobs 
WHERE
    enabled = 'TRUE'
AND
    OWNER not in ('SYS', 'SYSTEM')
AND
    JOB_CREATOR not in ('SYS', 'SYSTEM')
ORDER BY owner, job_name;



-- Verificar se algum JOB do SCHEDULER está em execução:

-- Listar JOBS em execução
SELECT * FROM DBA_SCHEDULER_JOBS WHERE STATE = 'RUNNING';


-- Se algum JOB foi encontrado em execução, então finalize a SESSION que está executando ele e depois o desative
SELECT
    'ALTER SYSTEM KILL SESSION '''
    || SID
    || ','
    || SERIAL#
    || ',@'
    || INST_ID
    || ''' IMMEDIATE; -- KILL SESSION: '
    || USERNAME
    || ' - INSTÂNCIA '
    || INST_ID
    || ''
FROM
    GV$SESSION
WHERE
    ACTION = 'NOME_DO_JOB_EM_EXECUCAO';



-- Desabilitar Trigggers no Sirius
•	T_BL_ACCESS
•	T_REG_LOG_ACCESS
•	TG_BLOCK_BORDERO




* Atualizar os seguintes dados


-- Essa tabela deve possuir apenas uma linha, se não existir dados registrados nessa tabela, execute o comando INSERT, senão execute o comando de UPDATE
INSERT INTO SIRIUS.SISTEMA (CDSISTEMA, NMSISTEMA, STSISTEMA, AMBIENTE, CDNFEAMBIENTE) VALUES (1, 'Sirius', 1, 'Desenv. ' || to_date(sysdate,'dd/mm/yyyy'), 2);
 -- OU --
UPDATE SIRIUS.SISTEMA SET CDNFEAMBIENTE = 2 , AMBIENTE = 'Desenv. ' || to_date(sysdate,'dd/mm/yyyy');

COMMIT;


-- Execute o UPDATE sem WHERE mesmo.
UPDATE SIRIUS.NATUOPERACAO SET CDNFEAMBIENTE = 2; --- Teste de Emissao de NF de Saida, mandar para o ambiente Homologação NFE Sefaz
COMMIT;



-- Necessário desativar a trigger SIRIUS.TG_NOTAFISCALSAIDA_ISM_AIU e TG_NOTAFISCALSAIDA_ID para executar o UPDATE abaixo
UPDATE SIRIUS.NOTAFISCALSAIDA SET CDNFEAMBIENTE = 2 WHERE DTEMISSAO >= TO_DATE(sysdate - 30); -- Para o caso de teste de cancelamento de NF, cancelar em Amb. Homolgação NFE SEFAZ
COMMIT;



-- Execute o UPDATE sem WHERE mesmo.
UPDATE SIRIUS.CONTEMAIL SET TXEMAIL ='x';
COMMIT;



-- Por último, crie os usuários e execute os GRANTS abaixo, essa senha é padrão.

   
ALEXANDRE_CHICRALA      Senha: LHUHDL
LUCAS_ROSA              Senha: NBH9RX
MARCONI_BARROSO         Senha: AUHUJ4
MARCOS_MELO             Senha: ST5FQ2
PRINCE_SOUZA            Senha: XA24RY
RICARDO_SOUZA           Senha: K366A9
RAPHAEL_CORREA          Senha: HOBPNS
SAMUEL_CORREA           Senha: CODKAM


CREATE USER ALEXANDRE_CHICRALA IDENTIFIED BY LHUHDL;
CREATE USER LUCAS_ROSA IDENTIFIED BY NBH9RX;
CREATE USER MARCONI_BARROSO IDENTIFIED BY AUHUJ4;
CREATE USER MARCOS_MELO IDENTIFIED BY ST5FQ2;
CREATE USER PRINCE_SOUZA IDENTIFIED BY XA24RY;
CREATE USER RICARDO_SOUZA IDENTIFIED BY K366A9;
CREATE USER RAPHAEL_CORREA IDENTIFIED BY HOBPNS;
CREATE USER SAMUEL_CORREA IDENTIFIED BY CODKAM;

GRANT DBA TO ALEXANDRE_CHICRALA;
GRANT DBA TO LUCAS_ROSA;
GRANT DBA TO MARCONI_BARROSO;
GRANT DBA TO MARCOS_MELO;
GRANT DBA TO PRINCE_SOUZA;
GRANT DBA TO RICARDO_SOUZA;
GRANT DBA TO RAPHAEL_CORREA;
GRANT DBA TO SAMUEL_CORREA;


GRANT CONNECT, RESOURCE TO ALEXANDRE_CHICRALA;
GRANT CONNECT, RESOURCE TO LUCAS_ROSA;
GRANT CONNECT, RESOURCE TO MARCONI_BARROSO;
GRANT CONNECT, RESOURCE TO MARCOS_MELO;
GRANT CONNECT, RESOURCE TO PRINCE_SOUZA;
GRANT CONNECT, RESOURCE TO RICARDO_SOUZA;
GRANT CONNECT, RESOURCE TO RAPHAEL_CORREA;
GRANT CONNECT, RESOURCE TO SAMUEL_CORREA;





==== FIM DO PROCESSO DE IMPORTAÇÃO BASE DE DADOS DE DESENVOLVIMENTO ====

    
	
	
    
    
	
	