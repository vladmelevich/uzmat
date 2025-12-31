"""
Template tag для версионирования статических файлов
Использование: {% load static_version %} <link rel="stylesheet" href="{% static_version 'uzmat/styles.css' %}">
"""
from django import template
from django.templatetags.static import static
from django.conf import settings

register = template.Library()

@register.simple_tag
def static_version(path):
    """
    Возвращает путь к статическому файлу с версией из settings.STATIC_VERSION
    Это помогает обновлять кэш браузера при изменении файлов
    """
    static_path = static(path)
    version = getattr(settings, 'STATIC_VERSION', '1.0.0')
    return f"{static_path}?v={version}"

