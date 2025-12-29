"""
WSGI config for uzmat_site project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os
import logging

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'uzmat_site.settings')

logger = logging.getLogger('django.request')

# Обертка для логирования проблем с ALLOWED_HOSTS
_original_application = None

def application(environ, start_response):
    global _original_application
    if _original_application is None:
        _original_application = get_wsgi_application()
    
    # Логируем Host заголовок для отладки
    host = environ.get('HTTP_HOST', '')
    logger.info(f'WSGI Request Host: {host}')
    
    try:
        return _original_application(environ, start_response)
    except Exception as e:
        # Логируем ошибки для отладки
        if 'DisallowedHost' in str(type(e)) or '400' in str(e):
            logger.error(f'ALLOWED_HOSTS error. Host: {host}, Error: {e}')
        raise












