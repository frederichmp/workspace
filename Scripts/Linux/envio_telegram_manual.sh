

# Como usar
# Chamar a function sentTelegram 'minha mensagem entre aspas simples'
# Copie e cole todo o código. Altere o valor da mensagem de acordo com o uso


# Existe necessario se o mandar executar depois do sqlplus, desta forma sai do sqlplus
exit;

# Realiza o envio da mensagem via telegram
function sentTelegram()
{

	# Informações do token
	LINE_BREAK='%0A'
	TELEGRAM_TOKEN='1342896033:AAEkL8VaFtRKNKcp8OOr33YT-bNjDtK72kE'
	
	TELEGRAM_CHAT_ID=1001245962399
		
		
	# Mensagem a ser enviada pelo telegram, 
	MSG="$1"
	MSG="$(echo -e "${MSG}" | sed "s, ,"${LINE_BREAK}",g")"
	

	# URL do chat do telegram
	URL_SEND="https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage?chat_id=-${TELEGRAM_CHAT_ID}&parse_mode=HTML&text="
	
	
	# Pega a data e hora atual
	EXECUTE_DATE="date +%d/%m/%Y_%H:%M:%S"
	DATE_ALERT=$(LANG=en_us_88591;${EXECUTE_DATE})


	# Inicio criação mensagem de alerta
	MSG_HEADER="<i>======${DATE_ALERT}=======</i>"${LINE_BREAK}
	MSG_FOOTER="<i>=============FIM=============</i>"
	
	echo ${URL_SEND}${MSG_HEADER}${MSG}${LINE_BREAK}${MSG_FOOTER}
	
	# Chamada do telegram
	curl ${URL_SEND}${MSG_HEADER}${MSG}${LINE_BREAK}${MSG_FOOTER}

}


sentTelegram 'minha mensagem entre aspas simples'