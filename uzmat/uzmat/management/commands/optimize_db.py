"""
Команда для оптимизации базы данных и создания индексов
Использование: python manage.py optimize_db
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Оптимизирует базу данных и создает индексы для улучшения производительности'

    def handle(self, *args, **options):
        self.stdout.write('Начинаю оптимизацию базы данных...')
        
        with connection.cursor() as cursor:
            # Для SQLite
            if 'sqlite' in connection.settings_dict['ENGINE']:
                self.stdout.write('Выполняю VACUUM для SQLite...')
                cursor.execute('VACUUM')
                self.stdout.write(self.style.SUCCESS('VACUUM выполнен успешно'))
                
                self.stdout.write('Анализирую базу данных...')
                cursor.execute('ANALYZE')
                self.stdout.write(self.style.SUCCESS('ANALYZE выполнен успешно'))
        
        self.stdout.write(self.style.SUCCESS('Оптимизация завершена!'))
        self.stdout.write('Примечание: Для production рекомендуется использовать PostgreSQL с правильными индексами')





