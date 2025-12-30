"""
Сессия базы данных.
"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from src.core.config import get_settings
from src.db.models import Base

logger = logging.getLogger(__name__)

# Глобальные объекты
_engine = None
_session_maker = None


def get_database_url() -> str:
    """Получить URL базы данных."""
    settings = get_settings()
    
    # Если PostgreSQL URL не задан или дефолтный — используем SQLite
    if "postgresql" in settings.database_url and "user:password" in settings.database_url and "localhost" in settings.database_url:
        # Дефолтный URL — переключаемся на SQLite
        return "sqlite+aiosqlite:///./diagnostic_bot.db"
    
    return settings.database_url


async def init_db():
    """Инициализация базы данных."""
    global _engine, _session_maker
    
    db_url = get_database_url()
    logger.info(f"Initializing database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    
    # Создаём движок
    if "sqlite" in db_url:
        _engine = create_async_engine(
            db_url,
            echo=False,
        )
    else:
        _engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
    
    # Создаём фабрику сессий
    _session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Создаём таблицы
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database initialized successfully")


async def close_db():
    """Закрытие соединения с БД."""
    global _engine
    
    if _engine:
        await _engine.dispose()
        logger.info("Database connection closed")


def get_session() -> AsyncSession:
    """Получить сессию БД."""
    if _session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _session_maker()


async def get_db_session():
    """Генератор сессии для dependency injection."""
    async with get_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

