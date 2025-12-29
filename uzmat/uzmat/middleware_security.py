"""
Middleware для дополнительной безопасности
Защита от брутфорса, rate limiting и другие меры безопасности
"""
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages
import time
import logging


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware для добавления безопасных HTTP заголовков
    """
    
    def _is_trustworthy_origin(self, request):
        """
        Проверяет, является ли origin надежным (HTTPS или localhost)
        Cross-Origin-Opener-Policy работает только для надежных origins
        Согласно спецификации: https://www.w3.org/TR/powerful-features/#potentially-trustworthy-origin
        """
        try:
            # Проверяем схему запроса напрямую (может не существовать в старых версиях Django)
            scheme = getattr(request, 'scheme', '').lower()
            is_https = scheme == 'https'
            
            # Также проверяем заголовки прокси (для случаев, когда Django за прокси)
            if not is_https:
                is_https = (
                    request.is_secure() or 
                    request.META.get('HTTP_X_FORWARDED_PROTO', '').lower() == 'https' or
                    request.META.get('HTTP_X_FORWARDED_SSL', '').lower() == 'on'
                )
            
            # Проверяем, является ли это localhost (для HTTP localhost тоже надежный)
            try:
                host = request.get_host().lower()
            except Exception:
                # Если не удалось получить host, считаем ненадежным
                return False
            
            # Убираем порт из host для проверки
            host_without_port = host.split(':')[0]
            is_localhost = (
                host_without_port == 'localhost' or 
                host_without_port == '127.0.0.1' or 
                host_without_port == '::1' or
                host_without_port.startswith('localhost.')
            )
            
            # Origin надежный, если это HTTPS или localhost
            return is_https or is_localhost
        except Exception:
            # В случае любой ошибки считаем origin ненадежным (безопасный вариант)
            return False
    
    def process_response(self, request, response):
        try:
            # X-Content-Type-Options: nosniff
            response['X-Content-Type-Options'] = 'nosniff'
            
            # X-Frame-Options: DENY (защита от clickjacking)
            response['X-Frame-Options'] = 'DENY'
            
            # X-XSS-Protection (для старых браузеров)
            response['X-XSS-Protection'] = '1; mode=block'
            
            # Referrer-Policy
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            # Permissions-Policy (бывший Feature-Policy)
            response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
            
            # Cross-Origin-Opener-Policy: добавляем только для надежных origins
            # (HTTPS или localhost), иначе браузер будет игнорировать заголовок и выдавать предупреждение
            # Если origin не надежный, явно удаляем заголовок, если он был установлен ранее
            try:
                if self._is_trustworthy_origin(request):
                    response['Cross-Origin-Opener-Policy'] = 'same-origin'
                else:
                    # Явно удаляем заголовок для ненадежных origins, чтобы избежать предупреждений
                    # Используем pop() с default, чтобы безопасно удалить заголовок
                    response.pop('Cross-Origin-Opener-Policy', None)
            except Exception:
                # Если ошибка при проверке origin, просто не добавляем заголовок
                response.pop('Cross-Origin-Opener-Policy', None)
        except Exception:
            # В случае любой ошибки просто возвращаем response без изменений
            # Логируем ошибку для отладки
            logger = logging.getLogger('django.request')
            logger.error('Ошибка в SecurityHeadersMiddleware.process_response', exc_info=True)
        
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    Middleware для защиты от брутфорса и rate limiting
    """
    
    def process_request(self, request):
        try:
            # Защита от брутфорса для страниц авторизации
            if request.path in ['/auth/', '/register/individual/', '/register/company/'] and request.method == 'POST':
                # Получаем IP адрес
                ip_address = self.get_client_ip(request)
                
                # Ключ для кэша
                rate_limit_key = f'rate_limit_login_{ip_address}'
                attempts_key = f'login_attempts_{ip_address}'
                
                # Проверяем количество попыток
                attempts = cache.get(attempts_key, 0)
                max_attempts = 5  # Максимум 5 попыток
                
                if attempts >= max_attempts:
                    # Проверяем, не истекла ли блокировка
                    blocked_until = cache.get(rate_limit_key)
                    if blocked_until and time.time() < blocked_until:
                        remaining_time = int(blocked_until - time.time())
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'ok': False,
                                'error': f'Слишком много попыток входа. Попробуйте через {remaining_time} секунд.'
                            }, status=429)
                        else:
                            messages.error(request, f'Слишком много попыток входа. Попробуйте через {remaining_time // 60} минут.')
                            from django.shortcuts import redirect
                            return redirect('uzmat:auth')
                    else:
                        # Блокировка истекла, сбрасываем счетчик
                        cache.delete(attempts_key)
                        cache.delete(rate_limit_key)
                        attempts = 0
                
                # Увеличиваем счетчик попыток при неудачной попытке входа
                # Это будет обработано в view после проверки пароля
        except Exception:
            # В случае ошибки просто пропускаем rate limiting
            logger = logging.getLogger('django.request')
            logger.error('Ошибка в RateLimitMiddleware.process_request', exc_info=True)
        
        return None
    
    def process_response(self, request, response):
        try:
            # Если это неудачная попытка входа (статус 200, но с ошибкой)
            if request.path in ['/auth/', '/register/individual/', '/register/company/'] and request.method == 'POST':
                if response.status_code == 200:
                    # Проверяем, есть ли сообщение об ошибке
                    try:
                        storage = messages.get_messages(request)
                        has_error = any(msg.tags == 'error' for msg in storage)
                        
                        if has_error:
                            ip_address = self.get_client_ip(request)
                            attempts_key = f'login_attempts_{ip_address}'
                            rate_limit_key = f'rate_limit_login_{ip_address}'
                            
                            # Увеличиваем счетчик попыток
                            attempts = cache.get(attempts_key, 0) + 1
                            cache.set(attempts_key, attempts, 3600)  # Храним 1 час
                            
                            # Если превышен лимит, блокируем на 5 минут
                            if attempts >= 5:
                                cache.set(rate_limit_key, time.time() + 300, 300)  # Блокировка на 5 минут
                    except Exception:
                        # Если ошибка при проверке сообщений, просто пропускаем
                        pass
        except Exception:
            # В случае ошибки просто возвращаем response
            logger = logging.getLogger('django.request')
            logger.error('Ошибка в RateLimitMiddleware.process_response', exc_info=True)
        
        return response
    
    def get_client_ip(self, request):
        """Получает реальный IP адрес клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class InputSanitizationMiddleware(MiddlewareMixin):
    """
    Middleware для базовой санитизации входных данных
    """
    
    def process_request(self, request):
        try:
            # Базовая защита от SQL инъекций через валидацию параметров
            # Django ORM уже защищает от SQL инъекций, но добавим дополнительную проверку
            
            # Проверяем GET параметры на подозрительные символы
            suspicious_chars = [';', '--', '/*', '*/', 'xp_', 'sp_', 'exec', 'union', 'select']
            
            for key, value in request.GET.items():
                if isinstance(value, str):
                    value_lower = value.lower()
                    for char in suspicious_chars:
                        if char in value_lower:
                            # Логируем попытку (в production можно отправить в систему мониторинга)
                            logger = logging.getLogger('security')
                            logger.warning(f'Подозрительный запрос от {self.get_client_ip(request)}: {key}={value[:50]}')
                            # Не блокируем, но логируем (Django ORM все равно защитит)
                            break
        except Exception:
            # В случае ошибки просто пропускаем проверку
            logger = logging.getLogger('django.request')
            logger.error('Ошибка в InputSanitizationMiddleware.process_request', exc_info=True)
        
        return None
    
    def get_client_ip(self, request):
        """Получает реальный IP адрес клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


