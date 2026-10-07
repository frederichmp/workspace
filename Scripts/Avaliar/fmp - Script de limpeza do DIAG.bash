# LIMPAR DIAG SCRIPT

#ENTRA NO DIRETORIO
for I in `ls -1d */`
do
echo "ENTRANDO NO DIRETORIO $I 1";
cd $I;
#ls -1d */;
echo "EXECUTANDO LOOP DENTRO DO DIRETORIO $I";
for II in `ls -1d */`
do
echo "ENTRANDO DENTRO DO DIRETORIO $II DENTRO DO LOOP";
cd $II;
echo "LISTANDO CONTEUDO DO DIRETORIO $II LOOP";
ls -1d */;
#echo "EXECUTANDO LIMPEZA DIRETORIO TRACE FIND +0 $II"
#find trace/*tr* -mtime +0 -exec rm -f {} \;
#echo "EXECUTANDO LIMPEZA DIRETORIO CDUMP RM -RF $II" 
#rm -rf trace/cdump*
#echo "EXECUTANDO LIMPEZA DIRETORIO ALERT RM -F LOG_* $II" 
#rm -f alert/log_*
echo "ECUTANDO LIMPEZA DIRETORIO TRACE RM -F TRACE/*TR* $II"
rm -f trace/*tr*
#du -sch */
echo "SAINDO DO DIRETORIO $II LOOP";
cd ..;
done
echo "SAINDO DO DIRETORIO $I 1";
cd ..;
done


/u01/aplic/copia/st_backup_copy.sh CUSTOM lastdays_1 'dw_param_copy_backup.par prdnew_param_copy_backup.par'
