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
    """
    logger.info(f"Сигнал post_save для объявления {instance.id}: created={created}, is_active={instance.is_active}, sent_to_telegram={instance.sent_to_telegram}")
    
    # Отправляем только при создании нового объявления
    if not created:
        logger.debug(f"Объявление {instance.id} не новое, пропускаем отправку в Telegram")
        return
    
    # Проверяем, что объявление еще не было отправлено
    if instance.sent_to_telegram:
        logger.debug(f"Объявление {instance.id} уже отправлено в Telegram, пропускаем")
        return
    
    # Проверяем, что объявление активно
    if not instance.is_active:
        logger.info(f"Объявление {instance.id} неактивно, пропускаем отправку в Telegram")
        return
    
    # Проверяем, что Telegram включен
    if not settings.TELEGRAM_ENABLED:
        logger.info(f"Telegram отправка отключена в настройках для объявления {instance.id}")
        return
    
    logger.info(f"Начинаем отправку объявления {instance.id} в Telegram")
    
    try:
        # Отправляем в Telegram
        success, message_id, error = send_ad_to_telegram(instance)
        
        if success:
            # Обновляем объявление
            instance.sent_to_telegram = True
            if message_id:
                instance.telegram_message_id = message_id
            instance.save(update_fields=['sent_to_telegram', 'telegram_message_id'])
            logger.info(f"Объявление {instance.id} успешно отправлено в Telegram. Message ID: {message_id}")
        else:
            logger.error(f"Ошибка при отправке объявления {instance.id} в Telegram: {error}")
            
    except Exception as e:
        logger.error(f"Исключение при отправке объявления {instance.id} в Telegram: {str(e)}", exc_info=True)

