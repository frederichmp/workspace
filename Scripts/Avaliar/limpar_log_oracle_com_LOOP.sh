#!/bin/bash


DIR_DELETE=/u01/app/oracle/diag/rdbms/*/*/trace/
PATTERN_DELETE=*.tr*


for FILE in $DIR_DELETE/$PATTERN_DELETE
do
	rm $FILE
	echo $FILE
done

