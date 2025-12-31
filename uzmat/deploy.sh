#!/bin/bash

# Скрипт для безопасного деплоя на сервер
# Использование: ./deploy.sh

set -e  # Остановка при ошибке

echo "🚀 Начинаем деплой Uzmat..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Бэкап базы данных
echo -e "${YELLOW}📦 Создаем бэкап базы данных...${NC}"
BACKUP_FILE="backups/backup_$(date +%Y%m%d_%H%M%S).sql"
mkdir -p backups
docker exec uzmat_mysql mysqldump -u ${DB_USER:-uzmat_user} -p${DB_PASSWORD:-uzmat_password} ${DB_NAME:-uzmat} > "$BACKUP_FILE" 2>/dev/null || \
docker exec uzmat_mysql mysqldump -u root -p${MYSQL_ROOT_PASSWORD:-root_password} ${DB_NAME:-uzmat} > "$BACKUP_FILE"
echo -e "${GREEN}✅ Бэкап создан: $BACKUP_FILE${NC}"

# 2. Останавливаем контейнеры
echo -e "${YELLOW}⏸️  Останавливаем контейнеры...${NC}"
docker-compose down

# 3. Обновляем код (если используется git)
if [ -d ".git" ]; then
    echo -e "${YELLOW}📥 Обновляем код из git...${NC}"
    git pull
fi

# 4. Пересобираем образы
echo -e "${YELLOW}🔨 Пересобираем Docker образы...${NC}"
docker-compose build --no-cache

# 5. Запускаем контейнеры
echo -e "${YELLOW}▶️  Запускаем контейнеры...${NC}"
docker-compose up -d

# 6. Ждем готовности MySQL
echo -e "${YELLOW}⏳ Ждем готовности MySQL...${NC}"
sleep 10

# 7. Применяем миграции
echo -e "${YELLOW}🔄 Применяем миграции...${NC}"
docker-compose exec -T web python manage.py migrate --noinput

# 8. Собираем статику
echo -e "${YELLOW}📦 Собираем статические файлы...${NC}"
docker-compose exec -T web python manage.py collectstatic --noinput --clear

# 9. Перезапускаем nginx для применения изменений
echo -e "${YELLOW}🔄 Перезапускаем nginx...${NC}"
docker-compose restart nginx || echo "Nginx не запущен, пропускаем"

# 10. Создаем суперпользователя (если еще не существует)
echo -e "${YELLOW}👤 Создаем суперпользователя...${NC}"
docker-compose exec -T web python manage.py create_default_superuser

# 11. Проверяем статус
echo -e "${YELLOW}🔍 Проверяем статус контейнеров...${NC}"
docker-compose ps

echo -e "${GREEN}✅ Деплой завершен успешно!${NC}"
echo -e "${GREEN}🌐 Сайт доступен по адресу: http://109.199.127.149${NC}"

