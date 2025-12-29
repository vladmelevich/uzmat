"""
Management команда для создания суперпользователя по умолчанию
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Создает суперпользователя по умолчанию, если его еще нет'

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@gmail.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '12133')

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'Суперпользователь "{username}" уже существует')
            )
        else:
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Суперпользователь создан:\n'
                    f'   Username: {username}\n'
                    f'   Email: {email}\n'
                    f'   Password: {password}'
                )
            )


