# Инструкция по деплою на VPS Contabo

## Подключение к серверу

### Windows (PowerShell или CMD)

```bash
ssh root@109.199.127.149
```

Когда система попросит пароль, введите пароль от вашего VPS. При первом подключении система спросит подтверждение - введите `yes`.

### Если SSH не установлен на Windows

Используйте программу **PuTTY** (скачать: https://www.putty.org/):
- Host Name: `109.199.127.149`
- Port: `22`
- Connection type: `SSH`
- Нажмите "Open"
- Login as: `root`
- Введите пароль

---

## Подготовка сервера

После подключения выполните следующие команды на сервере:

### 1. Обновление системы

```bash
apt update && apt upgrade -y
```

### 2. Установка необходимых пакетов

```bash
apt install -y python3 python3-pip python3-venv nginx git
```

### 3. Создание директории для проекта

```bash
mkdir -p /var/www/uzmat
cd /var/www/uzmat
```

---

## Загрузка проекта на сервер

### Вариант 1: Через Git (если проект в репозитории)

```bash
git clone <URL_ВАШЕГО_РЕПОЗИТОРИЯ> /var/www/uzmat
```

### Вариант 2: Через SCP (загрузка с вашего компьютера)

На вашем локальном компьютере (Windows PowerShell) выполните:

```bash
scp -r C:\Users\Wlad\OneDrive\Desktop\узмат\uzmat\* root@109.199.127.149:/var/www/uzmat/
```

Или используйте программу **WinSCP** (https://winscp.net/) для графической загрузки файлов.

### Вариант 3: Через SFTP клиент

Используйте **FileZilla** (https://filezilla-project.org/):
- Host: `sftp://109.199.127.149`
- Username: `root`
- Password: ваш пароль
- Port: `22`

---

## Настройка проекта на сервере

### 1. Создание виртуального окружения

```bash
cd /var/www/uzmat
python3 -m venv venv
source venv/bin/activate
```

### 2. Установка зависимостей

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn  # для запуска Django в production
```

### 3. Настройка settings.py для production

Отредактируйте файл `/var/www/uzmat/uzmat_site/settings.py`:

```python
# Изменить:
DEBUG = False
ALLOWED_HOSTS = ['109.199.127.149', 'ваш-домен.ru']  # добавьте ваш домен если есть

# Добавить в конец файла:
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
```

### 4. Сборка статических файлов

```bash
python manage.py collectstatic --noinput
```

### 5. Создание миграций и применение их

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Создание суперпользователя (если нужно)

```bash
python manage.py createsuperuser
```

---

## Настройка Gunicorn

### 1. Создание файла конфигурации Gunicorn

```bash
nano /var/www/uzmat/gunicorn_config.py
```

Вставьте:

```python
bind = "127.0.0.1:8000"
workers = 3
timeout = 120
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

### 2. Создание systemd сервиса

```bash
nano /etc/systemd/system/uzmat.service
```

Вставьте:

```ini
[Unit]
Description=Gunicorn daemon for uzmat
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/uzmat
ExecStart=/var/www/uzmat/venv/bin/gunicorn --config /var/www/uzmat/gunicorn_config.py uzmat_site.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Сохраните и запустите:

```bash
systemctl daemon-reload
systemctl start uzmat
systemctl enable uzmat
systemctl status uzmat
```

---

## Настройка Nginx

### 1. Создание конфигурации Nginx

```bash
nano /etc/nginx/sites-available/uzmat
```

Вставьте:

```nginx
server {
    listen 80;
    server_name 109.199.127.149;  # или ваш домен

    client_max_body_size 100M;

    location /static/ {
        alias /var/www/uzmat/staticfiles/;
    }

    location /media/ {
        alias /var/www/uzmat/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. Активация конфигурации

```bash
ln -s /etc/nginx/sites-available/uzmat /etc/nginx/sites-enabled/
nginx -t  # проверка конфигурации
systemctl restart nginx
```

---

## Настройка прав доступа

```bash
chown -R root:www-data /var/www/uzmat
chmod -R 755 /var/www/uzmat
chmod -R 775 /var/www/uzmat/media
```

---

## Проверка работы

Откройте в браузере: `http://109.199.127.149`

Если всё работает, вы увидите ваш сайт!

---

## Полезные команды для управления

```bash
# Перезапуск Gunicorn
systemctl restart uzmat

# Просмотр логов Gunicorn
journalctl -u uzmat -f

# Перезапуск Nginx
systemctl restart nginx

# Просмотр логов Nginx
tail -f /var/log/nginx/error.log
```

---

## Важные замечания

1. **Безопасность**: После деплоя обязательно смените `SECRET_KEY` в `settings.py` на случайный ключ
2. **База данных**: Сейчас используется SQLite. Для production лучше использовать PostgreSQL или MySQL
3. **SSL сертификат**: Для HTTPS установите Let's Encrypt сертификат через certbot
4. **Firewall**: Настройте firewall для безопасности сервера

---

## Если что-то не работает

1. Проверьте статус сервисов:
```bash
systemctl status uzmat
systemctl status nginx
```

2. Проверьте логи:
```bash
journalctl -u uzmat -n 50
tail -f /var/log/nginx/error.log
```

3. Проверьте, что порты открыты:
```bash
netstat -tulpn | grep :80
netstat -tulpn | grep :8000
```

