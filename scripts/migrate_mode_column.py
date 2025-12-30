"""
Миграция: переименование колонки mode -> diagnostic_mode

Запуск: python scripts/migrate_mode_column.py
"""
import asyncio
import os
import sys

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def migrate():
    """Переименовать колонку mode в diagnostic_mode."""
    # Загружаем переменные окружения
    from dotenv import load_dotenv
    load_dotenv()
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL не найден в .env")
        return False
    
    # Преобразуем URL для asyncpg
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    print(f"🔄 Подключение к БД...")
    engine = create_async_engine(database_url)
    
    try:
        async with engine.begin() as conn:
            # Проверяем, существует ли колонка mode
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'diagnostic_sessions' 
                AND column_name = 'mode'
            """))
            mode_exists = result.fetchone() is not None
            
            # Проверяем, существует ли колонка diagnostic_mode
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'diagnostic_sessions' 
                AND column_name = 'diagnostic_mode'
            """))
            diagnostic_mode_exists = result.fetchone() is not None
            
            if diagnostic_mode_exists:
                print("✅ Колонка diagnostic_mode уже существует. Миграция не нужна.")
                return True
            
            if not mode_exists:
                print("⚠️ Колонка mode не найдена. Создаём diagnostic_mode...")
                await conn.execute(text("""
                    ALTER TABLE diagnostic_sessions 
                    ADD COLUMN IF NOT EXISTS diagnostic_mode VARCHAR(10) DEFAULT 'full'
                """))
                print("✅ Колонка diagnostic_mode создана.")
                return True
            
            # Переименовываем колонку
            print("🔄 Переименование mode -> diagnostic_mode...")
            await conn.execute(text("""
                ALTER TABLE diagnostic_sessions 
                RENAME COLUMN mode TO diagnostic_mode
            """))
            print("✅ Колонка успешно переименована!")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return False
    finally:
        await engine.dispose()


if __name__ == "__main__":
    success = asyncio.run(migrate())
    sys.exit(0 if success else 1)

