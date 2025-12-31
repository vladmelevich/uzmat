"""
URL configuration for uzmat_site project.
"""
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, HttpResponseNotFound
from uzmat import views as uzmat_views
from uzmat.sitemaps import StaticViewSitemap, AdvertisementSitemap

# Sitemaps
sitemaps = {
    'static': StaticViewSitemap,
    'advertisements': AdvertisementSitemap,
}

def well_known_handler(request, path):
    """Обработчик для запросов .well-known (Chrome DevTools и т.д.)"""
    return HttpResponseNotFound()

def robots_txt(request):
    """Генерация robots.txt"""
    content = """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /chats/api/
Disallow: /payment/
Disallow: /verify/moderation/
Disallow: /check-auth/

Sitemap: {scheme}://{host}/sitemap.xml
""".format(
        scheme=request.scheme,
        host=request.get_host()
    )
    return HttpResponse(content, content_type='text/plain')

urlpatterns = [
    # ВАЖНО: должно стоять выше path('admin/', ...) иначе Django admin перехватит /admin/notify/
    path('admin/notify/', uzmat_views.admin_send_notification, name='admin_send_notification'),
    path('admin/', admin.site.urls),
    path('', include('uzmat.urls', namespace='uzmat')),
    # SEO
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
    # Игнорируем запросы от Chrome DevTools
    path('.well-known/<path:path>', well_known_handler, name='well-known'),
]

# Для разработки - обслуживание статики и медиа файлов
if settings.DEBUG:
    # Статика автоматически обслуживается из STATICFILES_DIRS через staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
    # Медиа файлы обслуживаются явно
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)











