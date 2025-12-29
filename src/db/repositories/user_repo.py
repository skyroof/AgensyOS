"""
Репозиторий для работы с пользователями.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    """
    Получить пользователя или создать нового.
    
    Args:
        session: Сессия БД
        telegram_id: ID пользователя в Telegram
        username: Username
        first_name: Имя
        last_name: Фамилия
        
    Returns:
        Объект пользователя
    """
    # Ищем существующего (используем first() на случай дубликатов в БД)
    stmt = select(User).where(User.telegram_id == telegram_id).limit(1)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user:
        # Обновляем данные если изменились
        updated = False
        if username and user.username != username:
            user.username = username
            updated = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updated = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            updated = True
        
        if updated:
            await session.commit()
        
        return user
    
    # Создаём нового
    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Получить пользователя по Telegram ID."""
    stmt = select(User).where(User.telegram_id == telegram_id).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

