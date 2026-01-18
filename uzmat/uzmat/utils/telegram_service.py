"""
Утилита для отправки объявлений в Telegram канал
"""
import os
import requests
import logging
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


def send_ad_to_telegram(advertisement):
    """
    Отправляет объявление в Telegram канал
    
    Args:
        advertisement: Экземпляр модели Advertisement
        
    Returns:
        tuple: (success: bool, message_id: str or None, error: str or None)
    """
    logger.info(f"=== НАЧАЛО ОТПРАВКИ ОБЪЯВЛЕНИЯ {advertisement.id} В TELEGRAM ===")
    logger.info(f"TELEGRAM_ENABLED={settings.TELEGRAM_ENABLED}")
    logger.info(f"TELEGRAM_BOT_TOKEN={'установлен' if settings.TELEGRAM_BOT_TOKEN else 'НЕ установлен'}")
    logger.info(f"TELEGRAM_CHANNEL_ID={settings.TELEGRAM_CHANNEL_ID}")
    
    if not settings.TELEGRAM_ENABLED:
        logger.warning("Telegram отправка отключена в настройках")
        return False, None, "Telegram отправка отключена"
    
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return False, None, "TELEGRAM_BOT_TOKEN не настроен"
    
    if not settings.TELEGRAM_CHANNEL_ID:
        logger.error("TELEGRAM_CHANNEL_ID не настроен")
        return False, None, "TELEGRAM_CHANNEL_ID не настроен"
    
    try:
        # Получаем базовый URL сайта из настроек
        base_url = getattr(settings, 'SITE_URL', 'https://uzmat.uz')
        if not base_url.startswith('http'):
            base_url = f"https://{base_url}"
        
        # Формируем ссылку на объявление
        ad_url = f"{base_url}{reverse('uzmat:ad_detail', kwargs={'slug': advertisement.slug})}"
        
        # Формируем текст сообщения
        message_text = format_ad_message(advertisement, ad_url)
        
        # Отправляем сообщение
        has_images = advertisement.images.exists() or advertisement.image
        logger.info(f"Объявление {advertisement.id}: has_images={has_images}, images.exists()={advertisement.images.exists()}, image={bool(advertisement.image)}")
        
        if has_images:
            # Если есть изображение, отправляем с фото
            logger.info(f"Пытаемся отправить объявление {advertisement.id} с фото")
            return send_photo_message(advertisement, message_text)
        else:
            # Если нет изображения, отправляем только текст
            logger.info(f"Объявление {advertisement.id} без изображений, отправляем только текст")
            return send_text_message(message_text)
            
    except Exception as e:
        logger.error(f"Ошибка при отправке объявления в Telegram: {str(e)}", exc_info=True)
        return False, None, str(e)


def format_ad_message(advertisement, ad_url):
    """
    Форматирует текст сообщения для Telegram
    
    Args:
        advertisement: Экземпляр модели Advertisement
        ad_url: URL объявления
        
    Returns:
        str: Отформатированный текст сообщения
    """
    # Тип объявления
    ad_type_map = {
        'rent': '🔄 Аренда',
        'sale': '💰 Продажа',
        'service': '🔧 Услуги',
        'parts': '⚙️ Запчасти',
    }
    ad_type_emoji = ad_type_map.get(advertisement.ad_type, '📋')
    
    # Формируем заголовок
    lines = [
        f"{ad_type_emoji} <b>{advertisement.title}</b>",
        "",
    ]
    
    # Цена
    price_display = advertisement.get_price_display()
    if price_display and price_display != "Договорная":
        lines.append(f"💵 <b>Цена:</b> {price_display}")
    
    # Характеристики техники
    if advertisement.equipment_type:
        lines.append(f"🚜 <b>Тип:</b> {advertisement.equipment_type}")
    
    if advertisement.brand:
        brand_line = f"🏷️ <b>Марка:</b> {advertisement.brand}"
        if advertisement.model:
            brand_line += f" {advertisement.model}"
        lines.append(brand_line)
    
    if advertisement.year:
        lines.append(f"📅 <b>Год:</b> {advertisement.year}")
    
    if advertisement.condition:
        condition_map = {
            'new': 'Новое',
            'excellent': 'Отличное',
            'good': 'Хорошее',
            'satisfactory': 'Удовлетворительное',
        }
        condition_text = condition_map.get(advertisement.condition, advertisement.condition)
        lines.append(f"✨ <b>Состояние:</b> {condition_text}")
    
    # Для аренды
    if advertisement.ad_type == 'rent' and advertisement.with_operator:
        lines.append("👷 <b>С оператором</b>")
    
    # Местоположение
    location = f"📍 <b>{advertisement.city}</b>"
    if advertisement.country:
        country_map = {
            'kz': '🇰🇿',
            'uz': '🇺🇿',
            'ru': '🇷🇺',
        }
        country_emoji = country_map.get(advertisement.country, '')
        if country_emoji:
            location = f"{country_emoji} {location}"
    lines.append(location)
    
    # Описание (обрезаем до 300 символов)
    if advertisement.description:
        description = advertisement.description.strip()
        if len(description) > 300:
            description = description[:297] + "..."
        lines.append("")
        lines.append(description)
    
    # Ссылка на объявление
    lines.append("")
    lines.append(f"🔗 <a href='{ad_url}'>Смотреть объявление</a>")
    
    return "\n".join(lines)


def send_text_message(message_text):
    """
    Отправляет текстовое сообщение в Telegram канал
    
    Args:
        message_text: Текст сообщения (HTML форматирование)
        
    Returns:
        tuple: (success: bool, message_id: str or None, error: str or None)
    """
    bot_token = settings.TELEGRAM_BOT_TOKEN
    channel_id = settings.TELEGRAM_CHANNEL_ID
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        'chat_id': channel_id,
        'text': message_text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False,
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get('ok'):
            message_id = str(result['result']['message_id'])
            logger.info(f"Сообщение успешно отправлено в Telegram. Message ID: {message_id}")
            return True, message_id, None
        else:
            error = result.get('description', 'Unknown error')
            logger.error(f"Ошибка при отправке сообщения в Telegram: {error}")
            return False, None, error
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при отправке в Telegram: {str(e)}")
        return False, None, str(e)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке в Telegram: {str(e)}", exc_info=True)
        return False, None, str(e)


def send_photo_message(advertisement, message_text):
    """
    Отправляет сообщение с фото в Telegram канал
    
    Args:
        advertisement: Экземпляр модели Advertisement
        message_text: Текст сообщения (HTML форматирование)
        
    Returns:
        tuple: (success: bool, message_id: str or None, error: str or None)
    """
    bot_token = settings.TELEGRAM_BOT_TOKEN
    channel_id = settings.TELEGRAM_CHANNEL_ID
    
    # Получаем главное изображение
    image_file = None
    if advertisement.images.exists():
        # Сначала ищем главное изображение
        main_image = advertisement.images.filter(is_main=True).first()
        if not main_image:
            # Если главного нет, берем первое изображение
            main_image = advertisement.images.first()
        if main_image:
            image_file = main_image.image
            logger.info(f"Найдено изображение из advertisement.images: {image_file.name if image_file else 'None'}")
    elif advertisement.image:
        # Используем старое поле image, если нет связанных изображений
        image_file = advertisement.image
        logger.info(f"Найдено изображение из advertisement.image: {image_file.name if image_file else 'None'}")
    
    if not image_file:
        # Если изображение не найдено, отправляем только текст
        logger.warning(f"Изображение не найдено для объявления {advertisement.id}, отправляем только текст")
        return send_text_message(message_text)
    
    logger.info(f"Найдено изображение для отправки: {image_file.name}")
    
    # ВАЖНО: Сначала пробуем отправить файл напрямую (наиболее надежный метод)
    # Это работает только если файл доступен локально
    file_result = send_photo_as_file(advertisement, message_text, image_file)
    if file_result[0]:  # Если успешно
        logger.info(f"Фото успешно отправлено как файл для объявления {advertisement.id}")
        return file_result
    
    # Если не получилось отправить файл, пробуем по URL
    logger.warning(f"Отправка файла не удалась для объявления {advertisement.id}, пробуем отправить по URL. Ошибка: {file_result[2]}")
    
    try:
        # Получаем URL изображения
        image_url = image_file.url
        logger.info(f"Исходный URL изображения: {image_url}")
        
        # Если URL относительный, формируем полный URL
        if not image_url.startswith('http'):
            # Получаем базовый URL сайта
            base_url = getattr(settings, 'SITE_URL', 'https://uzmat.uz')
            
            # Для локальной разработки используем localhost
            if settings.DEBUG:
                base_url = 'http://127.0.0.1:8000'
                logger.info(f"Используется локальный URL для разработки: {base_url}")
            elif not base_url.startswith('http'):
                base_url = f"https://{base_url}"
            
            logger.info(f"Базовый URL для изображения: {base_url}")
            
            # Получаем MEDIA_URL из настроек
            media_url = getattr(settings, 'MEDIA_URL', '/media/')
            
            # Если image_url уже содержит /media/, используем его как есть
            # Если нет, добавляем MEDIA_URL
            if image_url.startswith('/media/'):
                # URL уже правильный, просто добавляем базовый URL
                image_url = f"{base_url}{image_url}"
            elif image_url.startswith('media/'):
                # URL без начального слэша
                image_url = f"{base_url}/{image_url}"
            else:
                # Формируем полный путь с MEDIA_URL
                if not media_url.startswith('/'):
                    media_url = '/' + media_url
                if image_url.startswith('/'):
                    image_url = image_url[1:]
                image_url = f"{base_url}{media_url}{image_url}"
        
        logger.info(f"Пытаемся отправить фото по URL: {image_url}")
        
        # Проверяем доступность URL (опционально, для отладки)
        try:
            check_response = requests.head(image_url, timeout=5, allow_redirects=True)
            if check_response.status_code != 200:
                logger.warning(f"URL изображения возвращает статус {check_response.status_code}: {image_url}")
        except Exception as e:
            logger.warning(f"Не удалось проверить доступность URL изображения: {str(e)}")
        
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        
        # Отправляем фото по URL
        data = {
            'chat_id': channel_id,
            'photo': image_url,
            'caption': message_text,
            'parse_mode': 'HTML',
        }
        
        # ВАЖНО: Telegram API требует отправку через form-data, а не JSON для sendPhoto с URL
        # Используем data вместо json
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        if result.get('ok'):
            message_id = str(result['result']['message_id'])
            logger.info(f"Сообщение с фото успешно отправлено в Telegram по URL. Message ID: {message_id}")
            return True, message_id, None
        else:
            error = result.get('description', 'Unknown error')
            logger.error(f"Ошибка при отправке фото в Telegram по URL: {error}")
            logger.error(f"Полный ответ от Telegram API: {result}")
            # Если не получилось, возвращаем ошибку
            return False, None, error
                
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при отправке фото по URL: {str(e)}")
        return False, None, str(e)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке фото в Telegram: {str(e)}", exc_info=True)
        return False, None, str(e)


def send_photo_as_file(advertisement, message_text, image_file):
    """
    Отправляет фото как файл (наиболее надежный метод)
    """
    bot_token = settings.TELEGRAM_BOT_TOKEN
    channel_id = settings.TELEGRAM_CHANNEL_ID
    
    # Получаем полный путь к файлу
    if not image_file:
        logger.warning("Изображение не указано")
        return False, None, "Изображение не указано"
    
    # Проверяем, существует ли файл
    if not image_file.name:
        logger.warning("Имя файла изображения не указано")
        return False, None, "Имя файла изображения не указано"
    
    try:
        image_path = image_file.path
    except (ValueError, AttributeError, NotImplementedError) as e:
        # Если файл хранится в облаке (S3 и т.д.), используем URL
        logger.info(f"Файл не доступен локально ({str(e)}), используем URL метод")
        return False, None, "Файл не доступен локально"
    
    # Проверяем существование файла
    if not os.path.exists(image_path):
        logger.warning(f"Файл изображения не найден: {image_path}")
        return False, None, f"Файл не найден: {image_path}"
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        
        logger.info(f"Открываем файл для отправки: {image_path}")
        logger.info(f"Размер файла: {os.path.getsize(image_path) / 1024:.2f} KB")
        
        with open(image_path, 'rb') as photo:
            files = {'photo': ('image.jpg', photo, 'image/jpeg')}
            data = {
                'chat_id': channel_id,
                'caption': message_text,
                'parse_mode': 'HTML',
            }
            
            logger.info(f"Отправляем фото в Telegram канал {channel_id}")
            response = requests.post(url, files=files, data=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Ответ от Telegram API: {result}")
            
            if result.get('ok'):
                message_id = str(result['result']['message_id'])
                logger.info(f"✅ Сообщение с фото успешно отправлено в Telegram (как файл). Message ID: {message_id}")
                return True, message_id, None
            else:
                error = result.get('description', 'Unknown error')
                logger.error(f"❌ Ошибка при отправке фото в Telegram: {error}")
                logger.error(f"Полный ответ: {result}")
                return False, None, error
                
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при отправке фото в Telegram: {str(e)}")
        return False, None, str(e)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке фото в Telegram: {str(e)}", exc_info=True)
        return False, None, str(e)

