"""
Утилиты для безопасности и валидации входных данных
Защита от SQL инъекций, XSS и других атак
"""
import re
from django.utils.html import escape
from django.core.exceptions import ValidationError


def sanitize_string(value, max_length=1000, allow_html=False):
    """
    Санитизация строки от потенциально опасных символов
    
    Args:
        value: Строка для санитизации
        max_length: Максимальная длина строки
        allow_html: Разрешить HTML теги (по умолчанию False)
    
    Returns:
        Очищенная строка
    """
    if not isinstance(value, str):
        value = str(value)
    
    # Убираем пробелы в начале и конце
    value = value.strip()
    
    # Проверяем длину
    if len(value) > max_length:
        raise ValidationError(f'Строка слишком длинная (максимум {max_length} символов)')
    
    # Если HTML не разрешен, экранируем специальные символы
    if not allow_html:
        value = escape(value)
    
    return value


def validate_email(email):
    """
    Валидация email адреса
    
    Args:
        email: Email для валидации
    
    Returns:
        True если валидный, иначе False
    """
    if not email or not isinstance(email, str):
        return False
    
    email = email.strip().lower()
    
    # Базовая проверка формата
    if len(email) > 254:  # RFC 5321
        return False
    
    # Простая проверка формата email
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False
    
    # Проверка на подозрительные символы
    suspicious_chars = ['<', '>', '"', "'", ';', '--', '/*', '*/']
    for char in suspicious_chars:
        if char in email:
            return False
    
    return True


def validate_phone(phone):
    """
    Валидация номера телефона
    
    Args:
        phone: Номер телефона для валидации
    
    Returns:
        True если валидный, иначе False
    """
    if not phone or not isinstance(phone, str):
        return False
    
    phone = phone.strip()
    
    # Убираем все нецифровые символы кроме +, пробелов, дефисов и скобок
    cleaned = re.sub(r'[^\d\+\s\-\(\)]', '', phone)
    
    # Проверяем, что остались только допустимые символы
    if len(cleaned) < 5 or len(cleaned) > 20:
        return False
    
    # Проверка на подозрительные символы
    suspicious_chars = ['<', '>', '"', "'", ';', '--', '/*', '*/', 'script', 'javascript']
    phone_lower = phone.lower()
    for char in suspicious_chars:
        if char in phone_lower:
            return False
    
    return True


def sanitize_search_query(query):
    """
    Санитизация поискового запроса
    
    Args:
        query: Поисковый запрос
    
    Returns:
        Очищенный запрос
    """
    if not query or not isinstance(query, str):
        return ''
    
    query = query.strip()
    
    # Ограничиваем длину
    if len(query) > 200:
        query = query[:200]
    
    # Убираем опасные SQL конструкции (хотя Django ORM защищает)
    dangerous_patterns = [
        r';\s*(drop|delete|update|insert|alter|create|exec|execute)',
        r'--',
        r'/\*',
        r'\*/',
        r'union\s+select',
        r'xp_',
        r'sp_',
    ]
    
    query_lower = query.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, query_lower):
            # Логируем попытку SQL инъекции
            import logging
            logger = logging.getLogger('security')
            logger.warning(f'Обнаружена попытка SQL инъекции в поисковом запросе: {query[:50]}')
            # Удаляем опасные паттерны
            query = re.sub(pattern, '', query, flags=re.IGNORECASE)
    
    return query.strip()


def validate_file_upload(file, allowed_types=None, max_size_mb=10):
    """
    Валидация загружаемого файла
    
    Args:
        file: Файл для валидации
        allowed_types: Список разрешенных MIME типов
        max_size_mb: Максимальный размер в МБ
    
    Returns:
        True если валидный, иначе False
    """
    if not file:
        return False
    
    # Проверка размера
    max_size_bytes = max_size_mb * 1024 * 1024
    if hasattr(file, 'size') and file.size > max_size_bytes:
        return False
    
    # Проверка типа файла
    if allowed_types:
        content_type = getattr(file, 'content_type', '') or ''
        if not any(allowed_type in content_type for allowed_type in allowed_types):
            return False
    
    # Проверка имени файла на опасные символы
    if hasattr(file, 'name'):
        dangerous_chars = ['..', '/', '\\', '<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            if char in file.name:
                return False
    
    return True


def check_sql_injection_patterns(value):
    """
    Проверка на паттерны SQL инъекций
    
    Args:
        value: Значение для проверки
    
    Returns:
        True если обнаружены подозрительные паттерны
    """
    if not isinstance(value, str):
        return False
    
    value_lower = value.lower()
    
    # Паттерны SQL инъекций
    sql_patterns = [
        r"'\s*(or|and)\s+['\d]+\s*=\s*['\d]+",
        r"'\s*(or|and)\s+['\d]+\s*=\s*['\d]+",
        r'union\s+select',
        r';\s*(drop|delete|update|insert|alter|create|exec|execute)',
        r'--',
        r'/\*',
        r'\*/',
        r'xp_',
        r'sp_',
        r'waitfor\s+delay',
        r'benchmark\s*\(',
    ]
    
    for pattern in sql_patterns:
        if re.search(pattern, value_lower):
            return True
    
    return False





