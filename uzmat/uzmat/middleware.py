"""
Middleware для обработки ошибок загрузки файлов
Работает одинаково для HTTP и HTTPS протоколов
"""
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages
import json


class FileUploadErrorMiddleware(MiddlewareMixin):
    """
    Middleware для обработки ошибок загрузки файлов (413 Request Entity Too Large)
    и других ошибок, связанных с размером файлов
    """
    
    def process_exception(self, request, exception):
        """
        Обрабатывает исключения, связанные с загрузкой файлов
        Работает одинаково для HTTP и HTTPS протоколов
        """
        # Проверяем, является ли это ошибкой размера файла
        error_message = str(exception).lower()
        exception_type = type(exception).__name__
        
        # Django может выбросить различные исключения при превышении размера
        # Это работает независимо от протокола (HTTP/HTTPS)
        is_file_size_error = any(keyword in error_message for keyword in [
            'request entity too large',
            '413',
            'file too large',
            'file size',
            'max upload size',
            'request body too large',
            'content-length',
            'suspiciousoperation',
        ]) or '413' in str(exception)
        
        if is_file_size_error:
            # Определяем, это AJAX запрос или обычный
            # Работает одинаково для HTTP и HTTPS протоколов
            # Nginx передает информацию о протоколе через X-Forwarded-Proto,
            # но для обработки ошибок это не критично
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                request.path.startswith('/chats/api/') or
                'application/json' in request.headers.get('Accept', '')
            )
            
            if is_ajax:
                # Возвращаем JSON ответ для AJAX запросов
                return JsonResponse({
                    'ok': False,
                    'error': 'Размер фотографии слишком большой. Пожалуйста, выберите файл меньшего размера.'
                }, status=400)
            else:
                # Для обычных запросов возвращаем HTML ответ с сообщением об ошибке
                error_html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Ошибка загрузки файла</title>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                        .error { color: #e74c3c; font-size: 18px; margin: 20px 0; }
                        a { color: #3498db; text-decoration: none; }
                    </style>
                </head>
                <body>
                    <h1>Ошибка загрузки файла</h1>
                    <div class="error">Размер фотографии слишком большой. Пожалуйста, выберите файл меньшего размера.</div>
                    <a href="javascript:history.back()">Вернуться назад</a>
                </body>
                </html>
                """
                return HttpResponse(error_html, status=400)
        
        # Если это не наша ошибка, возвращаем None для стандартной обработки
        return None

