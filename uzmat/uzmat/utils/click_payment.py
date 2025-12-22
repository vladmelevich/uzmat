"""
Утилита для работы с Click платежной системой
"""
import hashlib
import hmac
import base64
from django.conf import settings
from decimal import Decimal


def generate_click_signature(merchant_trans_id: str, amount: Decimal, action: int, sign_time: str) -> str:
    """
    Генерирует подпись для Click API
    
    Args:
        merchant_trans_id: ID транзакции в системе мерчанта
        amount: Сумма платежа
        action: Действие (0 - prepare, 1 - complete)
        sign_time: Время подписи в формате YYYY-MM-DD HH:mm:ss
        
    Returns:
        Подпись для запроса
    """
    secret_key = settings.CLICK_SETTINGS['SECRET_KEY']
    
    # Формируем строку для подписи
    sign_string = f"{merchant_trans_id}{amount}{action}{sign_time}{secret_key}"
    
    # Создаем HMAC SHA256 подпись
    signature = hmac.new(
        secret_key.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_click_signature(merchant_trans_id: str, merchant_prepare_id: str, amount: Decimal, action: int, sign_time: str, sign_string: str) -> bool:
    """
    Проверяет подпись от Click webhook
    
    Args:
        merchant_trans_id: ID транзакции в системе мерчанта
        merchant_prepare_id: ID prepare транзакции
        amount: Сумма платежа
        action: Действие (0 - prepare, 1 - complete)
        sign_time: Время подписи
        sign_string: Подпись от Click
        
    Returns:
        True если подпись верна, False иначе
    """
    secret_key = settings.CLICK_SETTINGS['SECRET_KEY']
    
    # Формируем строку для проверки подписи
    sign_string_to_check = f"{merchant_trans_id}{merchant_prepare_id}{amount}{action}{sign_time}{secret_key}"
    
    # Создаем HMAC SHA256 подпись
    expected_signature = hmac.new(
        secret_key.encode('utf-8'),
        sign_string_to_check.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, sign_string)


def generate_click_payment_url(payment_id: int, amount: Decimal, return_url: str) -> str:
    """
    Генерирует URL для оплаты через Click
    
    Args:
        payment_id: ID платежа в нашей системе
        amount: Сумма платежа в сумах
        return_url: URL для возврата после оплаты
        
    Returns:
        URL для редиректа на оплату
    """
    service_id = settings.CLICK_SETTINGS['SERVICE_ID']
    merchant_id = settings.CLICK_SETTINGS['MERCHANT_ID']
    merchant_user_id = settings.CLICK_SETTINGS['MERCHANT_USER_ID']
    
    # Формируем URL для оплаты
    # Формат: https://my.click.uz/services/pay?service_id=XXX&merchant_id=XXX&amount=XXX&transaction_param=XXX&return_url=XXX
    
    base_url = "https://my.click.uz/services/pay"
    
    params = {
        'service_id': service_id,
        'merchant_id': merchant_id,
        'amount': str(amount),
        'transaction_param': str(payment_id),
        'return_url': return_url,
    }
    
    # Формируем query string
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    
    return f"{base_url}?{query_string}"
