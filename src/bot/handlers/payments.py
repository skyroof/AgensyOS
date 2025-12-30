"""
Хендлеры платежей.

/buy — показать тарифы
Callback buy:* — инициировать оплату
pre_checkout_query — валидация перед оплатой
successful_payment — обработка успешной оплаты
"""
import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, 
    CallbackQuery, 
    PreCheckoutQuery,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.db.session import get_session
from src.db.repositories import balance_repo
from src.payments.telegram_payments import (
    send_invoice,
    parse_invoice_payload,
    PACK_PRICES,
    PACK_COUNTS,
    PACK_NAMES,
    format_price,
)
from src.core.config import get_settings
from src.bot.keyboards.inline import (
    get_buy_keyboard,
    get_promo_input_keyboard,
    get_after_payment_keyboard,
    get_paywall_keyboard,
)


logger = logging.getLogger(__name__)
router = Router(name="payments")


# ==================== /buy COMMAND ====================

@router.message(Command("buy"))
async def cmd_buy(message: Message, state: FSMContext):
    """Показать тарифы и кнопки покупки."""
    await show_pricing(message)


async def show_pricing(message: Message, edit: bool = False):
    """Показать страницу с тарифами — красивое меню для ЮKassa."""
    text = """🎯 <b>Deep Diagnostic Bot</b>
<i>AI-диагностика компетенций специалистов</i>

━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 <b>КАТАЛОГ УСЛУГ</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ <b>Одна диагностика</b>
┃
┃ 💰 <b>299 ₽</b>
┃
┣ ✅ 10 адаптивных AI-вопросов
┣ ✅ Оценка 12 компетенций
┣ ✅ PDF-отчёт уровня McKinsey
┣ ✅ План развития на 30 дней
┗ ✅ Сравнение с 1000+ специалистов

━━━━━━━━━━━━━━━━━━━━━━━━━━

3️⃣ <b>Пакет из 3 диагностик</b>
┃
┃ 💰 <b>699 ₽</b> <s>897 ₽</s> <i>(-22%)</i>
┃
┣ ✅ Всё из "Одна диагностика" × 3
┗ ✅ Отслеживание прогресса

━━━━━━━━━━━━━━━━━━━━━━━━━━

🔟 <b>Пакет из 10 диагностик</b>
┃
┃ 💰 <b>1 990 ₽</b> <s>2 990 ₽</s> <i>(-33%)</i>
┃
┣ ✅ Всё из "Одна диагностика" × 10
┣ ✅ Для команд и активного развития
┗ ✅ Максимальная экономия

━━━━━━━━━━━━━━━━━━━━━━━━━━

🎁 <b>Есть промокод?</b> Нажми кнопку ниже"""

    keyboard = get_buy_keyboard()
    
    if edit and hasattr(message, 'edit_text'):
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


# ==================== BUY CALLBACKS ====================

@router.callback_query(F.data.startswith("buy:"))
async def buy_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия на кнопку покупки."""
    pack_type = callback.data.split(":")[1]
    
    if pack_type not in PACK_PRICES:
        await callback.answer("Неизвестный пакет", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    # Проверяем, есть ли сохранённый промокод
    data = await state.get_data()
    promo_code = data.get("promocode")
    promo = None
    
    async with get_session() as session:
        # Валидируем промокод если есть
        if promo_code:
            valid, error, promo = await balance_repo.validate_promocode(
                session, promo_code, pack_type, user_id
            )
            if not valid:
                promo = None
                await state.update_data(promocode=None)
        
        # Создаём платёж
        payment = await balance_repo.create_payment(
            session, user_id, pack_type, promo
        )
        
        # Если промокод 100% — сразу зачисляем без оплаты
        if payment.final_amount == 0:
            # Бесплатно по промокоду!
            payment.status = "success"
            payment.completed_at = datetime.utcnow()
            
            # Добавляем диагностики
            await balance_repo.add_diagnostics(
                session, user_id, payment.diagnostics_count, payment.id
            )
            
            # Записываем использование промокода
            if promo:
                await balance_repo.apply_promocode(
                    session, promo, user_id, payment.id, payment.discount_amount
                )
            
            await session.commit()
            
            # Показываем сообщение об успехе
            await callback.message.edit_text(
                f"""🎉 <b>Промокод применён!</b>

💰 Оплачено: 0₽ (скидка 100%)
🎯 Добавлено: {payment.diagnostics_count} диагностик{'а' if payment.diagnostics_count == 1 else 'и' if payment.diagnostics_count < 5 else ''}

Готов узнать свой реальный уровень?""",
                reply_markup=get_after_payment_keyboard(),
            )
            await callback.answer("🎁 Промокод применён!")
            return
        
        # Отправляем invoice для оплаты
        try:
            await send_invoice(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                pack_type=pack_type,
                payment_id=payment.id,
                final_price=payment.final_amount,
                user_id=user_id,
                promocode=promo_code,
            )
            await callback.answer()
            
            # Удаляем сообщение с тарифами
            try:
                await callback.message.delete()
            except Exception:
                pass
                
        except ValueError as e:
            logger.error(f"Payment error: {e}")
            await callback.answer(
                "⚠️ Платежи временно недоступны. Попробуй позже.",
                show_alert=True
            )


# ==================== PROMOCODE ====================

@router.callback_query(F.data == "enter_promo")
async def enter_promo_callback(callback: CallbackQuery, state: FSMContext):
    """Показать инструкцию по вводу промокода."""
    await callback.message.edit_text(
        """🎁 <b>ВВОД ПРОМОКОДА</b>

Отправь промокод в чат:

<i>Например: MAXVISUAL100</i>

Промокод будет применён к следующей покупке.""",
        reply_markup=get_promo_input_keyboard(),
    )
    await state.set_state("waiting_promo")
    await callback.answer()


@router.message(F.text, F.func(lambda m: len(m.text) <= 50))
async def handle_promo_input(message: Message, state: FSMContext):
    """Обработка ввода промокода."""
    current_state = await state.get_state()
    if current_state != "waiting_promo":
        return  # Не в режиме ввода промокода
    
    code = message.text.upper().strip()
    user_id = message.from_user.id
    
    async with get_session() as session:
        # Пробуем валидировать для single (проверим общую валидность)
        valid, error, promo = await balance_repo.validate_promocode(
            session, code, "single", user_id
        )
        
        if not valid:
            await message.answer(
                f"❌ {error}\n\nПопробуй другой промокод или нажми «Назад».",
                reply_markup=get_promo_input_keyboard(),
            )
            return
        
        # Сохраняем промокод
        await state.update_data(promocode=code)
        await state.set_state(None)
        
        # Показываем инфо о скидке
        if promo.discount_percent == 100:
            discount_text = "100% (БЕСПЛАТНО!)"
        elif promo.discount_percent > 0:
            discount_text = f"{promo.discount_percent}%"
        else:
            discount_text = format_price(promo.discount_amount)
        
        await message.answer(
            f"""✅ <b>Промокод применён!</b>

🎁 Код: <code>{code}</code>
💰 Скидка: {discount_text}

Теперь выбери пакет — скидка применится автоматически.""",
            reply_markup=get_buy_keyboard(show_promo_applied=True),
        )


@router.callback_query(F.data == "back_to_pricing")
async def back_to_pricing(callback: CallbackQuery, state: FSMContext):
    """Вернуться к тарифам."""
    await state.set_state(None)
    await show_pricing(callback.message, edit=True)
    await callback.answer()


# ==================== TELEGRAM PAYMENTS ====================

@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    """
    Валидация перед оплатой.
    
    Telegram вызывает этот хендлер после того, как пользователь
    нажал "Оплатить", но до списания денег.
    """
    logger.info(f"[PAYMENT] Pre-checkout: user={query.from_user.id}, payload={query.invoice_payload}")
    
    # Парсим payload
    payload = parse_invoice_payload(query.invoice_payload)
    
    if not payload:
        await query.answer(ok=False, error_message="Ошибка данных платежа")
        return
    
    # Проверяем что платёж существует
    async with get_session() as session:
        payment = await balance_repo.get_payment(session, payload.get("payment_id"))
        
        if not payment:
            await query.answer(ok=False, error_message="Платёж не найден")
            return
        
        if payment.status != "pending":
            await query.answer(ok=False, error_message="Платёж уже обработан")
            return
    
    # Всё ок, разрешаем оплату
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, state: FSMContext):
    """
    Обработка успешной оплаты.
    
    Telegram вызывает этот хендлер после успешного списания денег.
    """
    payment_info = message.successful_payment
    
    logger.info(
        f"[PAYMENT] Success: user={message.from_user.id}, "
        f"amount={payment_info.total_amount}, "
        f"payload={payment_info.invoice_payload}"
    )
    
    # Парсим payload
    payload = parse_invoice_payload(payment_info.invoice_payload)
    payment_id = payload.get("payment_id")
    
    if not payment_id:
        logger.error(f"[PAYMENT] No payment_id in payload: {payment_info.invoice_payload}")
        await message.answer("⚠️ Ошибка обработки платежа. Свяжись с поддержкой.")
        return
    
    async with get_session() as session:
        # Обновляем статус платежа
        payment = await balance_repo.complete_payment(
            session,
            payment_id,
            telegram_payment_charge_id=payment_info.telegram_payment_charge_id,
            provider_payment_charge_id=payment_info.provider_payment_charge_id,
        )
        
        # Добавляем диагностики на баланс
        balance = await balance_repo.add_diagnostics(
            session, message.from_user.id, payment.diagnostics_count, payment.id
        )
        
        # Применяем промокод если был
        promo_code = payload.get("promocode")
        if promo_code and payment.promocode_id:
            promo = await balance_repo.get_promocode(session, promo_code)
            if promo:
                await balance_repo.apply_promocode(
                    session, promo, message.from_user.id, payment.id, payment.discount_amount
                )
    
    # Очищаем state
    await state.clear()
    
    # Формируем сообщение
    pack_name = PACK_NAMES[payment.pack_type]
    count = payment.diagnostics_count
    count_word = "диагностика" if count == 1 else "диагностики" if count < 5 else "диагностик"
    
    # Экономия для пакетов
    savings_text = ""
    if payment.pack_type == "pack3":
        savings_text = "\n💡 Экономия: 198₽ (22%)"
    elif payment.pack_type == "pack10":
        savings_text = "\n💡 Экономия: 1000₽ (33%)"
    
    promo_text = ""
    if payment.discount_amount > 0:
        promo_text = f"\n🎁 Скидка по промокоду: -{format_price(payment.discount_amount)}"
    
    text = f"""✅ <b>Оплата прошла успешно!</b>

💰 Оплачено: {format_price(payment.final_amount)}
🎯 Добавлено: {count} {count_word}{savings_text}{promo_text}

━━━━━━━━━━━━━━━━━━━━
📊 <b>Твой баланс: {balance.diagnostics_balance} {count_word}</b>
━━━━━━━━━━━━━━━━━━━━

Готов узнать свой реальный уровень?"""

    await message.answer(text, reply_markup=get_after_payment_keyboard())
    
    # Уведомление админу
    await notify_admin_payment(message.bot, payment, message.from_user)


async def notify_admin_payment(bot: Bot, payment, user):
    """Уведомить админа о платеже."""
    settings = get_settings()
    if not settings.admin_telegram_id:
        return
    
    try:
        text = f"""💰 <b>Новый платёж!</b>

👤 {user.full_name} (@{user.username or 'no_username'})
📦 {PACK_NAMES[payment.pack_type]}
💵 {format_price(payment.final_amount)}
{"🎁 Промокод применён" if payment.discount_amount > 0 else ""}"""

        await bot.send_message(settings.admin_telegram_id, text)
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")


# ==================== PAYWALL ====================

async def show_paywall(message: Message, demo_completed: bool = False):
    """
    Показать paywall (нет доступа).
    
    Args:
        message: Сообщение для ответа
        demo_completed: True если пользователь только что завершил демо
    """
    if demo_completed:
        text = """🔥 <b>ЭТО БЫЛА ДЕМО-ВЕРСИЯ!</b>

Ты увидел только <b>2 из 12</b> метрик!

📊 <b>Скрытые метрики:</b>
├─ Системное мышление: ???
├─ Лидерство: ???
├─ Коммуникация: ???
├─ Эмпатия: ???
└─ <i>...ещё 6 метрик</i>

🎁 <b>Полная диагностика покажет:</b>
✅ Все 12 метрик с оценками
✅ Твои сильные стороны
✅ Зоны роста + план развития
✅ PDF-отчёт уровня McKinsey
✅ Сравнение с рынком

━━━━━━━━━━━━━━━━━━━━

Открой полный потенциал! 🚀"""
    else:
        text = """🔒 <b>Нет доступных диагностик</b>

Твой баланс: 0 диагностик

Чтобы пройти полную диагностику,
выбери один из пакетов:

1️⃣ Одна диагностика — 299₽
3️⃣ Пакет 3 — 699₽ (-22%)
🔟 Пакет 10 — 1990₽ (-33%)"""

    await message.answer(text, reply_markup=get_paywall_keyboard())


# ==================== BALANCE ====================

@router.callback_query(F.data == "show_pricing")
async def show_pricing_callback(callback: CallbackQuery, state: FSMContext):
    """Показать тарифы по callback."""
    await show_pricing(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data == "show_balance")
async def show_balance_callback(callback: CallbackQuery):
    """Показать баланс по callback."""
    user_id = callback.from_user.id
    
    async with get_session() as session:
        balance = await balance_repo.get_user_balance(session, user_id)
        payments = await balance_repo.get_user_payments(session, user_id)
    
    count = balance.diagnostics_balance
    count_word = "диагностика" if count == 1 else "диагностики" if 2 <= count <= 4 else "диагностик"
    demo_status = "✅ Использовано" if balance.demo_used else "🆓 Доступно"
    
    text = f"""📊 <b>ТВОЙ БАЛАНС</b>

🎯 Доступно: <b>{count}</b> {count_word}
🆓 Демо: {demo_status}
📈 Пройдено всего: {balance.total_used}
💰 Куплено всего: {balance.total_purchased}"""

    if payments:
        text += "\n\n━━━━━━━━━━━━━━━━━━━━\n📜 <b>Последние покупки:</b>\n"
        for p in payments[:5]:
            if p.status == "success":
                date = p.completed_at.strftime("%d.%m.%Y") if p.completed_at else "—"
                promo = " 🎁" if p.discount_amount > 0 else ""
                text += f"\n{date} — {PACK_NAMES[p.pack_type]} — {format_price(p.final_amount)}{promo}"
    
    from src.bot.keyboards.inline import get_balance_keyboard
    await callback.message.edit_text(text, reply_markup=get_balance_keyboard(count > 0))
    await callback.answer()


@router.message(Command("balance"))
async def cmd_balance(message: Message):
    """Показать баланс пользователя."""
    user_id = message.from_user.id
    
    async with get_session() as session:
        balance = await balance_repo.get_user_balance(session, user_id)
        payments = await balance_repo.get_user_payments(session, user_id)
    
    # Формируем текст
    count = balance.diagnostics_balance
    count_word = "диагностика" if count == 1 else "диагностики" if 2 <= count <= 4 else "диагностик"
    
    demo_status = "✅ Использовано" if balance.demo_used else "🆓 Доступно"
    
    text = f"""📊 <b>ТВОЙ БАЛАНС</b>

🎯 Доступно: <b>{count}</b> {count_word}
🆓 Демо: {demo_status}
📈 Пройдено всего: {balance.total_used}
💰 Куплено всего: {balance.total_purchased}"""

    # История покупок
    if payments:
        text += "\n\n━━━━━━━━━━━━━━━━━━━━\n📜 <b>Последние покупки:</b>\n"
        for p in payments[:5]:
            if p.status == "success":
                date = p.completed_at.strftime("%d.%m.%Y") if p.completed_at else "—"
                promo = " 🎁" if p.discount_amount > 0 else ""
                text += f"\n{date} — {PACK_NAMES[p.pack_type]} — {format_price(p.final_amount)}{promo}"
    
    text += "\n\n━━━━━━━━━━━━━━━━━━━━"
    
    from src.bot.keyboards.inline import get_balance_keyboard
    await message.answer(text, reply_markup=get_balance_keyboard(count > 0))

