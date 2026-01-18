"""
Sitemap для SEO оптимизации
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Advertisement


class StaticViewSitemap(Sitemap):
    """Статические страницы"""
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return [
            'uzmat:index',
            'uzmat:catalog',
            'uzmat:about',
            'uzmat:help',
            'uzmat:rules',
            'uzmat:safety',
            'uzmat:privacy_policy',
            'uzmat:terms_of_use',
            'uzmat:sitemap',
        ]

    def location(self, item):
        return reverse(item)


class AdvertisementSitemap(Sitemap):
    """Объявления"""
    changefreq = 'daily'
    priority = 0.9

    def items(self):
        # Только активные объявления с валидными slug
        return Advertisement.objects.filter(
            is_active=True
        ).exclude(slug='').exclude(slug__isnull=True).order_by('-created_at')

    def location(self, item):
        return reverse('uzmat:ad_detail', kwargs={'slug': item.slug})

    def lastmod(self, item):
        return item.updated_at or item.created_at


