#!/bin/bash

set -e

# Создание базы данных если её нет
if [ ! -f /app/db.sqlite3 ]; then
    echo "Создание базы данных..."
    touch /app/db.sqlite3
    chmod 666 /app/db.sqlite3
fi

echo "Выполнение миграций..."
python manage.py migrate --noinput

echo "Сборка статических файлов..."
python manage.py collectstatic --noinput

echo "Создание суперпользователя..."
python create_superuser.py

echo "Запуск Gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 --workers 3 uzmat_site.wsgi:application

