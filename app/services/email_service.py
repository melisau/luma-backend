import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)

def send_email(to: str, subject: str, body: str) -> bool:
    settings = get_settings()
    if settings.email_backend == "disabled": return False
    if settings.email_backend == "console":
        logger.info("Email to=%s subject=%s body=%s", to, subject, body)
        return True
    if settings.email_backend != "smtp" or not settings.smtp_host:
        raise RuntimeError("SMTP e-posta yapılandırması eksik.")
    message=EmailMessage();message["From"]=settings.email_from;message["To"]=to;message["Subject"]=subject;message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls: smtp.starttls()
        if settings.smtp_username: smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)
    return True
