"""
URL configuration for uzmat_site project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponseNotFound
from uzmat import views as uzmat_views

def well_known_handler(request, path):
    """Обработчик для запросов .well-known (Chrome DevTools и т.д.)"""
    return HttpResponseNotFound()

urlpatterns = [
    # ВАЖНО: должно стоять выше path('admin/', ...) иначе Django admin перехватит /admin/notify/
    path('admin/notify/', uzmat_views.admin_send_notification, name='admin_send_notification'),
    path('admin/', admin.site.urls),
    path('', include('uzmat.urls', namespace='uzmat')),
    # Игнорируем запросы от Chrome DevTools
    path('.well-known/<path:path>', well_known_handler, name='well-known'),
]

# Для разработки - обслуживание медиа файлов
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)











