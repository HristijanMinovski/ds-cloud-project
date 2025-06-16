import aiosmtplib
from celery import Celery
import os
from email.message import EmailMessage
from dotenv import load_dotenv
import asyncio

# funkcii za prakjanje na mejl

load_dotenv()
celery_app = Celery(
    "tasks",
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

celery_app.conf.task_routes = {
    "tasks.send_email_async": {"queue": "emails"},
}

SMTP_HOST = os.getenv("SMTP_HOST", "sandbox.smtp.mailtrap.io")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("MAILTRAP_USER")
SMTP_PASS = os.getenv("MAILTRAP_PASS")


@celery_app.task(name="tasks.send_email_async")
def send_email_async(to_email, subject, body):
    async def actually_send_email():
        message = EmailMessage()
        message["From"] = "jobscheduler@mailtrap.io"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        await aiosmtplib.send(
            message,
            hostname="sandbox.smtp.mailtrap.io",
            port=587,
            start_tls=True,

            validate_certs=False,
        )
    asyncio.run(actually_send_email())