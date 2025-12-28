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


def get_confirm_answer_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения ответа."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_answer"),
        InlineKeyboardButton(text="✏️ Изменить", callback_data="edit_answer"),
    )
    return builder.as_markup()


def get_onboarding_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура онбординга."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Понятно, начинаем!", callback_data="onboarding_done"),
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