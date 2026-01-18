# 🚀 Быстрый старт на сервере

## Шаг 1: Подготовка на сервере

```bash
# Установите Docker и Docker Compose (если еще не установлены)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Создайте директорию
sudo mkdir -p /var/www/uzmat
cd /var/www/uzmat
```

## Шаг 2: Загрузите проект

Загрузите все файлы проекта в `/var/www/uzmat/`

## Шаг 3: Настройте .env

```bash
cp env.example .env
nano .env
```

**Обязательно измените:**
- `SECRET_KEY` - сгенерируйте новый
- `DEBUG=False`
- `ALLOWED_HOSTS=localhost,127.0.0.1,109.199.127.149`
- `DB_PASSWORD` - надежный пароль
- `MYSQL_ROOT_PASSWORD` - надежный пароль

## Шаг 4: Запустите

```bash
chmod +x deploy.sh backup.sh
./deploy.sh
```

## Шаг 5: Создайте суперпользователя

```bash
docker-compose exec web python manage.py createsuperuser
```

## Готово! 🎉

Сайт доступен: `http://109.199.127.149`

## Обновление в будущем

Просто запустите:
```bash
./deploy.sh
```

Все данные сохранятся автоматически!






