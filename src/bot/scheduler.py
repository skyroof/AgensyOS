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
    get_pending_reminders_with_users,
    mark_reminder_sent,
    user_has_recent_diagnostic,
    cancel_stuck_reminders,
)
from src.db.repositories.user_repo import get_user_by_telegram_id
from src.db.models import User, DiagnosticSession


from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Интервал проверки (в секундах)
CHECK_INTERVAL = 60  # 1 минута (чаще для stuck reminders)

# Глобальный экземпляр планировщика
scheduler = AsyncIOScheduler()


def get_reminder_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для напоминания 30 дней."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎯 Пройти снова", callback_data="restart"),
    )
    builder.row(
        InlineKeyboardButton(text="⏰ Через неделю", callback_data=f"remind:postpone:{reminder_id}"),
        InlineKeyboardButton(text="🔕 Отписаться", callback_data=f"remind:unsubscribe:{reminder_id}"),
    )
    return builder.as_markup()


def get_stuck_reminder_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для зависшей диагностики."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="▶️ Продолжить", callback_data="continue_diagnostic"),
    )
    return builder.as_markup()


def format_reminder_text(
    last_score: int,
    focus_skill: Optional[str] = None,
    days_ago: int = 30,
) -> str:
    """Форматировать текст напоминания (30 дней)."""
    
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
            # Используем оптимизированный запрос с join
            reminders_data = await get_pending_reminders_with_users(db)
            
            if not reminders_data:
                # logger.debug("No pending reminders")
                return 0
            
            logger.info(f"Processing {len(reminders_data)} pending reminders")
            
            for reminder, telegram_id in reminders_data:
                try:
                    if not telegram_id:
                        logger.warning(f"User {reminder.user_id} has no telegram_id")
                        await mark_reminder_sent(db, reminder.id)
                        continue

                    # === STUCK REMINDERS ===
                    if reminder.reminder_type.startswith("stuck_"):
                        # Проверяем статус сессии
                        from sqlalchemy import select
                        session_stmt = select(DiagnosticSession).where(DiagnosticSession.id == reminder.session_id)
                        session_res = await db.execute(session_stmt)
                        diag_session = session_res.scalar_one_or_none()
                        
                        if not diag_session or diag_session.status != "in_progress":
                            # Сессия уже завершена или не найдена — отменяем напоминание
                            await mark_reminder_sent(db, reminder.id)
                            continue
                            
                        # Отправляем напоминание
                        await bot.send_message(
                            chat_id=telegram_id,
                            text=(
                                f"⏰ <b>Напоминание</b>\n\n"
                                f"Ты на вопросе {diag_session.current_question}/10.\n"
                                f"Можешь продолжить, когда будешь готов!\n\n"
                                f"<i>Если нужно время подумать — это нормально 😊</i>"
                            ),
                            # reply_markup=get_stuck_reminder_keyboard(), # Можно добавить кнопку
                        )
                        
                        await mark_reminder_sent(db, reminder.id)
                        sent_count += 1
                        logger.info(f"Sent stuck reminder to user {reminder.user_id}")
                        continue

                    # === 30 DAYS REMINDERS ===
                    # Проверяем, не прошёл ли пользователь диагностику недавно
                    if await user_has_recent_diagnostic(db, reminder.user_id, days=7):
                        logger.info(f"User {reminder.user_id} has recent diagnostic, skipping reminder")
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
    Wrapper для APScheduler job.
    """
    try:
        # Отправляем напоминания
        sent = await send_diagnostic_reminders(bot)
        if sent > 0:
            logger.info(f"Sent {sent} diagnostic reminders")
        
        # TODO: Добавить PDP daily reminders
        
    except Exception as e:
        logger.error(f"Scheduler error: {e}")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Запустить планировщик."""
    if scheduler.running:
        return scheduler
        
    scheduler.add_job(
        scheduler_loop,
        IntervalTrigger(seconds=CHECK_INTERVAL),
        args=[bot],
        id="diagnostic_reminders",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("Scheduler started (APScheduler)")
    return scheduler


def stop_scheduler():
    """Остановить планировщик."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")

