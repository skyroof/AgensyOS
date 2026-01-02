"""
Inline клавиатуры для бота.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_role_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора роли."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎨 Дизайнер", callback_data="role:designer"),
        InlineKeyboardButton(text="📊 Продакт", callback_data="role:product"),
    )
    builder.row(
        InlineKeyboardButton(text="💳 Баланс / Купить", callback_data="buy_menu"),
    )
    return builder.as_markup()


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора цели (Micro-commitment)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📈 Рост дохода", callback_data="goal:salary"),
        InlineKeyboardButton(text="🚀 Поиск работы", callback_data="goal:job"),
    )
    builder.row(
        InlineKeyboardButton(text="🧐 Оценка навыков", callback_data="goal:check"),
        InlineKeyboardButton(text="👀 Просто интересно", callback_data="goal:curious"),
    )
    return builder.as_markup()


def get_start_with_history_keyboard(has_completed: bool = False, best_score: int | None = None) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора роли с дополнительной кнопкой истории.
    Показывается пользователям с завершёнными диагностиками.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎨 Дизайнер", callback_data="role:designer"),
        InlineKeyboardButton(text="📊 Продакт", callback_data="role:product"),
    )
    if has_completed:
        history_text = "📊 Мои результаты"
        if best_score:
            history_text = f"📊 Мои результаты ({best_score}/100)"
        builder.row(
            InlineKeyboardButton(text=history_text, callback_data="show_history"),
        )
    builder.row(
        InlineKeyboardButton(text="💳 Баланс / Купить", callback_data="buy_menu"),
    )
    return builder.as_markup()


def get_experience_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора опыта."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="До 1 года", callback_data="exp:junior"),
        InlineKeyboardButton(text="1-3 года", callback_data="exp:middle"),
    )
    builder.row(
        InlineKeyboardButton(text="3-5 лет", callback_data="exp:senior"),
        InlineKeyboardButton(text="5+ лет", callback_data="exp:lead"),
    )
    return builder.as_markup()


def get_start_diagnostic_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура начала диагностики."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚀 Начать диагностику", callback_data="start_diagnostic"),
    )
    return builder.as_markup()


def get_restart_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура перезапуска."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Пройти ещё раз", callback_data="restart"),
    )
    return builder.as_markup()


def get_report_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """Клавиатура после отчёта с PDF."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📄 Скачать PDF", callback_data=f"pdf:{session_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Пройти ещё раз", callback_data="restart"),
    )
    return builder.as_markup()


def get_question_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура под вопросом (пауза, контекст)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏸️ Сделать паузу", callback_data="pause_session"),
    )
    return builder.as_markup()


def get_confirm_answer_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения ответа."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_answer"),
        InlineKeyboardButton(text="✏️ Изменить", callback_data="edit_answer"),
    )
    return builder.as_markup()


def get_onboarding_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура онбординга (шаг 1)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👉 Далее", callback_data="onboarding_step2"),
    )
    return builder.as_markup()


def get_onboarding_step2_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура онбординга (шаг 2 — пример ответа)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Понятно, начинаем!", callback_data="onboarding_done"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="onboarding_back"),
    )
    return builder.as_markup()


def get_returning_user_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для возвращающегося пользователя (skip onboarding)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚀 Погнали!", callback_data="skip_onboarding"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Напомни правила", callback_data="show_onboarding"),
    )
    return builder.as_markup()


def get_feedback_rating_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопками 1-10 для оценки."""
    builder = InlineKeyboardBuilder()
    # Первый ряд: 1-5
    builder.row(
        InlineKeyboardButton(text="1", callback_data="feedback:1"),
        InlineKeyboardButton(text="2", callback_data="feedback:2"),
        InlineKeyboardButton(text="3", callback_data="feedback:3"),
        InlineKeyboardButton(text="4", callback_data="feedback:4"),
        InlineKeyboardButton(text="5", callback_data="feedback:5"),
    )
    # Второй ряд: 6-10
    builder.row(
        InlineKeyboardButton(text="6", callback_data="feedback:6"),
        InlineKeyboardButton(text="7", callback_data="feedback:7"),
        InlineKeyboardButton(text="8", callback_data="feedback:8"),
        InlineKeyboardButton(text="9", callback_data="feedback:9"),
        InlineKeyboardButton(text="🔟", callback_data="feedback:10"),
    )
    return builder.as_markup()


def get_skip_comment_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пропуска комментария."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_feedback_comment"),
    )
    return builder.as_markup()


def get_result_summary_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура после Summary Card — минималистичная, 2 ряда.
    Детали доступны по кнопкам, не спамим чат.
    """
    builder = InlineKeyboardBuilder()
    # Основные действия — подробности в одно сообщение каждое
    builder.row(
        InlineKeyboardButton(text="📊 Подробнее", callback_data=f"show:report:{session_id}"),
        InlineKeyboardButton(text="📈 План", callback_data=f"show:pdp:{session_id}"),
        InlineKeyboardButton(text="📄 PDF", callback_data=f"pdf:{session_id}"),
    )
    # Вторичные действия
    builder.row(
        InlineKeyboardButton(text="📤 Поделиться", callback_data=f"share:{session_id}"),
        InlineKeyboardButton(text="🔄 Ещё раз", callback_data="restart"),
    )
    return builder.as_markup()


def get_report_sections_keyboard(session_id: int, sections: list[dict]) -> InlineKeyboardMarkup:
    """Клавиатура с разделами отчёта."""
    builder = InlineKeyboardBuilder()
    
    # Кнопки для каждой секции (по 2 в ряд)
    for i, section in enumerate(sections):
        builder.add(InlineKeyboardButton(
            text=f"{section['emoji']} {section['title']}",
            callback_data=f"report_section:{session_id}:{i}"
        ))
    
    builder.adjust(2)  # 2 кнопки в ряд
    
    # Дополнительные действия
    builder.row(
        InlineKeyboardButton(text="📄 Скачать PDF", callback_data=f"pdf:{session_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ К результатам", callback_data=f"show:summary:{session_id}"),
    )
    
    return builder.as_markup()


def get_back_to_report_menu_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """Кнопка возврата к меню отчёта."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ К разделам", callback_data=f"show:report:{session_id}"),
    )
    return builder.as_markup()


def get_back_to_summary_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """Кнопка возврата к summary после просмотра блока."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к результатам", callback_data=f"show:summary:{session_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📄 Скачать PDF", callback_data=f"pdf:{session_id}"),
    )
    return builder.as_markup()


def get_delayed_feedback_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для отложенного feedback (упрощённая)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👍", callback_data="quick_feedback:good"),
        InlineKeyboardButton(text="👎", callback_data="quick_feedback:bad"),
        InlineKeyboardButton(text="💬 Подробнее", callback_data="quick_feedback:detailed"),
    )
    return builder.as_markup()


def get_session_recovery_keyboard(session_id: int, current_q: int, total_q: int = 10) -> InlineKeyboardMarkup:
    """Клавиатура для восстановления незавершённой сессии."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"▶️ Продолжить ({current_q}/{total_q})",
            callback_data=f"continue_session:{session_id}",
        ),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Начать заново", callback_data="restart_fresh"),
    )
    return builder.as_markup()


def get_pause_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура паузы во время диагностики (добавляется к confirm)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_answer"),
        InlineKeyboardButton(text="✏️ Изменить", callback_data="edit_answer"),
    )
    builder.row(
        InlineKeyboardButton(text="⏸️ Пауза", callback_data="pause_session"),
    )
    return builder.as_markup()


def get_error_retry_keyboard(retry_action: str = "retry_analysis") -> InlineKeyboardMarkup:
    """Клавиатура для ошибок с кнопкой повтора."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Попробовать ещё раз", callback_data=retry_action),
    )
    builder.row(
        InlineKeyboardButton(text="⏸️ Пауза", callback_data="pause_session"),
        InlineKeyboardButton(text="🏠 В начало", callback_data="restart"),
    )
    return builder.as_markup()


def get_timeout_keyboard(retry_action: str = "retry_analysis") -> InlineKeyboardMarkup:
    """Клавиатура для таймаута."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏳ Подождать ещё", callback_data="wait_more"),
        InlineKeyboardButton(text="🔄 Повторить", callback_data=retry_action),
    )
    builder.row(
        InlineKeyboardButton(text="⏸️ Пауза", callback_data="pause_session"),
    )
    return builder.as_markup()


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Универсальная клавиатура для возврата в меню."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Пройти снова", callback_data="restart"),
        InlineKeyboardButton(text="📊 История", callback_data="show_history"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def get_after_share_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """Клавиатура после шаринга — вернуться к результатам."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 К результатам", callback_data=f"back_to_results:{session_id}"),
    )
    return builder.as_markup()


def get_oto_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для One-Time Offer (скидка 30% на Pack 3)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔥 Забрать за 490₽ (-30%)", callback_data="oto_buy:pack3"),
    )
    builder.row(
        InlineKeyboardButton(text="🙅‍♂️ Нет, спасибо", callback_data="delete_message"),
    )
    return builder.as_markup()
    builder.row(
        InlineKeyboardButton(text="🔄 Пройти снова", callback_data="restart"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def get_history_keyboard(last_session_id: int | None = None) -> InlineKeyboardMarkup:
    """Клавиатура для истории диагностик."""
    builder = InlineKeyboardBuilder()
    
    if last_session_id:
        # Кнопка для просмотра последней диагностики
        builder.row(
            InlineKeyboardButton(text="📋 Последний результат", callback_data=f"back_to_results:{last_session_id}"),
            InlineKeyboardButton(text="📄 PDF", callback_data=f"pdf:{last_session_id}"),
        )
    
    builder.row(
        InlineKeyboardButton(text="🔄 Новая диагностика", callback_data="restart"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def get_compare_sessions_keyboard(session1_id: int, session2_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для сравнения двух сессий."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Сессия 1", callback_data=f"back_to_results:{session1_id}"),
        InlineKeyboardButton(text="📋 Сессия 2", callback_data=f"back_to_results:{session2_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ К истории", callback_data="show_history"),
    )
    return builder.as_markup()


# ==================== ПЛАТЕЖИ ====================

def get_buy_keyboard(show_promo_applied: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура с тарифами для покупки — красивые кнопки с ценами."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🛒 Купить 1 диагностику • 390 ₽", callback_data="buy:single"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Пакет 3 шт • 990 ₽", callback_data="buy:pack3"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Пакет 10 шт • 2 490 ₽", callback_data="buy:pack10"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Карьерный Трекер (1 мес) • 490 ₽", callback_data="buy:subscription_1m"),
    )
    if show_promo_applied:
        builder.row(
            InlineKeyboardButton(text="✅ Промокод применён", callback_data="noop"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🎁 У меня есть промокод", callback_data="enter_promo"),
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"),
    )
    return builder.as_markup()


def get_promo_input_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура при вводе промокода."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к тарифам", callback_data="back_to_pricing"),
    )
    return builder.as_markup()


def get_after_payment_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после успешной оплаты."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎯 Начать диагностику", callback_data="restart"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Мой баланс", callback_data="show_balance"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def get_paywall_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура paywall — нет доступа."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔓 Открыть полную версию — 390₽", callback_data="buy:single"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Все тарифы", callback_data="show_pricing"),
        InlineKeyboardButton(text="🎁 Промокод", callback_data="enter_promo"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def get_balance_keyboard(has_balance: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для страницы баланса."""
    builder = InlineKeyboardBuilder()
    if has_balance:
        builder.row(
            InlineKeyboardButton(text="🎯 Начать диагностику", callback_data="restart"),
        )
    builder.row(
        InlineKeyboardButton(text="💰 Пополнить", callback_data="show_pricing"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def get_demo_result_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после демо-диагностики — агрессивный CTA."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔓 Открыть все 12 метрик — 390₽", callback_data="buy:single"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Другие тарифы", callback_data="show_pricing"),
        InlineKeyboardButton(text="🎁 Промокод", callback_data="enter_promo"),
    )
    return builder.as_markup()