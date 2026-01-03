#!/bin/bash

# Остановка скрипта при ошибке
set -e

echo "🚀 Starting deployment..."

# 1. Pull latest code
echo "📥 Pulling latest code..."
git pull origin main

# 2. Check for .env file
if [ ! -f .env ]; then
    echo "⚠️ .env file not found! Creating from example..."
    cp env-example.txt .env
    echo "❗ Please edit .env file and run this script again."
    exit 1
fi

# 3. Build and restart containers
echo "🏗️ Building and restarting containers..."
docker-compose down --remove-orphans
# Force remove containers to prevent name conflicts
docker rm -f diagnostic-bot diagnostic-redis diagnostic-db || true

docker-compose build --no-cache
docker-compose up -d

# 3.1 Run migrations
echo "🔄 Running migrations..."
docker-compose exec -T bot python scripts/migrate_mode_column.py
docker-compose exec -T bot python scripts/force_migration.py

# 4. Cleanup unused images
echo "🧹 Cleaning up..."
docker image prune -f

echo "✅ Deployment completed successfully!"
echo "📜 Logs:"
docker-compose logs -f --tail=50 bot
