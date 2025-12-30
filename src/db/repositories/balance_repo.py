"""
Репозиторий для работы с балансом диагностик.

Pay-per-Diagnostic модель:
- Demo: бесплатно, 1 раз, 3 вопроса
- Single/Pack3/Pack10: платные полные диагностики
"""
from datetime import datetime
from typing import Optional, NamedTuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import UserBalance, Payment, Promocode, PromocodeUse


class DiagnosticAccess(NamedTuple):
    """Результат проверки доступа к диагностике."""
    allowed: bool
    mode: Optional[str]  # "demo" | "full" | None
    balance: int
    demo_used: bool


# Цены пакетов (в копейках)
PACK_PRICES = {
    "single": 29900,   # 299₽
    "pack3": 69900,    # 699₽
    "pack10": 199000,  # 1990₽
}

PACK_COUNTS = {
    "single": 1,
    "pack3": 3,
    "pack10": 10,
}


async def get_or_create_balance(session: AsyncSession, user_id: int) -> UserBalance:
    """Получить или создать баланс пользователя."""
    result = await session.execute(
        select(UserBalance).where(UserBalance.user_id == user_id)
    )
    balance = result.scalar_one_or_none()
    
    if not balance:
        balance = UserBalance(user_id=user_id)
        session.add(balance)
        await session.commit()
        await session.refresh(balance)
    
    return balance


async def get_user_balance(session: AsyncSession, user_id: int) -> UserBalance:
    """Получить баланс пользователя (создаёт если нет)."""
    return await get_or_create_balance(session, user_id)


async def check_diagnostic_access(session: AsyncSession, user_id: int) -> DiagnosticAccess:
    """
    Проверить доступ к диагностике.
    
    Возвращает:
    - allowed: можно ли начать диагностику
    - mode: "demo" или "full"
    - balance: текущий баланс
    - demo_used: использовано ли демо
    """
    balance = await get_or_create_balance(session, user_id)
    
    # Есть оплаченные диагностики?
    if balance.diagnostics_balance > 0:
        return DiagnosticAccess(
            allowed=True,
            mode="full",
            balance=balance.diagnostics_balance,
            demo_used=balance.demo_used,
        )
    
    # Демо ещё не использовано?
    if not balance.demo_used:
        return DiagnosticAccess(
            allowed=True,
            mode="demo",
            balance=0,
            demo_used=False,
        )
    
    # Нет доступа
    return DiagnosticAccess(
        allowed=False,
        mode=None,
        balance=0,
        demo_used=True,
    )


async def use_diagnostic(session: AsyncSession, user_id: int, mode: str) -> bool:
    """
    Списать диагностику с баланса.
    
    Args:
        user_id: ID пользователя
        mode: "demo" или "full"
        
    Returns:
        True если успешно списано
    """
    balance = await get_or_create_balance(session, user_id)
    
    if mode == "demo":
        if balance.demo_used:
            return False
        balance.demo_used = True
        balance.total_used += 1
        balance.updated_at = datetime.utcnow()
        await session.commit()
        return True
    
    elif mode == "full":
        if balance.diagnostics_balance <= 0:
            return False
        balance.diagnostics_balance -= 1
        balance.total_used += 1
        balance.updated_at = datetime.utcnow()
        await session.commit()
        return True
    
    return False


async def add_diagnostics(
    session: AsyncSession, 
    user_id: int, 
    count: int,
    payment_id: Optional[int] = None
) -> UserBalance:
    """
    Добавить диагностики на баланс (после оплаты).
    
    Args:
        user_id: ID пользователя
        count: Количество диагностик
        payment_id: ID платежа (опционально)
    """
    balance = await get_or_create_balance(session, user_id)
    
    balance.diagnostics_balance += count
    balance.total_purchased += count
    balance.updated_at = datetime.utcnow()
    
    await session.commit()
    await session.refresh(balance)
    
    return balance


async def mark_demo_used(session: AsyncSession, user_id: int) -> None:
    """Отметить демо как использованное."""
    balance = await get_or_create_balance(session, user_id)
    balance.demo_used = True
    balance.updated_at = datetime.utcnow()
    await session.commit()


# ==================== ПРОМОКОДЫ ====================

async def get_promocode(session: AsyncSession, code: str) -> Optional[Promocode]:
    """Получить промокод по коду."""
    result = await session.execute(
        select(Promocode).where(Promocode.code == code.upper().strip())
    )
    return result.scalar_one_or_none()


async def validate_promocode(
    session: AsyncSession, 
    code: str, 
    pack_type: str,
    user_id: int
) -> tuple[bool, str, Optional[Promocode]]:
    """
    Валидировать промокод.
    
    Returns:
        (valid, error_message, promocode)
    """
    promo = await get_promocode(session, code)
    
    if not promo:
        return False, "Промокод не найден", None
    
    if not promo.is_active:
        return False, "Промокод недействителен", None
    
    # Проверить срок действия
    now = datetime.utcnow()
    if promo.valid_from and now < promo.valid_from:
        return False, "Промокод ещё не активен", None
    if promo.valid_until and now > promo.valid_until:
        return False, "Промокод истёк", None
    
    # Проверить лимит использований
    if promo.max_uses and promo.current_uses >= promo.max_uses:
        return False, "Лимит использований исчерпан", None
    
    # Проверить применимость к пакету
    if promo.applicable_packs and pack_type not in promo.applicable_packs:
        return False, f"Промокод не применим к пакету {pack_type}", None
    
    # Проверить не использовал ли уже этот пользователь
    result = await session.execute(
        select(PromocodeUse).where(
            PromocodeUse.promocode_id == promo.id,
            PromocodeUse.user_id == user_id
        )
    )
    if result.scalar_one_or_none():
        return False, "Ты уже использовал этот промокод", None
    
    return True, "", promo


def calculate_discount(promo: Promocode, original_price: int) -> int:
    """
    Рассчитать скидку.
    
    Returns:
        Размер скидки в копейках
    """
    if promo.discount_percent > 0:
        return int(original_price * promo.discount_percent / 100)
    elif promo.discount_amount > 0:
        return min(promo.discount_amount, original_price)
    return 0


async def apply_promocode(
    session: AsyncSession,
    promo: Promocode,
    user_id: int,
    payment_id: int,
    discount_applied: int
) -> PromocodeUse:
    """
    Применить промокод (записать использование).
    """
    # Увеличить счётчик
    promo.current_uses += 1
    
    # Записать использование
    use = PromocodeUse(
        promocode_id=promo.id,
        user_id=user_id,
        payment_id=payment_id,
        discount_applied=discount_applied,
    )
    session.add(use)
    await session.commit()
    
    return use


async def create_promocode(
    session: AsyncSession,
    code: str,
    discount_percent: int = 0,
    discount_amount: int = 0,
    max_uses: Optional[int] = None,
    valid_until: Optional[datetime] = None,
    applicable_packs: Optional[list] = None,
    description: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Promocode:
    """Создать новый промокод."""
    promo = Promocode(
        code=code.upper().strip(),
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        max_uses=max_uses,
        valid_until=valid_until,
        applicable_packs=applicable_packs,
        description=description,
        created_by=created_by,
    )
    session.add(promo)
    await session.commit()
    await session.refresh(promo)
    return promo


# ==================== ПЛАТЕЖИ ====================

async def create_payment(
    session: AsyncSession,
    user_id: int,
    pack_type: str,
    promo: Optional[Promocode] = None,
) -> Payment:
    """Создать запись о платеже (pending)."""
    original_price = PACK_PRICES[pack_type]
    discount = calculate_discount(promo, original_price) if promo else 0
    final_price = max(0, original_price - discount)
    
    payment = Payment(
        user_id=user_id,
        pack_type=pack_type,
        diagnostics_count=PACK_COUNTS[pack_type],
        amount=original_price,
        discount_amount=discount,
        final_amount=final_price,
        promocode_id=promo.id if promo else None,
        status="pending",
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    
    return payment


async def complete_payment(
    session: AsyncSession,
    payment_id: int,
    telegram_payment_charge_id: str,
    provider_payment_charge_id: str,
) -> Payment:
    """Завершить платёж (success)."""
    result = await session.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    payment = result.scalar_one()
    
    payment.status = "success"
    payment.telegram_payment_charge_id = telegram_payment_charge_id
    payment.provider_payment_charge_id = provider_payment_charge_id
    payment.completed_at = datetime.utcnow()
    
    await session.commit()
    await session.refresh(payment)
    
    return payment


async def get_payment(session: AsyncSession, payment_id: int) -> Optional[Payment]:
    """Получить платёж по ID."""
    result = await session.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    return result.scalar_one_or_none()


async def get_user_payments(session: AsyncSession, user_id: int) -> list[Payment]:
    """Получить все платежи пользователя."""
    result = await session.execute(
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
    )
    return list(result.scalars().all())


# ==================== СТАТИСТИКА ====================

async def get_balance_stats(session: AsyncSession) -> dict:
    """Статистика по балансам (для админа)."""
    from sqlalchemy import func
    
    # Всего пользователей с балансом
    total_users = await session.execute(
        select(func.count(UserBalance.id))
    )
    
    # Использовали демо
    demo_used = await session.execute(
        select(func.count(UserBalance.id)).where(UserBalance.demo_used == True)
    )
    
    # Купили хоть раз
    paid_users = await session.execute(
        select(func.count(UserBalance.id)).where(UserBalance.total_purchased > 0)
    )
    
    # Всего куплено диагностик
    total_purchased = await session.execute(
        select(func.sum(UserBalance.total_purchased))
    )
    
    # Сумма платежей
    total_revenue = await session.execute(
        select(func.sum(Payment.final_amount)).where(Payment.status == "success")
    )
    
    return {
        "total_users": total_users.scalar() or 0,
        "demo_used": demo_used.scalar() or 0,
        "paid_users": paid_users.scalar() or 0,
        "total_purchased": total_purchased.scalar() or 0,
        "total_revenue": (total_revenue.scalar() or 0) / 100,  # В рублях
    }

