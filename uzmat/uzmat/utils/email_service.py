"""
Утилита для отправки email через SendGrid
"""
import logging
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

logger = logging.getLogger(__name__)


def send_email_simple(to_email, subject, message, html_message=None):
    """
    Простая отправка email через Django (использует SendGrid SMTP)
    
    Args:
        to_email: Email получателя или список email адресов
        subject: Тема письма
        message: Текст письма (plain text)
        html_message: HTML версия письма (опционально)
    
    Returns:
        bool: True если письмо отправлено успешно, False в противном случае
    """
    try:
        if isinstance(to_email, str):
            to_email = [to_email]
        
        send_mail(
            subject=subject,
            message=message,
            from_email=f"{settings.DEFAULT_FROM_NAME} <{settings.DEFAULT_FROM_EMAIL}>",
            recipient_list=to_email,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Email успешно отправлен на {to_email}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке email на {to_email}: {str(e)}")
        return False


def send_email_sendgrid_api(to_email, subject, html_content, text_content=None):
    """
    Отправка email через SendGrid API (более продвинутый способ)
    
    Args:
        to_email: Email получателя или список email адресов
        subject: Тема письма
        html_content: HTML содержимое письма
        text_content: Текстовая версия письма (опционально)
    
    Returns:
        bool: True если письмо отправлено успешно, False в противном случае
    """
    if not settings.SENDGRID_API_KEY:
        logger.error("SENDGRID_API_KEY не настроен в settings.py")
        return False
    
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        
        if isinstance(to_email, str):
            to_email = [to_email]
        
        for email in to_email:
            message = Mail(
                from_email=Email(settings.DEFAULT_FROM_EMAIL, settings.DEFAULT_FROM_NAME),
                to_emails=To(email),
                subject=subject,
                html_content=html_content,
            )
            
            if text_content:
                message.plain_text_content = Content("text/plain", text_content)
            
            response = sg.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email успешно отправлен на {email} через SendGrid API")
            else:
                logger.warning(f"SendGrid вернул статус {response.status_code} для {email}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке email через SendGrid API: {str(e)}")
        return False


def send_email_template(to_email, subject, template_name, context, text_template=None):
    """
    Отправка email с использованием Django шаблонов
    
    Args:
        to_email: Email получателя или список email адресов
        subject: Тема письма
        template_name: Имя HTML шаблона (например, 'uzmat/emails/welcome.html')
        context: Словарь с данными для шаблона
        text_template: Имя текстового шаблона (опционально)
    
    Returns:
        bool: True если письмо отправлено успешно, False в противном случае
    """
    try:
        # Рендерим HTML шаблон
        html_content = render_to_string(template_name, context)
        
        # Рендерим текстовый шаблон, если указан
        text_content = None
        if text_template:
            text_content = render_to_string(text_template, context)
        
        # Отправляем через простой метод
        return send_email_simple(to_email, subject, text_content or '', html_content)
    except Exception as e:
        logger.error(f"Ошибка при отправке email с шаблоном: {str(e)}")
        return False


def send_welcome_email(user):
    """
    Пример: отправка приветственного письма новому пользователю
    
    Args:
        user: Объект User
    """
    if not user.email:
        logger.warning(f"У пользователя {user.username} нет email адреса")
        return False
    
    subject = 'Добро пожаловать в Uzmat!'
    context = {
        'user': user,
        'username': user.username,
    }
    
    # Простой вариант без шаблона
    html_message = f"""
    <html>
    <body>
        <h1>Добро пожаловать, {user.username}!</h1>
        <p>Спасибо за регистрацию в Uzmat.</p>
        <p>Мы рады видеть вас в нашем сообществе!</p>
    </body>
    </html>
    """
    
    text_message = f"Добро пожаловать, {user.username}!\n\nСпасибо за регистрацию в Uzmat."
    
    return send_email_simple(user.email, subject, text_message, html_message)


def send_notification_email(user, notification_text):
    """
    Пример: отправка уведомления пользователю
    
    Args:
        user: Объект User
        notification_text: Текст уведомления
    """
    if not user.email:
        return False
    
    subject = 'Уведомление от Uzmat'
    html_message = f"""
    <html>
    <body>
        <h2>Уведомление</h2>
        <p>{notification_text}</p>
    </body>
    </html>
    """
    
    return send_email_simple(user.email, subject, notification_text, html_message)





