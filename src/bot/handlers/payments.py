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
    User,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.db.session import get_session
from src.db.repositories import balance_repo, get_or_create_user
from src.payments.telegram_payments import (
    send_invoice,
    parse_invoice_payload,
    PACK_PRICES,
    PACK_COUNTS,
    PACK_NAMES,
    format_price,
)
from src.core.config import get_settings
from src.core.prices import OTO_PACK3_PRICE
from src.db.repositories.subscription_repo import activate_subscription
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


@router.callback_query(F.data == "buy_menu")
async def show_pricing_callback(callback: CallbackQuery):
    """Обработка нажатия кнопки 'Купить / Баланс'."""
    await show_pricing(callback.message, edit=True)
    await callback.answer()


async def show_pricing(message: Message, edit: bool = False):
    """Показать страницу с тарифами — красивое меню для ЮKassa."""
    text = """🎯 <b>MAX Diagnostic Bot</b>
<i>AI-диагностика компетенций специалистов</i>

Здесь ты можешь выбрать подходящий формат диагностики.

👇 <b>Нажми на кнопку пакета, чтобы узнать подробности и преимущества.</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ <b>Одна диагностика</b>
<i>Базовый анализ компетенций</i>

3️⃣ <b>Пакет из 3 диагностик</b>
<i>Для отслеживания прогресса (выгодно!)</i>

🔟 <b>Пакет из 10 диагностик</b>
<i>Для команд и активного развития</i>

⭐ <b>Карьерный Трекер</b>
<i>Личный AI-коуч (NEW!)</i>

━━━━━━━━━━━━━━━━━━━━━━━━━━

🎁 <b>Есть промокод?</b> Нажми кнопку ниже"""

    keyboard = get_buy_keyboard()
    
    if edit and hasattr(message, 'edit_text'):
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


# ==================== BUY CALLBACKS ====================

@router.callback_query(F.data.startswith("buy:"))
async def show_pack_details(callback: CallbackQuery, state: FSMContext):
    """Показать подробности пакета перед покупкой."""
    pack_type = callback.data.split(":")[1]
    
    details = {
        "single": {
            "title": "1️⃣ Одна диагностика",
            "price": "390 ₽",
            "desc": """
✅ <b>Глубокий анализ компетенций</b>
• 10 профессиональных кейсов
• Оценка 12 метрик (Hard, Soft, Thinking, Mindset)
• Сравнение с рынком (Junior/Middle/Senior)

📄 <b>Что ты получишь:</b>
• Детальный PDF-отчёт (15+ страниц)
• Разбор сильных сторон и зон роста
• Персональный вектор развития

<i>Идеально для старта и понимания текущего уровня.</i>
"""
        },
        "pack3": {
            "title": "3️⃣ Пакет из 3 диагностик",
            "price": "990 ₽",
            "old_price": "1 170 ₽",
            "discount": "15%",
            "desc": """
✅ <b>Система трекинга прогресса</b>

📉 <b>Как это работает:</b>
1. Пройди сейчас → получи точку А
2. Через месяц → замерь прогресс
3. Через квартал → подтверди рост грейда

💡 <i>Выгода 180 ₽. Выбор тех, кто растет осознанно.</i>
"""
        },
        "pack10": {
            "title": "🔟 Пакет из 10 диагностик",
            "price": "2 490 ₽",
            "old_price": "3 900 ₽",
            "discount": "36%",
            "desc": """
✅ <b>Профессиональный набор</b>
• Для регулярного чекапа (раз в 2 недели)
• Можно использовать для оценки команды
• Максимальная выгода

💡 <i>Экономия 1410 ₽. Цена одной диагностики < 250 ₽.</i>
"""
        },
        "subscription_1m": {
            "title": "⭐ Карьерный Трекер (1 мес)",
            "price": "490 ₽",
            "desc": """
🚀 <b>Твой личный AI-коуч</b>

Вместо скучных лекций — практика в работе:
• <b>Ежедневные микро-задания</b> (15 мин)
• Модель развития 70/20/10
• Геймификация (XP, уровни, стрики)

🧠 <b>А также:</b>
• Доступ к базе знаний (гайды, фреймворки)
• Умные напоминания

<i>Преврати развитие в привычку. Цена чашки кофе.</i>
"""
        }
    }

    info = details.get(pack_type)
    if not info:
        await callback.answer("Информация не найдена")
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"💳 Купить за {info['price']}", callback_data=f"confirm_buy:{pack_type}")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад в каталог", callback_data="back_to_pricing")
    )

    price_line = f"💰 <b>{info['price']}</b>"
    if "old_price" in info:
        price_line += f" <s>{info['old_price']}</s> <i>(-{info['discount']})</i>"

    text = f"""{info['title']}

{price_line}

{info['desc']}"""

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_buy:"))
async def confirm_buy_callback(callback: CallbackQuery, state: FSMContext):
    """Подтверждение покупки (переход к оплате)."""
    pack_type = callback.data.split(":")[1]
    await process_purchase(callback, state, pack_type)


@router.callback_query(F.data == "oto_buy:pack3")
async def oto_buy_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка покупки OTO (Pack 3 со скидкой)."""
    await process_purchase(callback, state, "pack3", override_price=OTO_PACK3_PRICE)


async def process_purchase(
    callback: CallbackQuery, 
    state: FSMContext, 
    pack_type: str, 
    override_price: int | None = None
):
    """Общая логика покупки."""
    if pack_type not in PACK_PRICES:
        await callback.answer("Неизвестный пакет", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    # Проверяем, есть ли сохранённый промокод
    data = await state.get_data()
    promo_code = data.get("promocode")
    promo = None
    
    async with get_session() as session:
        # Гарантируем, что пользователь существует и получаем его внутренний ID
        from src.db.repositories.user_repo import get_or_create_user
        user = await get_or_create_user(
            session, 
            telegram_id=user_id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )
        internal_user_id = user.id

        # Валидируем промокод если есть
        if promo_code and not override_price:
            valid, error, promo = await balance_repo.validate_promocode(
                session, promo_code, pack_type, internal_user_id
            )
            if not valid:
                promo = None
                await state.update_data(promocode=None)
        
        # Создаём платёж
        payment = await balance_repo.create_payment(
            session, internal_user_id, pack_type, promo
        )
        
        # Если есть override_price (OTO), обновляем сумму платежа
        if override_price:
            payment.amount = override_price
            payment.final_amount = override_price
            payment.discount_amount = PACK_PRICES[pack_type] - override_price
            await session.commit()
        
        # Если промокод 100% — сразу зачисляем без оплаты
        if payment.final_amount == 0:
            # Бесплатно по промокоду!
            payment.status = "success"
            payment.completed_at = datetime.utcnow()
            
            # Если это подписка — активируем
            if payment.pack_type == "subscription_1m":
                 from src.db.repositories.subscription_repo import activate_subscription
                 await activate_subscription(session, internal_user_id, days=30)
            
            # Добавляем диагностики
            await balance_repo.add_diagnostics(
                session, internal_user_id, payment.diagnostics_count, payment.id, commit=False
            )
            
            # Записываем использование промокода
            if promo:
                await balance_repo.apply_promocode(
                    session, promo, internal_user_id, payment.id, payment.discount_amount, commit=False
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
            
            # Удаляем сообщение с тарифами (если это обычное меню)
            # Для OTO не удаляем, пусть висит пока пользователь думает
            if not override_price:
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
    
    # === GOD MODE для конкретного промокода (по просьбе пользователя) ===
    if code == "MAXVISUAL200":
        try:
            async with get_session() as session:
                # 0. Гарантируем, что пользователь существует
                from src.db.repositories.user_repo import get_or_create_user
                from src.db.repositories.subscription_repo import activate_subscription
                
                # Используем данные из сообщения для создания/обновления пользователя
                user = await get_or_create_user(
                    session, 
                    telegram_id=user_id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name
                )
                
                # ВАЖНО: Используем user.id (внутренний ID), а не telegram_id
                internal_user_id = user.id

                # 1. Даем 999 диагностик
                await balance_repo.add_diagnostics(
                    session, internal_user_id, 999, payment_id=None, commit=False
                )
                
                # 2. Активируем подписку на 10 лет
                await activate_subscription(session, internal_user_id, days=3650)
                
                # 3. Коммитим
                await session.commit()
                
            await message.answer(
                f"""🎉 <b>MAX ACCESS АКТИВИРОВАН!</b>
                
        🎁 Код: <code>{code}</code>

        ✅ <b>Диагностики:</b> +999 шт.
        ✅ <b>Карьерный трекер:</b> 10 лет доступа
        ✅ <b>База знаний:</b> Разблокирована

        Приятного использования! 🚀""",
                reply_markup=get_after_payment_keyboard(),
            )
            await state.clear()
        except Exception as e:
            import html
            logger.error(f"GOD MODE ERROR: {e}", exc_info=True)
            # Экранируем текст ошибки, чтобы не сломать HTML-парсинг Telegram
            safe_error = html.escape(str(e))
            await message.answer(f"⚠️ Ошибка активации: {safe_error}")
        return
    # ====================================================================

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
        await query.answer(ok=False, error_message="Ошибка данных платежа. Попробуйте снова.")
        return
    
    # Проверяем что платёж существует
    async with get_session() as session:
        payment = await balance_repo.get_payment(session, payload.get("payment_id"))
        
        if not payment:
            await query.answer(ok=False, error_message="Платёж не найден. Начните покупку заново.")
            return
        
        if payment.status != "pending":
            await query.answer(ok=False, error_message="Платёж уже обработан или отменен.")
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
        # Гарантируем, что пользователь существует и получаем его внутренний ID
        from src.db.repositories.user_repo import get_or_create_user
        user = await get_or_create_user(
            session, 
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        internal_user_id = user.id

        # 1. Проверка идемпотентности
        # Сначала получаем текущий статус платежа
        existing_payment = await balance_repo.get_payment(session, payment_id)
        
        if not existing_payment:
            logger.error(f"[PAYMENT] Payment not found: {payment_id}")
            await message.answer("⚠️ Ошибка: платёж не найден.")
            return

        if existing_payment.status == "success":
            logger.warning(f"[PAYMENT] Duplicate webhook for payment {payment_id}")
            # Платёж уже обработан, просто сообщаем пользователю (или молчим, если это повторный webhook)
            # Но так как это message handler (successful_payment), это сообщение от пользователя (клиент Telegram)
            # или сервиса. successful_payment обычно приходит от клиента.
            # Поэтому лучше сообщить, что всё ок.
            await message.answer("✅ Платёж уже был успешно обработан ранее.", reply_markup=get_after_payment_keyboard())
            return

        # Обновляем статус платежа
        payment = await balance_repo.complete_payment(
            session,
            payment_id,
            telegram_payment_charge_id=payment_info.telegram_payment_charge_id,
            provider_payment_charge_id=payment_info.provider_payment_charge_id,
            commit=False
        )
        
        # Если это подписка — активируем
        if payment.pack_type == "subscription_1m":
             from src.db.repositories.subscription_repo import activate_subscription
             await activate_subscription(session, internal_user_id, days=30)

        # Добавляем диагностики на баланс
        balance = await balance_repo.add_diagnostics(
            session, internal_user_id, payment.diagnostics_count, payment.id, commit=False
        )
        
        # Применяем промокод если был
        promo_code = payload.get("promocode")
        if promo_code and payment.promocode_id:
            promo = await balance_repo.get_promocode(session, promo_code)
            if promo:
                await balance_repo.apply_promocode(
                    session, promo, internal_user_id, payment.id, payment.discount_amount, commit=False
                )
    
        await session.commit()
    
    # Очищаем state
    await state.clear()
    
    # Если это подписка — шлем отдельное сообщение и выходим (или показываем другое)
    if payment.pack_type == "subscription_1m":
        text = f"""✅ <b>Подписка активирована!</b>

💰 Оплачено: {format_price(payment.final_amount)}
⭐ Доступ: 30 дней (PDP, трекинг, база знаний)

Теперь тебе доступны еженедельные задания!"""
        await message.answer(text, reply_markup=get_after_payment_keyboard())
        return

    # Формируем сообщение
    pack_name = PACK_NAMES[payment.pack_type]
    count = payment.diagnostics_count
    count_word = "диагностика" if count == 1 else "диагностики" if count < 5 else "диагностик"
    
    # Экономия для пакетов
    savings_text = ""
    if payment.pack_type == "pack3":
        savings_text = "\n💡 Экономия: 180₽ (15%)"
    elif payment.pack_type == "pack10":
        savings_text = "\n💡 Экономия: 1410₽ (36%)"
    
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

1️⃣ Одна диагностика — 390₽
3️⃣ Пакет 3 — 990₽ (-15%)
🔟 Пакет 10 — 2490₽ (-36%)"""

    await message.answer(text, reply_markup=get_paywall_keyboard())


# ==================== BALANCE ====================

@router.callback_query(F.data == "show_pricing")
async def show_pricing_callback(callback: CallbackQuery, state: FSMContext):
    """Показать тарифы по callback."""
    await show_pricing(callback.message, edit=True)
    await callback.answer()


async def send_balance_info(tg_user: User, message: Message, is_edit: bool = False):
    """Отправить или обновить информацию о балансе."""
    async with get_session() as session:
        # Ensure user exists
        await get_or_create_user(
            session, 
            tg_user.id, 
            tg_user.username, 
            tg_user.first_name, 
            tg_user.last_name
        )
        
        balance = await balance_repo.get_user_balance(session, tg_user.id)
        payments = await balance_repo.get_user_payments(session, tg_user.id)
    
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
    
    text += "\n\n━━━━━━━━━━━━━━━━━━━━"
    
    from src.bot.keyboards.inline import get_balance_keyboard
    keyboard = get_balance_keyboard(count > 0)

    try:
        if is_edit:
            await message.edit_text(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Failed to send balance info: {e}")
        # Fallback if edit fails
        if is_edit:
            await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "show_balance")
async def show_balance_callback(callback: CallbackQuery):
    """Показать баланс по callback."""
    await send_balance_info(callback.from_user, callback.message, is_edit=True)
    await callback.answer()


@router.message(Command("balance"))
@router.message(F.text == "💳 Баланс")
async def cmd_balance(message: Message):
    """Показать баланс пользователя."""
    await send_balance_info(message.from_user, message, is_edit=False)

