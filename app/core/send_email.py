from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.core.config import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,  
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,  
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS, 
    USE_CREDENTIALS=True,  # Ensures credentials are used for authentication
    TEMPLATE_FOLDER='templates'  # Path to email templates
)


async def send_email_async(email_to: str, body: dict):
    message = MessageSchema(
        subject="Registered please verify with OTP.",
        recipients=[email_to],
        body=body,
        subtype='html',
    )

    fm = FastMail(conf)
    
    await fm.send_message(message, template_name='email.html')


def send_email_background(background_tasks: BackgroundTasks, subject: str, email_to: str, body: dict):
    message = MessageSchema(
        subject=subject,
        recipients=[email_to],
        body=body,
        subtype='html',
    )
    fm = FastMail(conf)
    background_tasks.add_task(
        fm.send_message, message, template_name='email.html')
