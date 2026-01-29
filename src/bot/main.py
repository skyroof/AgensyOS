"""
MAX Diagnostic Bot — точка входа.
"""
import asyncio
import logging
import sys

import sentry_sdk

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramServerError
from aiogram.fsm.storage.redis import RedisStorage

from src.core.config import get_settings
from src.bot.handlers import start, diagnostic, history, voice, pdp, settings, payments
from src.bot.middlewares.error_handler import ErrorHandlerMiddleware
from src.bot.middlewares.logging_middleware import LoggingMiddleware
from src.bot.scheduler import start_scheduler, stop_scheduler
from src.db import init_db, close_db


async def send_admin_alert(bot, message: str):
    """Отправить алерт админу."""
    config = get_settings()
    if not config.admin_telegram_id:
        return
        
    try:
        await bot.send_message(config.admin_telegram_id, f"🔔 <b>Bot Alert</b>\n\n{message}")
    except Exception:
        pass


async def main():
    """Запуск бота."""
    config = get_settings()
    
    # Sentry для мониторинга ошибок
    if config.sentry_dsn:
        sentry_sdk.init(
            dsn=config.sentry_dsn,
            send_default_pii=True,
            traces_sample_rate=0.1,
        )
    
    # Настройка логирования
    log_handler = logging.StreamHandler(sys.stdout)
    
    if config.log_format.lower() == "json":
        try:
            from pythonjsonlogger import jsonlogger
            formatter = jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s",
                rename_fields={"levelname": "level", "asctime": "timestamp"}
            )
            log_handler.setFormatter(formatter)
        except ImportError:
            pass

    if not log_handler.formatter:
        log_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))

    logging.basicConfig(
        level=getattr(logging, config.log_level),
        handlers=[log_handler],
        force=True,
    )
    # Понижаем уровень логов для aiogram, чтобы не спамить ERROR при временных сетевых ошибках
    logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    
    # Инициализация базы данных
    logger.info("🗄️ Инициализация базы данных...")
    await init_db()
    logger.info("🗄️ DB init done. Creating Bot...")
    
    # Инициализация бота
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("🤖 Bot created. Init Redis...")
    
    # Диспетчер с хранилищем состояний
    try:
        storage = RedisStorage.from_url(config.redis_url)
        # Проверка соединения с Redis
        logger.info("Checking Redis connection...")
        await storage.redis.ping()
        logger.info("✅ Подключено к Redis")
    except Exception as e:
        logger.warning(f"⚠️ Redis недоступен ({e}), используется MemoryStorage. Состояния сбросятся при перезапуске.")
        from aiogram.fsm.storage.memory import MemoryStorage
        storage = MemoryStorage()

    logger.info("Creating Dispatcher...")
    dp = Dispatcher(storage=storage)
    logger.info("Dispatcher created. Registering middlewares...")
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
    scheduler = start_scheduler(bot)
    logger.info("⏰ Планировщик напоминаний запущен")
    
    try:
        # Алерт о запуске (не блокируем основной поток)
        asyncio.create_task(send_admin_alert(bot, "✅ Бот успешно запущен на сервере!"))

        # Запуск polling с авто-реконнектом при сетевых ошибках
        retry_delay = 5
        logger.info("📡 Запуск polling...")
        while True:
            try:
                await dp.start_polling(bot)
                # Если start_polling вернул управление без ошибки — значит был штатный останов (например, SIGINT)
                break 
            except (TelegramNetworkError, TelegramServerError) as e:
                # Если это Bad Gateway или сетевая ошибка — просто ждем и пробуем снова
                level = logging.WARNING
                if isinstance(e, TelegramServerError) and "Bad Gateway" not in str(e):
                    level = logging.ERROR # Другие серверные ошибки логируем как ERROR
                
                logger.log(level, f"⚠️ Поллинг прерван ({type(e).__name__}): {e}. Повтор через {retry_delay}с...")
                await asyncio.sleep(retry_delay)
                # Экспоненциальный бэкофф до 60 секунд
                retry_delay = min(retry_delay * 2, 60)
            except Exception as e:
                logger.error(f"❌ Необработанная ошибка в цикле поллинга: {e}")
                await asyncio.sleep(5)
                retry_delay = 5
                
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        await send_admin_alert(bot, f"❌ Критическая ошибка:\n<code>{e}</code>")
        raise
    finally:
        stop_scheduler()
        await close_db()
        await bot.session.close()
        logger.info("🛑 Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
