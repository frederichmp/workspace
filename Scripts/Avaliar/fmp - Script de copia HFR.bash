#!/bin/bash

i=$1

#LOGICA

PROC=`ps -ef | grep -v grep | grep "/backup/script_copia_rsync.sh $i" | wc -l`
FILE=`ls -l "/backup/.cp_f_$i.lck" | wc -l` 2> /dev/null
TFITA=`echo $i | grep FITA | wc -l`
TODA=`echo $i | grep ODA | wc -l`

if [ $PROC -eq 0 ] && [ $FILE -eq 0 ]; then
        echo "EXECUTA NORMALMENTE"

        /backup/script_copia_rsync.sh $i

elif [ $PROC -eq 0 ] && [ $FILE -eq 1 ]; then
        echo "EXECUCAO FINALIZADA CONTROL+C"
        rm -f /backup/.cp_f_$i.lck

        /backup/script_copia_rsync.sh $i

elif [ $PROC -eq 1 ] && [ $FILE -eq 0 ]; then
        echo "FALHA"
        exit 0

elif [ $PROC -eq 1 ] && [ $FILE -eq 1 ]; then
        echo "EM EXECUCAO"
        exit 0
fi