"""
Deep Diagnostic Bot — точка входа.
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from src.core.config import get_settings
from src.bot.handlers import start, diagnostic, history, voice
from src.bot.middlewares.error_handler import ErrorHandlerMiddleware
from src.bot.middlewares.logging_middleware import LoggingMiddleware
from src.db import init_db, close_db


async def main():
    """Запуск бота."""
    settings = get_settings()
    
    # Настройка логирования
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)
    
    # Инициализация базы данных
    logger.info("🗄️ Инициализация базы данных...")
    await init_db()
    
    # Инициализация бота
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    
    # Диспетчер с хранилищем состояний в памяти
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация middleware
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())
    
    # Регистрация роутеров (порядок важен!)
    dp.include_router(start.router)
    dp.include_router(history.router)
    dp.include_router(voice.router)  # Голосовые до diagnostic (для фильтрации)
    dp.include_router(diagnostic.router)
    
    # Запуск
    logger.info("🚀 Бот запускается...")
    logger.info(f"📡 AI Provider: {settings.routerai_base_url}")
    logger.info(f"🤖 AI Model: {settings.ai_model}")
    
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("🛑 Бот останавливается...")
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
