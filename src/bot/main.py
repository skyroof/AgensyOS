"""
Deep Diagnostic Bot — точка входа.
"""
import asyncio
import logging
import sys

import sentry_sdk

from aiogram import Bot, Dispatcher

# Sentry для мониторинга ошибок
sentry_sdk.init(
    dsn="https://e1fcaa6128a4bde0ad242461c6058ab2@o4510615985061888.ingest.de.sentry.io/4510615988404304",
    send_default_pii=True,
    traces_sample_rate=0.1,  # 10% трейсов для производительности
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from src.core.config import get_settings
from src.bot.handlers import start, diagnostic, history, voice, pdp, settings, payments
from src.bot.middlewares.error_handler import ErrorHandlerMiddleware
from src.bot.middlewares.logging_middleware import LoggingMiddleware
from src.bot.scheduler import start_scheduler
from src.db import init_db, close_db


ADMIN_ID = 785561885  # @laitnerbro — для алертов


async def send_admin_alert(bot, message: str):
    """Отправить алерт админу."""
    try:
        await bot.send_message(ADMIN_ID, f"🔔 <b>Bot Alert</b>\n\n{message}")
    except Exception:
        pass


async def main():
    """Запуск бота."""
    config = get_settings()
    
    # Настройка логирования
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)
    
    # Инициализация базы данных
    logger.info("🗄️ Инициализация базы данных...")
    await init_db()
    
    # Инициализация бота
    bot = Bot(
        token=config.bot_token,
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
    dp.include_router(payments.router)  # Платежи (до diagnostic!)
    dp.include_router(history.router)
    dp.include_router(pdp.router)  # PDP 2.0
    dp.include_router(settings.router)  # Настройки и напоминания
    dp.include_router(voice.router)  # Голосовые до diagnostic (для фильтрации)
    dp.include_router(diagnostic.router)
    
    # Запуск
    logger.info("🚀 Бот запускается...")
    logger.info(f"📡 AI Provider: {config.routerai_base_url}")
    logger.info(f"🤖 AI Model: {config.ai_model}")
    
    # Запуск планировщика напоминаний
    scheduler_task = start_scheduler(bot)
    logger.info("⏰ Планировщик напоминаний запущен")
    
    try:
        # Алерт о запуске
        await send_admin_alert(bot, "✅ Бот успешно запущен на сервере!")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        await send_admin_alert(bot, f"❌ Критическая ошибка:\n<code>{e}</code>")
        raise
    finally:
        logger.info("🛑 Бот останавливается...")
        scheduler_task.cancel()  # Останавливаем планировщик
        await send_admin_alert(bot, "🛑 Бот остановлен")
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
