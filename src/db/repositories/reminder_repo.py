"""
Репозиторий для работы с напоминаниями о диагностике.
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import DiagnosticReminder, UserSettings, DiagnosticSession, User, TaskReminder, PdpTask


# ==================== TASK REMINDERS ====================


async def schedule_task_reminder(
    session: AsyncSession,
    user_id: int,
    task_id: int,
    reminder_time: datetime,
) -> TaskReminder:
    """Запланировать напоминание о задаче PDP."""
    reminder = TaskReminder(
        user_id=user_id,
        task_id=task_id,
        scheduled_at=reminder_time,
        sent=False,
    )
    session.add(reminder)
    await session.flush()
    return reminder


async def get_pending_task_reminders(
    session: AsyncSession,
) -> list[TaskReminder]:
    """Получить задачи, о которых пора напомнить."""
    now = datetime.utcnow()
    stmt = (
        select(TaskReminder)
        .options(selectinload(TaskReminder.task), selectinload(TaskReminder.user))  # Подгружаем задачу и юзера
        .where(TaskReminder.sent.is_(False))
        .where(TaskReminder.scheduled_at <= now)
        .limit(100)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def mark_task_reminder_sent(
    session: AsyncSession,
    reminder_id: int,
) -> None:
    """Отметить напоминание как отправленное."""
    stmt = (
        update(TaskReminder)
        .where(TaskReminder.id == reminder_id)
        .values(sent=True)
    )
    await session.execute(stmt)


# ==================== DIAGNOSTIC REMINDERS ====================


async def schedule_diagnostic_reminder(
    session: AsyncSession,
    user_id: int,
    session_id: int,
    last_score: int,
    focus_skill: Optional[str] = None,
    days_delay: int = 30,
) -> DiagnosticReminder:
    """
    Запланировать напоминание о повторной диагностике.

    По умолчанию через 30 дней после завершения.
    """
    scheduled_at = datetime.utcnow() + timedelta(days=days_delay)

    reminder = DiagnosticReminder(
        user_id=user_id,
        session_id=session_id,
        scheduled_at=scheduled_at,
        reminder_type=f"{days_delay}_days",
        last_score=last_score,
        focus_skill=focus_skill,
        sent=False,
        cancelled=False,
    )
    session.add(reminder)
    await session.flush()
    return reminder


async def schedule_smart_reminder(
    session: AsyncSession,
    user_id: int,
    session_id: int,
    hours_delay: int = 24,
) -> DiagnosticReminder:
    """
    Запланировать умное напоминание (через 24ч).
    """
    scheduled_at = datetime.utcnow() + timedelta(hours=hours_delay)

    reminder = DiagnosticReminder(
        user_id=user_id,
        session_id=session_id,
        scheduled_at=scheduled_at,
        reminder_type=f"smart_{hours_delay}h",
        sent=False,
        cancelled=False,
    )
    session.add(reminder)
    await session.flush()
    return reminder


async def schedule_stuck_reminder(
    session: AsyncSession,
    user_id: int,
    session_id: int,
    minutes_delay: int = 5,
) -> DiagnosticReminder:
    """
    Запланировать напоминание о зависшей диагностике.
    """
    scheduled_at = datetime.utcnow() + timedelta(minutes=minutes_delay)

    reminder = DiagnosticReminder(
        user_id=user_id,
        session_id=session_id,
        scheduled_at=scheduled_at,
        reminder_type=f"stuck_{minutes_delay}min",
        sent=False,
        cancelled=False,
    )
    session.add(reminder)
    await session.flush()
    return reminder


async def cancel_stuck_reminders(
    session: AsyncSession,
    user_id: int,
    session_id: int,
) -> None:
    """Отменить все stuck-напоминания для сессии (когда юзер ответил)."""
    stmt = (
        update(DiagnosticReminder)
        .where(DiagnosticReminder.user_id == user_id)
        .where(DiagnosticReminder.session_id == session_id)
        .where(DiagnosticReminder.reminder_type.like("stuck_%"))
        .where(DiagnosticReminder.sent.is_(False))
        .where(DiagnosticReminder.cancelled.is_(False))
        .values(cancelled=True)
    )
    await session.execute(stmt)


async def get_pending_reminders_with_users(
    session: AsyncSession,
    before: Optional[datetime] = None,
) -> list[tuple[DiagnosticReminder, int]]:
    """
    Получить напоминания вместе с telegram_id пользователей.

    Возвращает список кортежей (reminder, telegram_id).
    """
    if before is None:
        before = datetime.utcnow()

    stmt = (
        select(DiagnosticReminder, User.telegram_id)
        .join(User, DiagnosticReminder.user_id == User.id)
        .where(DiagnosticReminder.scheduled_at <= before)
        .where(DiagnosticReminder.sent.is_(False))
        .where(DiagnosticReminder.cancelled.is_(False))
        .order_by(DiagnosticReminder.scheduled_at)
        .limit(100)
    )
    result = await session.execute(stmt)
    return list(result.all())


async def get_pending_reminders(
    session: AsyncSession,
    before: Optional[datetime] = None,
) -> list[DiagnosticReminder]:
    """
    Получить напоминания, которые нужно отправить.

    Возвращает напоминания где:
    - scheduled_at <= before (или now)
    - sent = False
    - cancelled = False
    """
    if before is None:
        before = datetime.utcnow()

    stmt = (
        select(DiagnosticReminder)
        .where(DiagnosticReminder.scheduled_at <= before)
        .where(DiagnosticReminder.sent.is_(False))
        .where(DiagnosticReminder.cancelled.is_(False))
        .order_by(DiagnosticReminder.scheduled_at)
        .limit(100)  # Batch limit
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_reminder_sent(
    session: AsyncSession,
    reminder_id: int,
) -> None:
    """Отметить напоминание как отправленное."""
    stmt = (
        update(DiagnosticReminder)
        .where(DiagnosticReminder.id == reminder_id)
        .values(sent=True, sent_at=datetime.utcnow())
    )
    await session.execute(stmt)


async def cancel_reminder(
    session: AsyncSession,
    reminder_id: int,
) -> None:
    """Отменить напоминание."""
    stmt = (
        update(DiagnosticReminder)
        .where(DiagnosticReminder.id == reminder_id)
        .values(cancelled=True)
    )
    await session.execute(stmt)


async def postpone_reminder(
    session: AsyncSession,
    reminder_id: int,
    days: int = 7,
) -> None:
    """Отложить напоминание на N дней."""
    new_time = datetime.utcnow() + timedelta(days=days)
    stmt = (
        update(DiagnosticReminder)
        .where(DiagnosticReminder.id == reminder_id)
        .values(scheduled_at=new_time, reminder_type=f"postponed_{days}")
    )
    await session.execute(stmt)


async def get_user_pending_reminder(
    session: AsyncSession,
    user_id: int,
) -> Optional[DiagnosticReminder]:
    """Получить активное напоминание пользователя."""
    stmt = (
        select(DiagnosticReminder)
        .where(DiagnosticReminder.user_id == user_id)
        .where(DiagnosticReminder.sent.is_(False))
        .where(DiagnosticReminder.cancelled.is_(False))
        .order_by(DiagnosticReminder.scheduled_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def cancel_user_reminders(
    session: AsyncSession,
    user_id: int,
) -> int:
    """Отменить все напоминания пользователя. Возвращает количество."""
    stmt = (
        update(DiagnosticReminder)
        .where(DiagnosticReminder.user_id == user_id)
        .where(DiagnosticReminder.sent.is_(False))
        .where(DiagnosticReminder.cancelled.is_(False))
        .values(cancelled=True)
    )
    result = await session.execute(stmt)
    return result.rowcount


async def user_has_recent_diagnostic(
    session: AsyncSession,
    user_id: int,
    days: int = 7,
) -> bool:
    """
    Проверить, проходил ли пользователь диагностику недавно.

    Используется для умных напоминаний — не отправлять если уже прошёл.
    """
    threshold = datetime.utcnow() - timedelta(days=days)

    stmt = (
        select(DiagnosticSession.id)
        .where(DiagnosticSession.user_id == user_id)
        .where(DiagnosticSession.status == "completed")
        .where(DiagnosticSession.completed_at >= threshold)
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


# ==================== USER SETTINGS ====================


async def get_or_create_user_settings(
    session: AsyncSession,
    user_id: int,
) -> UserSettings:
    """Получить или создать настройки пользователя."""
    stmt = select(UserSettings).where(UserSettings.user_id == user_id)
    result = await session.execute(stmt)
    settings = result.scalar_one_or_none()

    if not settings:
        settings = UserSettings(
            user_id=user_id,
            diagnostic_reminders_enabled=True,
            pdp_reminders_enabled=True,
        )
        session.add(settings)
        await session.flush()

    return settings


async def update_user_settings(
    session: AsyncSession,
    user_id: int,
    **kwargs,
) -> None:
    """Обновить настройки пользователя."""
    # Сначала убедимся что settings существует
    await get_or_create_user_settings(session, user_id)

    kwargs["updated_at"] = datetime.utcnow()

    stmt = update(UserSettings).where(UserSettings.user_id == user_id).values(**kwargs)
    await session.execute(stmt)


async def get_users_with_reminders_enabled(
    session: AsyncSession,
) -> list[int]:
    """Получить telegram_id пользователей с включенными напоминаниями."""
    stmt = (
        select(User.telegram_id)
        .join(UserSettings, UserSettings.user_id == User.id)
        .where(UserSettings.diagnostic_reminders_enabled.is_(True))
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]
