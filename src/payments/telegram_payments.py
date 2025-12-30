"""
Telegram Payments API.

Интеграция с CloudPayments через встроенные платежи Telegram.
"""
import json
import logging
from typing import Optional

from aiogram import Bot
from aiogram.types import LabeledPrice, Message

from src.core.config import get_settings


logger = logging.getLogger(__name__)

# Цены пакетов (в копейках)
PACK_PRICES = {
    "single": 29900,   # 299₽
    "pack3": 69900,    # 699₽
    "pack10": 199000,  # 1990₽
}

# Количество диагностик в пакете
PACK_COUNTS = {
    "single": 1,
    "pack3": 3,
    "pack10": 10,
}

# Названия пакетов
PACK_NAMES = {
    "single": "Одна диагностика",
    "pack3": "Пакет 3 диагностики",
    "pack10": "Пакет 10 диагностик",
}

# Описания пакетов
PACK_DESCRIPTIONS = {
    "single": "Полная диагностика: 10 вопросов, PDF-отчёт, план развития",
    "pack3": "3 полные диагностики для отслеживания прогресса (-22%)",
    "pack10": "10 диагностик для команды или активного развития (-33%)",
}


def create_invoice_payload(
    user_id: int,
    pack_type: str,
    payment_id: int,
    promocode: Optional[str] = None,
) -> str:
    """
    Создать payload для invoice.
    
    Payload сохраняется в Telegram и возвращается при успешной оплате.
    """
    payload = {
        "user_id": user_id,
        "pack_type": pack_type,
        "payment_id": payment_id,
        "promocode": promocode,
    }
    return json.dumps(payload)


def parse_invoice_payload(payload: str) -> dict:
    """Распарсить payload из successful_payment."""
    try:
        return json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return {}


async def send_invoice(
    bot: Bot,
    chat_id: int,
    pack_type: str,
    payment_id: int,
    final_price: int,
    user_id: int,
    promocode: Optional[str] = None,
) -> Message:
    """
    Отправить invoice для оплаты.
    
    Args:
        bot: Bot instance
        chat_id: ID чата
        pack_type: Тип пакета (single/pack3/pack10)
        payment_id: ID платежа в БД
        final_price: Итоговая цена в копейках (после скидки)
        user_id: ID пользователя
        promocode: Применённый промокод (опционально)
    
    Returns:
        Сообщение с invoice
    """
    settings = get_settings()
    
    if not settings.payment_provider_token:
        raise ValueError("PAYMENT_PROVIDER_TOKEN не настроен")
    
    title = PACK_NAMES[pack_type]
    description = PACK_DESCRIPTIONS[pack_type]
    
    # Добавить инфо о скидке
    original_price = PACK_PRICES[pack_type]
    if final_price < original_price:
        discount = original_price - final_price
        discount_percent = int(discount / original_price * 100)
        description += f"\n\n🎁 Скидка {discount_percent}%: -{discount/100:.0f}₽"
    
    payload = create_invoice_payload(
        user_id=user_id,
        pack_type=pack_type,
        payment_id=payment_id,
        promocode=promocode,
    )
    
    # Создаём LabeledPrice
    prices = [
        LabeledPrice(
            label=title,
            amount=final_price,  # В копейках
        )
    ]
    
    logger.info(
        f"[PAYMENT] Sending invoice: user={user_id}, pack={pack_type}, "
        f"price={final_price/100}₽, payment_id={payment_id}"
    )
    
    return await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token=settings.payment_provider_token,
        currency="RUB",
        prices=prices,
        start_parameter=f"buy_{pack_type}",
        # Настройки
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False,
        # Защита
        protect_content=True,
    )


def format_price(kopeks: int) -> str:
    """Форматировать цену из копеек."""
    rubles = kopeks / 100
    if rubles == int(rubles):
        return f"{int(rubles)}₽"
    return f"{rubles:.2f}₽"


def get_pack_info(pack_type: str) -> dict:
    """Получить информацию о пакете."""
    return {
        "type": pack_type,
        "name": PACK_NAMES.get(pack_type, pack_type),
        "price": PACK_PRICES.get(pack_type, 0),
        "count": PACK_COUNTS.get(pack_type, 0),
        "description": PACK_DESCRIPTIONS.get(pack_type, ""),
    }

