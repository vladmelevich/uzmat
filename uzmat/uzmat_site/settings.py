"""
Django settings for uzmat_site project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-uzmat-premium-site-2024-secret-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# Разрешенные хосты (из переменной окружения или по умолчанию)
ALLOWED_HOSTS_STR = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,109.199.127.149,uzmat.uz,www.uzmat.uz')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_STR.split(',') if host.strip()]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'uzmat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'uzmat.middleware_security.SecurityHeadersMiddleware',  # Безопасные HTTP заголовки
    'uzmat.middleware_security.RateLimitMiddleware',  # Защита от брутфорса
    'uzmat.middleware_security.InputSanitizationMiddleware',  # Санитизация входных данных
    'uzmat.middleware.FileUploadErrorMiddleware',  # Обработка ошибок загрузки файлов
]

ROOT_URLCONF = 'uzmat_site.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'uzmat_site.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

# Настройки базы данных из переменных окружения
# Если не указаны, используется SQLite для разработки
DB_ENGINE = os.environ.get('DB_ENGINE', 'sqlite3')
DB_NAME = os.environ.get('DB_NAME', '')
DB_USER = os.environ.get('DB_USER', '')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_HOST = os.environ.get('DB_HOST', '')
DB_PORT = os.environ.get('DB_PORT', '')

if DB_ENGINE == 'mysql' and DB_NAME and DB_USER and DB_PASSWORD:
    # MySQL база данных
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST or 'localhost',
            'PORT': DB_PORT or '3306',
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    # SQLite для разработки (по умолчанию)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'ru-ru'

TIME_ZONE = 'Asia/Almaty'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Для production (когда соберёшь статику)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'uzmat.User'

# Media files (загруженные пользователями)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Настройки для загрузки файлов
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 МБ (для больших фото)
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 МБ
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Session settings (запоминание пользователя)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 дней
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SECURE = False  # Временно для HTTP, после активации Cloudflare изменить на True
SESSION_COOKIE_HTTPONLY = True  # Защита от XSS
SESSION_COOKIE_SAMESITE = 'Lax'  # Защита от CSRF

# Login URL для редиректа неавторизованных пользователей
LOGIN_URL = '/auth/'

# Безопасность: количество попыток входа
LOGIN_ATTEMPTS_LIMIT = 5  # Максимум попыток входа
LOGIN_ATTEMPTS_TIMEOUT = 300  # Блокировка на 5 минут (в секундах)

# Django REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# CSRF настройки для локальной разработки
CSRF_TRUSTED_ORIGINS_STR = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000,http://109.199.127.149,https://uzmat.uz,https://www.uzmat.uz')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in CSRF_TRUSTED_ORIGINS_STR.split(',') if origin.strip()]
CSRF_COOKIE_SECURE = False  # Временно для HTTP, после активации Cloudflare изменить на True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = False  # Используем cookies для CSRF токена

# Безопасные HTTP заголовки
SECURE_BROWSER_XSS_FILTER = True  # XSS фильтр браузера
SECURE_CONTENT_TYPE_NOSNIFF = True  # Защита от MIME-sniffing
X_FRAME_OPTIONS = 'DENY'  # Защита от clickjacking (уже есть в middleware, но дублируем)
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0  # HSTS только в production
SECURE_HSTS_INCLUDE_SUBDOMAINS = True if not DEBUG else False
SECURE_HSTS_PRELOAD = True if not DEBUG else False
SECURE_SSL_REDIRECT = False  # Nginx должен обрабатывать редирект на HTTPS

# Content Security Policy (базовая защита от XSS)
# В production можно настроить более строгую политику
if not DEBUG:
    SECURE_CSP_DEFAULT_SRC = "'self'"
    SECURE_CSP_SCRIPT_SRC = "'self' 'unsafe-inline'"  # Для Django admin и некоторых скриптов
    SECURE_CSP_STYLE_SRC = "'self' 'unsafe-inline'"
    SECURE_CSP_IMG_SRC = "'self' data: https:"
    SECURE_CSP_FONT_SRC = "'self' data:"

# Click платежная система настройки
CLICK_SETTINGS = {
    'SERVICE_ID': os.environ.get('CLICK_SERVICE_ID', '81723'),
    'MERCHANT_ID': os.environ.get('CLICK_MERCHANT_ID', '45447'),
    'SECRET_KEY': os.environ.get('CLICK_SECRET_KEY', 'KvAacs6ABwlULaC'),
    'MERCHANT_USER_ID': os.environ.get('CLICK_MERCHANT_USER_ID', '63140'),
    'API_URL': 'https://api.click.uz/v2/merchant/',
}

# Кэш для конвертации валют и оптимизации производительности
# Для production используйте Redis, для разработки - локальный кэш
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 10000,
            'CULL_FREQUENCY': 3,
        },
        'TIMEOUT': 300,  # 5 минут по умолчанию
    }
}

# Для production раскомментируйте и настройте Redis:
# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.redis.RedisCache',
#         'LOCATION': 'redis://127.0.0.1:6379/1',
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient',
#             'SOCKET_CONNECT_TIMEOUT': 5,
#             'SOCKET_TIMEOUT': 5,
#             'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
#             'IGNORE_EXCEPTIONS': True,
#         },
#         'KEY_PREFIX': 'uzmat',
#         'TIMEOUT': 300,
#     }
# }

# Настройки email отключены (не используются в проекте)
# Если понадобится отправка email в будущем, раскомментируйте и настройте:
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.yandex.ru'
# EMAIL_PORT = 465
# EMAIL_USE_SSL = True
# EMAIL_HOST_USER = 'your-email@yandex.ru'
# EMAIL_HOST_PASSWORD = 'your-app-password'
# DEFAULT_FROM_EMAIL = 'your-email@yandex.ru'
# DEFAULT_FROM_NAME = 'Uzmat'

# Логирование для безопасности
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'security.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'security': {
            'handlers': ['security_file', 'console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['security_file', 'console'],
            'level': 'WARNING',
            'propagate': True,
        },
    },
}

