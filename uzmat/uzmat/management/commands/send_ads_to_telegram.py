"""
Management command для отправки объявлений в Telegram канал
Использование: python manage.py send_ads_to_telegram [--all] [--limit N]
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from uzmat.models import Advertisement
from uzmat.utils.telegram_service import send_ad_to_telegram
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Отправляет объявления в Telegram канал'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Отправить все объявления, даже уже отправленные',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Максимальное количество объявлений для отправки (по умолчанию: 10)',
        )
        parser.add_argument(
            '--active-only',
            action='store_true',
            help='Отправлять только активные объявления',
        )

    def handle(self, *args, **options):
        send_all = options['all']
        limit = options['limit']
        active_only = options['active_only']
        
        # Формируем запрос
        queryset = Advertisement.objects.all()
        
        if not send_all:
            # Отправляем только те, которые еще не были отправлены
            queryset = queryset.filter(sent_to_telegram=False)
        
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        # Сортируем по дате создания (новые первыми)
        queryset = queryset.order_by('-created_at')
        
        # Ограничиваем количество
        ads = queryset[:limit]
        
        total = ads.count()
        if total == 0:
            self.stdout.write(
                self.style.WARNING('Нет объявлений для отправки')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(f'Найдено {total} объявлений для отправки')
        )
        
        success_count = 0
        error_count = 0
        
        for ad in ads:
            self.stdout.write(f'Отправка объявления: {ad.title}...')
            
            success, message_id, error = send_ad_to_telegram(ad)
            
            if success:
                # Обновляем объявление
                ad.sent_to_telegram = True
                if message_id:
                    ad.telegram_message_id = message_id
                ad.save(update_fields=['sent_to_telegram', 'telegram_message_id'])
                
                success_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Успешно отправлено (ID: {message_id})')
                )
            else:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ Ошибка: {error}')
                )
        
        # Итоговая статистика
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Готово! Успешно: {success_count}, Ошибок: {error_count}'
            )
        )


