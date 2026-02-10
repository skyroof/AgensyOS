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
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.db import get_session
from src.db.repositories.reminder_repo import (
    get_pending_reminders_with_users,
    mark_reminder_sent,
    user_has_recent_diagnostic,
    get_pending_task_reminders,
    mark_task_reminder_sent,
)
from src.db.models import DiagnosticSession


from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.services.digest_service import send_weekly_digests

logger = logging.getLogger(__name__)

# Интервал проверки (в секундах)
CHECK_INTERVAL = 60  # 1 минута (чаще для stuck reminders)
DIGEST_INTERVAL = 3600  # 1 час

# Глобальный экземпляр планировщика
scheduler = AsyncIOScheduler()


def get_reminder_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для напоминания 30 дней."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎯 Пройти снова", callback_data="restart"),
    )
    builder.row(
        InlineKeyboardButton(
            text="⏰ Через неделю", callback_data=f"remind:postpone:{reminder_id}"
        ),
        InlineKeyboardButton(
            text="🔕 Отписаться", callback_data=f"remind:unsubscribe:{reminder_id}"
        ),
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

                        session_stmt = select(DiagnosticSession).where(
                            DiagnosticSession.id == reminder.session_id
                        )
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

                    # === SMART REMINDERS (24h Provocation) ===
                    if reminder.reminder_type.startswith("smart_"):
                        # Провокация через 24 часа после диагностики
                        # Цель: вернуть пользователя в контекст и предложить PDP (если нет)

                        # Проверяем, есть ли активная подписка (если есть, то этот ремайндер может быть лишним, но оставим как engagement)
                        # Для простоты шлем всем

                        text = """🤔 <b>Мы тут подумали...</b>

Прошли сутки после твоей диагностики. Результаты уже улеглись в голове?

Обычно в этот момент возникает вопрос: <i>"И что теперь с этим делать?"</i>

У нас есть ответ: <b>Персональный План Развития (PDP)</b>.
Это 15 минут в день, которые превратят твои зоны роста в супер-силы.

Готов попробовать?"""

                        keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="🚀 Создать мой план",
                                        callback_data="start_pdp_setup",
                                    )
                                ]
                            ]
                        )

                        await bot.send_message(
                            chat_id=telegram_id,
                            text=text,
                            reply_markup=keyboard,
                            parse_mode="HTML",
                        )

                        await mark_reminder_sent(db, reminder.id)
                        sent_count += 1
                        logger.info(f"Sent smart reminder to user {reminder.user_id}")
                        continue

                    # === 30 DAYS REMINDERS ===
                    # Проверяем, не прошёл ли пользователь диагностику недавно
                    if await user_has_recent_diagnostic(db, reminder.user_id, days=7):
                        logger.info(
                            f"User {reminder.user_id} has recent diagnostic, skipping reminder"
                        )
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

                except TelegramForbiddenError:
                    logger.warning(f"User {reminder.user_id} blocked bot. Marking reminder {reminder.id} as sent.")
                    await mark_reminder_sent(db, reminder.id)
                except Exception as e:
                    logger.error(f"Failed to send reminder {reminder.id}: {e}")
                    continue

            await db.commit()

    except Exception as e:
        logger.error(f"Error in send_diagnostic_reminders: {e}")

    return sent_count


async def send_daily_pdp_tasks(bot: Bot) -> int:
    """
    Рассылка ежедневных заданий PDP.
    """
    from src.db.repositories import pdp_repo
    from src.db import get_session

    sent_count = 0

    try:
        async with get_session() as session:
            plans = await pdp_repo.get_active_plans_for_daily_push(session)

            for plan in plans:
                try:
                    # Обновляем текущий день на основе времени старта
                    days_since_start = (datetime.utcnow() - plan.started_at).days + 1

                    if days_since_start > 30:
                        # План закончился - нужно завершить
                        await pdp_repo.complete_pdp_plan(session, plan.id)
                        continue

                    # Если день изменился, обрабатываем переход
                    if days_since_start > plan.current_day:
                        await pdp_repo.process_daily_transition(
                            session, plan.id, days_since_start
                        )
                        # Перезагружаем план, чтобы получить актуальные данные (например, стрик)
                        # В данном цикле это не обязательно, но полезно для консистентности

                    # Получаем задачу на сегодня
                    task = await pdp_repo.get_today_task(session, plan.id)
                    if not task:
                        continue

                    # Если статус не pending (значит уже отправляли или выполнена) - пропускаем
                    if task.status != "pending":
                        continue

                    # Формируем сообщение
                    text = f"""📅 <b>Твой план на сегодня (День {days_since_start})</b>
            
🎯 <b>{task.title}</b>
<i>{task.skill_name} • {task.duration_minutes} мин</i>

{task.description}"""

                    if task.resource_url:
                        text += f"\n\n🔗 <a href='{task.resource_url}'>{task.resource_title or 'Материал'}</a>"

                    # Кнопка "Я сделал"
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="✅ Я сделал (+10 XP)",
                                    callback_data=f"pdp:done:{task.id}:{plan.id}",
                                )
                            ],
                            [
                                InlineKeyboardButton(
                                    text="⏭ Пропустить",
                                    callback_data=f"pdp:skip:{task.id}:{plan.id}",
                                )
                            ],
                        ]
                    )

                    await bot.send_message(
                        plan.user.telegram_id, text, reply_markup=keyboard, parse_mode="HTML"
                    )

                    # Обновляем статус на sent (чтобы не слать повторно)
                    # Используем execute напрямую, так как в репозитории нет update_status
                    from sqlalchemy import update
                    from src.db.models import PdpTask

                    await session.execute(
                        update(PdpTask)
                        .where(PdpTask.id == task.id)
                        .values(status="sent")
                    )
                    await session.commit()

                    sent_count += 1

                except TelegramForbiddenError:
                    logger.warning(f"User {plan.user_id} blocked bot. Skipping PDP task.")
                    # Mark as sent to avoid retry
                    await session.execute(
                        update(PdpTask)
                        .where(PdpTask.id == task.id)
                        .values(status="sent")
                    )
                    await session.commit()

                except Exception as e:
                    logger.error(f"Failed to send PDP task to user {plan.user.telegram_id} (id={plan.user_id}): {e}")

    except Exception as e:
        logger.error(f"PDP Scheduler error: {e}")

    return sent_count


async def send_task_reminders(bot: Bot) -> int:
    """
    Отправка конкретных напоминаний о задачах (Remind Later).
    """
    sent_count = 0
    try:
        async with get_session() as db:
            reminders = await get_pending_task_reminders(db)
            
            for reminder in reminders:
                try:
                    task = reminder.task
                    if not reminder.user or not reminder.user.telegram_id:
                        await mark_task_reminder_sent(db, reminder.id)
                        continue
                        
                    telegram_id = reminder.user.telegram_id
                    
                    text = f"""⏰ <b>Напоминание о задаче</b>
                    
🎯 <b>{task.title}</b>
<i>{task.skill_name}</i>

{task.description[:200]}{'...' if len(task.description) > 200 else ''}

<i>Ты просил напомнить. Готов сделать?</i>"""

                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="👀 Открыть задачу", callback_data=f"pdp:view_task:{task.id}:{task.plan_id}")],
                            [InlineKeyboardButton(text="✅ Сделано", callback_data=f"pdp:done:{task.id}:{task.plan_id}")]
                        ]
                    )
                    
                    await bot.send_message(chat_id=telegram_id, text=text, reply_markup=keyboard)
                    
                    await mark_task_reminder_sent(db, reminder.id)
                    sent_count += 1
                    
                except TelegramForbiddenError:
                    logger.warning(f"User {reminder.user_id} blocked bot. Marking task reminder {reminder.id} as sent.")
                    await mark_task_reminder_sent(db, reminder.id)

                except Exception as e:
                    logger.error(f"Failed to send task reminder {reminder.id}: {e}")
                    # If user blocked bot, mark as sent to avoid loop
                    if "Forbidden" in str(e) or "blocked" in str(e):
                         await mark_task_reminder_sent(db, reminder.id)

            await db.commit()
            
    except Exception as e:
        logger.error(f"Error in send_task_reminders: {e}")
        
    return sent_count


async def scheduler_loop(bot: Bot):
    """Основной цикл планировщика."""
    logger.info("Scheduler tick...")

    # 1. Напоминания о диагностике
    await send_diagnostic_reminders(bot)

    # 2. Daily PDP tasks
    await send_daily_pdp_tasks(bot)
    
    # 3. Task Reminders (Remind Later)
    await send_task_reminders(bot)


async def run_weekly_digest_job(bot: Bot):
    """Запуск рассылки дайджеста."""
    try:
        async with get_session() as session:
            await send_weekly_digests(session, bot)
    except Exception as e:
        logger.error(f"Error in weekly digest job: {e}")


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

    # Еженедельный дайджест (проверка раз в час)
    scheduler.add_job(
        run_weekly_digest_job,
        IntervalTrigger(seconds=DIGEST_INTERVAL),
        args=[bot],
        id="weekly_digest",
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
