"""
Módulo de Notificação de Alertas Críticos via SMTP (Gmail App Password).
Integrado à barreira de segurança HITL (Human-in-the-Loop) para governança de intervenções DBA.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Tuple
from dotenv import load_dotenv

load_dotenv()


def enviar_alerta_email(assunto: str, corpo: str) -> Tuple[bool, str]:
    """Envia um e-mail de alerta utilizando SMTP do Gmail (TLS na porta 587)."""
    load_dotenv(override=True)
    remetente = os.getenv("EMAIL_REMETENTE", "").strip()
    # Remove espaços caso a senha de app de 16 dígitos tenha sido colada com espaços
    senha = os.getenv("EMAIL_SENHA_APP", "").replace(" ", "").strip()
    destinatario = os.getenv("EMAIL_DESTINATARIO", "").strip()

    if not all([remetente, senha, destinatario]) or "seu_email" in remetente:
        return False, "Credenciais de e-mail ausentes ou não configuradas no .env."

    try:
        msg = MIMEMultipart()
        msg["From"] = remetente
        msg["To"] = destinatario
        msg["Subject"] = assunto

        msg.attach(MIMEText(corpo, "plain", "utf-8"))

        # Conexão segura com o Gmail (TLS)
        servidor = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        servidor.starttls()
        servidor.login(remetente, senha)
        servidor.send_message(msg)
        servidor.quit()

        return True, "E-mail enviado com sucesso."
    except Exception as e:
        return False, f"Falha ao enviar e-mail: {str(e)}"


if __name__ == "__main__":
    print("Testando envio de alerta por e-mail...")
    ok, mensagem = enviar_alerta_email(
        assunto="[AGENTE DBA] Teste de Configuração SMTP",
        corpo="Este é um teste automático do módulo notificador.py do Personal Agent.",
    )
    print(f"Sucesso: {ok} | Mensagem: {mensagem}")
