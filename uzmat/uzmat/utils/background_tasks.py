"""
Утилиты для выполнения фоновых задач асинхронно
"""
import threading
from django.utils import timezone
from django.core.cache import cache


def run_in_background(func, *args, **kwargs):
    """
    Запускает функцию в фоновом потоке
    Не блокирует основной запрос
    """
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread


def bump_ads_async():
    """
    Асинхронное автоподнятие объявлений
    Выполняется в фоновом потоке, не блокирует запрос
    """
    try:
        # Импортируем здесь, чтобы избежать циклических импортов
        from ..models import Advertisement
        from django.db.models import Q
        
        now = timezone.now()
        bump_candidates = list(
            Advertisement.objects.filter(
                is_active=True
            ).filter(
                Q(last_bumped_at__isnull=True) | Q(last_bumped_at__lte=now - timezone.timedelta(hours=3))
            ).values_list('id', flat=True)[:500]
        )
        if bump_candidates:
            # Используем bulk update для производительности
            Advertisement.objects.filter(id__in=bump_candidates).update(last_bumped_at=now)
    except Exception as e:
        # Логируем ошибку, но не прерываем работу сайта
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при автоподнятии объявлений: {e}")


def increment_ad_views_async(ad_id, user_ip):
    """
    Асинхронное увеличение счетчика просмотров
    Выполняется в фоновом потоке
    """
    try:
        # Импортируем здесь, чтобы избежать циклических импортов
        from ..models import Advertisement
        from django.db.models import F
        
        # Используем кэш для предотвращения частых обновлений от одного IP
        view_cache_key = f'ad_view_{ad_id}_{user_ip}'
        if not cache.get(view_cache_key):
            # Атомарное обновление через F() - быстрее и безопаснее
            Advertisement.objects.filter(id=ad_id).update(views_count=F('views_count') + 1)
            # Кэшируем на 5 минут, чтобы один IP не накручивал счетчик
            cache.set(view_cache_key, True, 300)
    except Exception as e:
        # Логируем ошибку, но не прерываем работу сайта
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при увеличении счетчика просмотров: {e}")


def update_unread_count_cache_async(user_id, unread_count):
    """
    Асинхронное обновление кэша непрочитанных сообщений
    """
    try:
        cache_key = f'unread_count_{user_id}'
        cache.set(cache_key, unread_count, 30)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при обновлении кэша непрочитанных сообщений: {e}")


def send_notification_async(user_id, message, thread_id=None):
    """
    Асинхронная отправка уведомлений (можно расширить для email/push)
    """
    try:
        # Здесь можно добавить отправку email, push-уведомлений и т.д.
        # Пока просто логируем
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Уведомление отправлено пользователю {user_id}: {message}")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при отправке уведомления: {e}")


def send_ad_to_telegram_async(ad_id):
    """
    Асинхронная отправка объявления в Telegram канал
    Выполняется в фоновом потоке, не блокирует основной запрос
    """
    try:
        # Импортируем здесь, чтобы избежать циклических импортов
        from ..models import Advertisement
        from .telegram_service import send_ad_to_telegram
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"🔄 [ASYNC] Начинаем асинхронную отправку объявления {ad_id} в Telegram")
        
        # Получаем объявление из БД
        try:
            ad = Advertisement.objects.get(id=ad_id)
        except Advertisement.DoesNotExist:
            logger.error(f"❌ [ASYNC] Объявление {ad_id} не найдено в БД")
            return
        
        # Обновляем объект, чтобы получить актуальные изображения
        ad.refresh_from_db()
        logger.info(f"📸 [ASYNC] Объявление {ad_id}: images.exists()={ad.images.exists()}, image={bool(ad.image)}")
        
        # Отправляем в Telegram
        success, message_id, error = send_ad_to_telegram(ad)
        
        if success:
            # Обновляем объявление
            ad.sent_to_telegram = True
            if message_id:
                ad.telegram_message_id = message_id
            ad.save(update_fields=['sent_to_telegram', 'telegram_message_id'])
            logger.info(f"✅ [ASYNC] Объявление {ad_id} успешно отправлено в Telegram. Message ID: {message_id}")
        else:
            logger.error(f"❌ [ASYNC] Ошибка при отправке объявления {ad_id} в Telegram: {error}")
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ [ASYNC] Исключение при отправке объявления {ad_id} в Telegram: {str(e)}", exc_info=True)

