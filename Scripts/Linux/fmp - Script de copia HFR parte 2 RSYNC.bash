#!/bin/bash

i=$1;

#FUNCOES
f_prog_fita (){
case $i in
FITA_FULL)
;;

FITA_INC0)
touch /backup/.cp_f_$i.lck
sshpass -p startup2019 /usr/bin/rsync --progress --delete-before -vtrapolgu /backup/prdmv/data/*level0* fred.startupnet@10.50.2.25:/orabkp/prdmv/data/ > /backup/log_copia_fita_inc0_`date +%d%m%y_%H%M`.log
find /backup/log_copia_fita_inc0* -mtime +7 -exec rm -f {} \;
rm -f /backup/.cp_f_$i.lck
;;

FITA_INC1)
touch /backup/.cp_f_$i.lck
sshpass -p startup2019 /usr/bin/rsync --progress --delete-before -vtrapolgu /backup/prdmv/data/*level1* fred.startupnet@10.50.2.25:/orabkp/prdmv/data/ > /backup/log_copia_fita_inc1_`date +%d%m%y_%H%M`.log
find /backup/log_copia_fita_inc1* -mtime +7 -exec rm -f {} \;
rm -f /backup/.cp_f_$i.lck
;;

FITA_ARCH)
touch /backup/.cp_f_$i.lck
sshpass -p startup2019 /usr/bin/rsync --progress --delete-before -vtrapolgu /backup/prdmv/arch fred.startupnet@10.50.2.25:/orabkp/prdmv/ > /backup/log_copia_fita_arch_`date +%d%m%y_%H%M`.log
find /backup/log_copia_fita_arch* -mtime +7 -exec rm -f {} \;
rm -f /backup/.cp_f_$i.lck
;;

FITA_CTL)
touch /backup/.cp_f_$i.lck
sshpass -p startup2019 /usr/bin/rsync --progress --delete-before -vtrapolgu /backup/prdmv/ctl fred.startupnet@10.50.2.25:/orabkp/prdmv/ > /backup/log_copia_fita_ctl_`date +%d%m%y_%H%M`.log
find /backup/log_copia_fita_ctl* -mtime +7 -exec rm -f {} \;
rm -f /backup/.cp_f_$i.lck
;;

esac
}

f_prog_oda (){
case $i in
ODA_FULL)
;;

ODA_INC0)
touch /backup/.cp_f_$i.lck
sshpass -p "PassWord19#_" /usr/bin/rsync --progress --delete-before -vtrapolgu /backup/prdmv/data/*level0* root@172.17.200.161:/backup_aix/prdmv/data/ > /backup/log_copia_oda_inc0_`date +%d%m%y_%H%M`.log
find /backup/log_copia_oda_inc0* -mtime +7 -exec rm -f {} \;
rm -f /backup/.cp_f_$i.lck
;;

ODA_INC1)
touch /backup/.cp_f_$i.lck
sshpass -p "PassWord19#_" /usr/bin/rsync --progress --delete-before -vtrapolgu /backup/prdmv/data/*level1* root@172.17.200.161:/backup_aix/prdmv/data/ > /backup/log_copia_oda_inc1_`date +%d%m%y_%H%M`.log
find /backup/log_copia_oda_inc1* -mtime +7 -exec rm -f {} \;
rm -f /backup/.cp_f_$i.lck
;;

ODA_ARCH)
touch /backup/.cp_f_$i.lck
sshpass -p "PassWord19#_" /usr/bin/rsync --progress --delete-before -vtrapolgu /backup/prdmv/arch root@172.17.200.161:/backup_aix/prdmv/ > /backup/log_copia_oda_arch_`date +%d%m%y_%H%M`.log
find /backup/log_copia_oda_arch* -mtime +7 -exec rm -f {} \;
rm -f /backup/.cp_f_$i.lck
;;

ODA_CTL)
touch /backup/.cp_f_$i.lck
sshpass -p "PassWord19#_" /usr/bin/rsync --progress --delete-before -vtrapolgu /backup/prdmv/ctl root@172.17.200.161:/backup_aix/prdmv/ > /backup/log_copia_oda_ctl_`date +%d%m%y_%H%M`.log
find /backup/log_copia_oda_ctl* -mtime +7 -exec rm -f {} \;
rm -f /backup/.cp_f_$i.lck
;;

esac
}

#LOGICA


TFITA=`echo $i | grep FITA | wc -l`
TODA=`echo $i | grep ODA | wc -l`


	if [ $TFITA -eq 1 ];then	
	f_prog_fita
	echo "EXECUTA NORMALMENTE FITA"

	fi
	
	if [ $TODA -eq 1 ];then	
	f_prog_oda
	echo "EXECUTA NORMALMENTE ODA"

	fi
	
