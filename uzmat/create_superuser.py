#!/usr/bin/env python
"""
Скрипт для создания суперпользователя
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'uzmat_site.settings')
django.setup()

from uzmat.models import User

def create_superuser():
    username = 'admin'
    email = 'admin@uzmat.com'
    password = '12133'
    
    if User.objects.filter(username=username).exists():
        print(f'Суперпользователь {username} уже существует')
        # Обновляем пароль на случай если нужно изменить
        user = User.objects.get(username=username)
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        print(f'Пароль для {username} обновлен')
    else:
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        print(f'Суперпользователь {username} создан успешно')

if __name__ == '__main__':
    create_superuser()

