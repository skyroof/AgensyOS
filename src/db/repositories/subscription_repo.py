from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import UserSubscription


async def get_or_create_subscription(
    session: AsyncSession, user_id: int
) -> UserSubscription:
    """Получить или создать запись о подписке."""
    result = await session.execute(
        select(UserSubscription).where(UserSubscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        subscription = UserSubscription(user_id=user_id)
        session.add(subscription)
        await session.flush()

    return subscription


async def activate_subscription(
    session: AsyncSession, user_id: int, days: int = 30
) -> UserSubscription:
    """
    Активировать или продлить подписку.

    Args:
        days: На сколько дней продлить
    """
    subscription = await get_or_create_subscription(session, user_id)

    now = datetime.utcnow()

    # Если подписка активна — продлеваем
    if subscription.is_active and subscription.end_date and subscription.end_date > now:
        subscription.end_date += timedelta(days=days)
    else:
        # Иначе активируем с текущего момента
        subscription.is_active = True
        subscription.start_date = now
        subscription.end_date = now + timedelta(days=days)

    subscription.updated_at = now
    await session.commit()
    return subscription


async def check_subscription(session: AsyncSession, user_id: int) -> bool:
    """Проверить, активна ли подписка."""
    subscription = await get_or_create_subscription(session, user_id)

    if not subscription.is_active:
        return False

    if subscription.end_date and subscription.end_date < datetime.utcnow():
        subscription.is_active = False
        await session.commit()
        return False

    return True
