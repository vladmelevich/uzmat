#!/bin/bash

# Скрипт для создания бэкапа базы данных
# Использование: ./backup.sh

set -e

BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql"

echo "📦 Создаем бэкап базы данных..."

# Пытаемся создать бэкап с пользователем БД
docker exec uzmat_mysql mysqldump -u ${DB_USER:-uzmat_user} -p${DB_PASSWORD:-uzmat_password} ${DB_NAME:-uzmat} > "$BACKUP_FILE" 2>/dev/null || \
# Если не получилось, используем root
docker exec uzmat_mysql mysqldump -u root -p${MYSQL_ROOT_PASSWORD:-root_password} ${DB_NAME:-uzmat} > "$BACKUP_FILE"

# Сжимаем бэкап
gzip "$BACKUP_FILE"

echo "✅ Бэкап создан: ${BACKUP_FILE}.gz"

# Удаляем старые бэкапы (оставляем последние 7)
echo "🧹 Удаляем старые бэкапы (оставляем последние 7)..."
ls -t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true

echo "✅ Готово!"





