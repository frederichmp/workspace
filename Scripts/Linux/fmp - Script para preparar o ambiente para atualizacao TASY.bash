#!/bin/bash

export ORACLE_SID=TASYPRD
export ORACLE_BASE=/u01/app/oracle
export ORACLE_HOME=/u01/app/oracle/product/11.2.0.4/dbhome_1

case $1 in

inicio) echo "PREPARANDO O ORACLE PARA ATUALIZACAO DO SISTEMA"
$ORACLE_HOME/bin/sqlplus / as sysdba <<! 2> /dev/null
shutdown immediate;
startup mount;
alter system set job_queue_processes=0;
alter database open;
!
echo "BASE PREPARADA PARA ATUALIZACAO DO SISTEMA"
;;

fim) echo "PREPARANDO O ORACLE PARA O AMBIENTE DE PRODUCAO"
$ORACLE_HOME/bin/sqlplus / as sysdba <<! 2> /dev/null
shutdown immediate;
startup mount;
alter system set job_queue_processes=10;
alter database open;
!
echo "BASE PRONTA PARA PRODUCAO"
;;

*) echo "Use os pametros [\"inicio\" - para iniciar a preparacao do banco | \"fim\" - para finalizar a operacao de atualizacao]"
;;

esac