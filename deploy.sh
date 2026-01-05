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

# 3. Build
export COMPOSE_PARALLEL_LIMIT=1
echo "🏗️ Building..."
docker compose build

# 3.0 Stop containers to avoid conflicts
echo "🛑 Stopping existing containers..."
docker compose down --remove-orphans
docker rm -f diagnostic-redis diagnostic-db diagnostic-bot || true

# 3.1 Run migrations (using run --rm to ensure DB is accessible even if bot fails)
echo "🔄 Running migrations..."
docker compose run --rm bot python scripts/migrate_mode_column.py
docker compose run --rm bot alembic upgrade head
docker compose run --rm bot python scripts/add_maxvisual200.py

# 3.2 Start bot
echo "🚀 Starting bot..."
docker compose up -d

# 4. Cleanup unused images
echo "🧹 Cleaning up..."
docker image prune -f

echo "✅ Deployment completed successfully!"
echo "📜 Logs:"
docker compose logs -f --tail=50 bot
