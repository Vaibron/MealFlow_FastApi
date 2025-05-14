import asyncio
import smtplib
from email.mime.text import MIMEText
from core.config import config
import logging

logger = logging.getLogger(__name__)

async def send_email(to_email: str, subject: str, body: str):
    """Асинхронная отправка email через SMTP."""
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to_email

    loop = asyncio.get_event_loop()
    try:
        # Выполняем синхронную отправку в асинхронном контексте
        await loop.run_in_executor(None, lambda: send_smtp_email(msg))
        logger.info(f"Письмо успешно отправлено на {to_email}")
    except Exception as e:
        logger.error(f"Ошибка отправки письма на {to_email}: {str(e)}")
        raise

def send_smtp_email(msg: MIMEText):
    """Синхронная функция для отправки письма через SMTP."""
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls()  # Включаем TLS
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(msg)