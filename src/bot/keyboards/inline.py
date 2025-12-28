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

