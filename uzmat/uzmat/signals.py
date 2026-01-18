"""
Django signals для автоматической отправки объявлений в Telegram
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from uzmat.models import Advertisement
from uzmat.utils.telegram_service import send_ad_to_telegram
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Advertisement)
def send_ad_to_telegram_on_create(sender, instance, created, **kwargs):
    """
    Автоматически отправляет объявление в Telegram при создании
    ВАЖНО: Отправка происходит только из views.py после сохранения всех изображений
    Этот сигнал отключен, чтобы избежать отправки до загрузки изображений
    """
    # ОТКЛЮЧЕНО: Отправка теперь происходит из views.py после сохранения всех изображений
    # Это гарантирует, что изображения уже загружены перед отправкой
    return
    
    # Старый код (закомментирован для справки):
    # logger.info(f"Сигнал post_save для объявления {instance.id}: created={created}, is_active={instance.is_active}, sent_to_telegram={instance.sent_to_telegram}")
    # if not created:
    #     return
    # if instance.sent_to_telegram:
    #     return
    # if not instance.is_active:
    #     return
    # if not settings.TELEGRAM_ENABLED:
    #     return
    # ... остальной код

