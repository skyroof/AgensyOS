"""
Репозиторий для работы с PDP 2.0.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import PdpPlan, PdpTask, PdpReminder, User


# ==================== PDP PLANS ====================


async def create_pdp_plan(
    session: AsyncSession,
    user_id: int,
    session_id: int,
    focus_skills: list[str],
    daily_time_minutes: int = 30,
    learning_style: str = "mixed",
) -> PdpPlan:
    """Создать новый план развития."""
    plan = PdpPlan(
        user_id=user_id,
        session_id=session_id,
        focus_skills={"skills": focus_skills},
        daily_time_minutes=daily_time_minutes,
        learning_style=learning_style,
        status="active",
        current_week=1,
        current_day=1,
        total_tasks=0,
        completed_tasks=0,
        skipped_tasks=0,
        current_streak=0,
        best_streak=0,
        total_points=0,
        badges={},
        started_at=datetime.utcnow(),
    )
    session.add(plan)
    await session.flush()
    return plan


async def create_and_fill_pdp_plan(
    session: AsyncSession,
    user_id: int,
    session_id: int,
    focus_skills: list[str],
    daily_time_minutes: int = 30,
    learning_style: str = "mixed",
) -> PdpPlan:
    """Создать план и наполнить его задачами."""
    from src.analytics.pdp_generator import generate_pdp_plan

    # 1. Создаём план
    plan = await create_pdp_plan(
        session, user_id, session_id, focus_skills, daily_time_minutes, learning_style
    )

    # 2. Генерируем контент
    pdp_content = generate_pdp_plan(focus_skills, daily_time_minutes, learning_style)

    # 3. Сохраняем задачи
    tasks_data = []
    order = 1

    for week in pdp_content.weeks:
        for day, daily_tasks in week.days.items():
            for task in daily_tasks:
                tasks_data.append(
                    {
                        "week": week.week_number,
                        "day": day,
                        "order": order,
                        "skill": task.skill,
                        "skill_name": task.skill_name,
                        "title": task.title,
                        "description": task.description,
                        "duration_minutes": task.duration_minutes,
                        "task_type": task.task_type,
                        "xp": task.xp,
                        "resource_type": task.resource_type,
                        "resource_title": task.resource_title,
                        "resource_url": task.resource_url,
                        "status": "pending",
                    }
                )
                order += 1

    await add_tasks_batch(session, plan.id, tasks_data)

    # Обновляем счетчик задач
    await update_pdp_progress(session, plan.id, total_tasks=len(tasks_data))

    return plan


async def get_active_pdp_plan(
    session: AsyncSession,
    user_id: int,
) -> Optional[PdpPlan]:
    """Получить активный план пользователя."""
    stmt = (
        select(PdpPlan)
        .where(PdpPlan.user_id == user_id)
        .where(PdpPlan.status == "active")
        .options(selectinload(PdpPlan.tasks))
        .order_by(PdpPlan.started_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_pdp_plan_by_id(
    session: AsyncSession,
    plan_id: int,
) -> Optional[PdpPlan]:
    """Получить план по ID."""
    stmt = (
        select(PdpPlan)
        .where(PdpPlan.id == plan_id)
        .options(selectinload(PdpPlan.tasks))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_pdp_progress(
    session: AsyncSession,
    plan_id: int,
    **kwargs,
) -> None:
    """Обновить прогресс плана."""
    stmt = (
        update(PdpPlan)
        .where(PdpPlan.id == plan_id)
        .values(last_activity_at=datetime.utcnow(), **kwargs)
    )
    await session.execute(stmt)


async def update_pdp_reflection(
    session: AsyncSession,
    plan_id: int,
    week_number: int,
    reflection_data: dict,
) -> None:
    """Обновить данные рефлексии в плане."""
    # Получаем текущий план
    stmt = select(PdpPlan).where(PdpPlan.id == plan_id)
    result = await session.execute(stmt)
    plan = result.scalar_one_or_none()

    if not plan:
        return

    # Обновляем JSON
    current_reflections = dict(plan.reflections) if plan.reflections else {}
    current_reflections[str(week_number)] = reflection_data

    # Сохраняем (используем update для явного изменения поля)
    stmt = (
        update(PdpPlan)
        .where(PdpPlan.id == plan_id)
        .values(reflections=current_reflections)
    )
    await session.execute(stmt)


async def complete_pdp_plan(
    session: AsyncSession,
    plan_id: int,
) -> None:
    """Завершить план."""
    stmt = (
        update(PdpPlan)
        .where(PdpPlan.id == plan_id)
        .values(
            status="completed",
            completed_at=datetime.utcnow(),
        )
    )
    await session.execute(stmt)


# ==================== PDP TASKS ====================


async def add_pdp_task(
    session: AsyncSession,
    plan_id: int,
    week: int,
    day: int,
    order: int,
    skill: str,
    skill_name: str,
    title: str,
    description: str,
    duration_minutes: int,
    task_type: str,
    xp: int = 10,
    resource_type: Optional[str] = None,
    resource_title: Optional[str] = None,
    resource_url: Optional[str] = None,
) -> PdpTask:
    """Добавить задачу в план."""
    task = PdpTask(
        plan_id=plan_id,
        week=week,
        day=day,
        order=order,
        skill=skill,
        skill_name=skill_name,
        title=title,
        description=description,
        duration_minutes=duration_minutes,
        task_type=task_type,
        xp=xp,
        resource_type=resource_type,
        resource_title=resource_title,
        resource_url=resource_url,
        status="pending",
    )
    session.add(task)
    await session.flush()
    return task


async def add_tasks_batch(
    session: AsyncSession,
    plan_id: int,
    tasks_data: list[dict],
) -> int:
    """Массовое добавление задач."""
    count = 0
    for data in tasks_data:
        task = PdpTask(plan_id=plan_id, **data)
        session.add(task)
        count += 1
    await session.flush()
    return count


async def get_tasks_for_day(
    session: AsyncSession,
    plan_id: int,
    week: int,
    day: int,
) -> list[PdpTask]:
    """Получить задачи на день."""
    stmt = (
        select(PdpTask)
        .where(PdpTask.plan_id == plan_id)
        .where(PdpTask.week == week)
        .where(PdpTask.day == day)
        .order_by(PdpTask.order)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_tasks_for_week(
    session: AsyncSession,
    plan_id: int,
    week: int,
) -> list[PdpTask]:
    """Получить все задачи недели."""
    stmt = (
        select(PdpTask)
        .where(PdpTask.plan_id == plan_id)
        .where(PdpTask.week == week)
        .order_by(PdpTask.day, PdpTask.order)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_task_by_id(
    session: AsyncSession,
    task_id: int,
) -> Optional[PdpTask]:
    """Получить задачу по ID."""
    stmt = select(PdpTask).where(PdpTask.id == task_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def complete_task(
    session: AsyncSession,
    task_id: int,
    note: Optional[str] = None,
) -> None:
    """Отметить задачу выполненной."""
    stmt = (
        update(PdpTask)
        .where(PdpTask.id == task_id)
        .values(
            status="completed",
            completed_at=datetime.utcnow(),
            user_note=note,
        )
    )
    await session.execute(stmt)


async def skip_task(
    session: AsyncSession,
    task_id: int,
    note: Optional[str] = None,
) -> None:
    """Пропустить задачу."""
    stmt = (
        update(PdpTask)
        .where(PdpTask.id == task_id)
        .values(
            status="skipped",
            user_note=note,
        )
    )
    await session.execute(stmt)


async def get_today_task(
    session: AsyncSession,
    plan_id: int,
) -> Optional[PdpTask]:
    """Получить сегодняшнюю задачу (первую незавершённую)."""
    plan = await get_pdp_plan_by_id(session, plan_id)
    if not plan:
        return None

    tasks = await get_tasks_for_day(
        session, plan_id, plan.current_week, plan.current_day
    )

    # Возвращаем первую незавершённую задачу (pending или sent)
    for task in tasks:
        if task.status in ["pending", "sent"]:
            return task

    return None


# ==================== STREAKS & GAMIFICATION ====================


async def update_streak(
    session: AsyncSession,
    plan_id: int,
    completed_today: bool,
) -> dict:
    """
    Обновить streak и вернуть результат.

    Returns:
        {"current_streak": int, "best_streak": int, "streak_broken": bool, "new_best": bool}
    """
    plan = await get_pdp_plan_by_id(session, plan_id)
    if not plan:
        return {
            "current_streak": 0,
            "best_streak": 0,
            "streak_broken": False,
            "new_best": False,
        }

    current = plan.current_streak
    best = plan.best_streak
    streak_broken = False
    new_best = False

    if completed_today:
        current += 1
        if current > best:
            best = current
            new_best = True
    else:
        if current > 0:
            streak_broken = True
        current = 0

    await update_pdp_progress(
        session,
        plan_id,
        current_streak=current,
        best_streak=best,
    )

    return {
        "current_streak": current,
        "best_streak": best,
        "streak_broken": streak_broken,
        "new_best": new_best,
    }


async def add_points(
    session: AsyncSession,
    plan_id: int,
    points: int,
) -> int:
    """Добавить очки и вернуть новый total."""
    plan = await get_pdp_plan_by_id(session, plan_id)
    if not plan:
        return 0

    new_total = plan.total_points + points
    await update_pdp_progress(session, plan_id, total_points=new_total)
    return new_total


async def add_badge(
    session: AsyncSession,
    plan_id: int,
    badge_id: str,
    badge_name: str,
) -> bool:
    """
    Добавить бейдж пользователю.

    Returns:
        True если бейдж новый, False если уже был
    """
    plan = await get_pdp_plan_by_id(session, plan_id)
    if not plan:
        return False

    badges = plan.badges or {}
    if badge_id in badges:
        return False

    badges[badge_id] = {
        "name": badge_name,
        "earned_at": datetime.utcnow().isoformat(),
    }
    
    # Важно: обновить словарь в БД
    stmt = (
        update(PdpPlan)
        .where(PdpPlan.id == plan_id)
        .values(badges=badges)
    )
    await session.execute(stmt)
    
    return True


async def get_pdp_stats(
    session: AsyncSession,
    plan_id: int,
) -> dict:
    """Получить статистику плана."""
    plan = await get_pdp_plan_by_id(session, plan_id)
    if not plan:
        return {}

    # Считаем задачи
    total = await session.scalar(
        select(select(PdpTask).where(PdpTask.plan_id == plan_id).count())
    )
    completed = await session.scalar(
        select(select(PdpTask).where(PdpTask.plan_id == plan_id).where(PdpTask.status == "completed").count())
    )

    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "completion_rate": int(completed / total * 100) if total > 0 else 0,
        "current_week": plan.current_week,
        "current_streak": plan.current_streak,
        "total_points": plan.total_points,
        "badges_count": len(plan.badges) if plan.badges else 0,
    }


async def get_or_create_reminder(
    session: AsyncSession,
    user_id: int,
) -> PdpReminder:
    """Получить или создать настройки напоминаний."""
    stmt = select(PdpReminder).where(PdpReminder.user_id == user_id)
    result = await session.execute(stmt)
    reminder = result.scalar_one_or_none()
    
    if not reminder:
        reminder = PdpReminder(user_id=user_id)
        session.add(reminder)
        await session.flush()
        
    return reminder


async def update_reminder_settings(
    session: AsyncSession,
    user_id: int,
    enabled: Optional[bool] = None,
    reminder_time: Optional[str] = None,
) -> None:
    """Обновить настройки напоминаний."""
    values = {}
    if enabled is not None:
        values["enabled"] = enabled
    if reminder_time is not None:
        values["reminder_time"] = reminder_time
        
    if not values:
        return

    stmt = (
        update(PdpReminder)
        .where(PdpReminder.user_id == user_id)
        .values(**values)
    )
    await session.execute(stmt)


async def get_active_plans_for_daily_push(session: AsyncSession) -> list[PdpPlan]:
    """Получить активные планы для рассылки."""
    now = datetime.utcnow()
    current_time = now.strftime("%H:%M")
    
    stmt = (
        select(PdpPlan)
        .join(PdpReminder, PdpPlan.user_id == PdpReminder.user_id)
        .where(PdpPlan.status == "active")
        .where(PdpReminder.enabled == True)
        .where(PdpReminder.reminder_time == current_time)
        .options(selectinload(PdpPlan.tasks))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def process_daily_transition(
    session: AsyncSession,
    plan_id: int,
    day_number: int,
) -> None:
    """Обработать переход на новый день."""
    week_number = (day_number - 1) // 7 + 1
    
    stmt = (
        update(PdpPlan)
        .where(PdpPlan.id == plan_id)
        .values(
            current_day=day_number,
            current_week=week_number,
        )
    )
    await session.execute(stmt)
