"""
Планировщик задач для бота.

Отправляет:
- Напоминания о повторной диагностике (через 30 дней)
- Ежедневные задачи PDP
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.db import get_session
from src.db.repositories.reminder_repo import (
    get_pending_reminders,
    mark_reminder_sent,
    user_has_recent_diagnostic,
)
from src.db.repositories.user_repo import get_user_by_telegram_id
from src.db.models import User

logger = logging.getLogger(__name__)

# Интервал проверки (в секундах)
CHECK_INTERVAL = 3600  # 1 час


def get_reminder_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для напоминания."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎯 Пройти снова", callback_data="restart"),
    )
    builder.row(
        InlineKeyboardButton(text="⏰ Через неделю", callback_data=f"remind:postpone:{reminder_id}"),
        InlineKeyboardButton(text="🔕 Отписаться", callback_data=f"remind:unsubscribe:{reminder_id}"),
    )
    return builder.as_markup()


def format_reminder_text(
    last_score: int,
    focus_skill: Optional[str] = None,
    days_ago: int = 30,
) -> str:
    """Форматировать текст напоминания."""
    
    text = f"""👋 <b>Привет!</b>

Прошло {days_ago} дней с твоей последней диагностики.

📊 <b>Твой результат тогда:</b> {last_score}/100

За это время ты мог:
✅ Прокачать слабые зоны
✅ Закрепить сильные стороны
✅ Получить новый опыт"""
    
    if focus_skill:
        text += f"\n\n🎯 <b>Твоя зона роста:</b> {focus_skill}"
        text += "\nПроверим, есть ли прогресс?"
    
    text += "\n\n<b>Готов увидеть свой рост?</b> 🚀"
    
    return text


async def send_diagnostic_reminders(bot: Bot) -> int:
    """
    Отправить запланированные напоминания о диагностике.
    
    Returns:
        Количество отправленных напоминаний
    """
    sent_count = 0
    
    try:
        async with get_session() as db:
            reminders = await get_pending_reminders(db)
            
            if not reminders:
                logger.debug("No pending reminders")
                return 0
            
            logger.info(f"Processing {len(reminders)} pending reminders")
            
            for reminder in reminders:
                try:
                    # Проверяем, не прошёл ли пользователь диагностику недавно
                    if await user_has_recent_diagnostic(db, reminder.user_id, days=7):
                        logger.info(f"User {reminder.user_id} has recent diagnostic, skipping reminder")
                        await mark_reminder_sent(db, reminder.id)
                        continue
                    
                    # Получаем telegram_id
                    from sqlalchemy import select
                    from src.db.models import User
                    
                    stmt = select(User.telegram_id).where(User.id == reminder.user_id)
                    result = await db.execute(stmt)
                    telegram_id = result.scalar_one_or_none()
                    
                    if not telegram_id:
                        logger.warning(f"User {reminder.user_id} not found")
                        await mark_reminder_sent(db, reminder.id)
                        continue
                    
                    # Считаем дни с последней диагностики
                    days_ago = (datetime.utcnow() - reminder.created_at).days
                    
                    # Форматируем текст
                    text = format_reminder_text(
                        last_score=reminder.last_score or 0,
                        focus_skill=reminder.focus_skill,
                        days_ago=days_ago,
                    )
                    
                    # Отправляем
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=text,
                        reply_markup=get_reminder_keyboard(reminder.id),
                    )
                    
                    await mark_reminder_sent(db, reminder.id)
                    sent_count += 1
                    
                    logger.info(f"Sent reminder to user {reminder.user_id}")
                    
                    # Небольшая задержка между сообщениями
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Failed to send reminder {reminder.id}: {e}")
                    continue
            
            await db.commit()
    
    except Exception as e:
        logger.error(f"Error in send_diagnostic_reminders: {e}")
    
    return sent_count


async def scheduler_loop(bot: Bot):
    """
    Основной цикл планировщика.
    
    Запускается как фоновая задача при старте бота.
    """
    logger.info("Scheduler started")
    
    while True:
        try:
            # Отправляем напоминания
            sent = await send_diagnostic_reminders(bot)
            if sent > 0:
                logger.info(f"Sent {sent} diagnostic reminders")
            
            # TODO: Добавить PDP daily reminders
            
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        
        # Ждём до следующей проверки
        await asyncio.sleep(CHECK_INTERVAL)


def start_scheduler(bot: Bot) -> asyncio.Task:
    """Запустить планировщик как фоновую задачу."""
    return asyncio.create_task(scheduler_loop(bot))

