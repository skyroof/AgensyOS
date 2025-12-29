"""
Reply клавиатуры для accessibility.

Reply keyboards отображаются внизу экрана и более доступны для:
- Пользователей с ограниченными возможностями
- Устройств с маленькими экранами
- Пользователей, предпочитающих физическую клавиатуру
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_role_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply-клавиатура выбора роли (accessibility)."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🎨 Дизайнер"),
        KeyboardButton(text="📊 Продакт"),
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_experience_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply-клавиатура выбора опыта."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="До 1 года"),
        KeyboardButton(text="1-3 года"),
    )
    builder.row(
        KeyboardButton(text="3-5 лет"),
        KeyboardButton(text="5+ лет"),
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_confirm_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply-клавиатура подтверждения ответа."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="✅ Отправить"),
        KeyboardButton(text="✏️ Изменить"),
    )
    builder.row(
        KeyboardButton(text="⏸️ Пауза"),
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_navigation_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply-клавиатура для навигации в онбординге."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="👉 Далее"),
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_start_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply-клавиатура для старта диагностики."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🚀 Начать диагностику"),
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_result_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply-клавиатура для результатов."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📊 Детальный анализ"),
        KeyboardButton(text="🎯 Профиль"),
    )
    builder.row(
        KeyboardButton(text="📈 План развития"),
        KeyboardButton(text="📄 PDF"),
    )
    builder.row(
        KeyboardButton(text="📤 Поделиться"),
        KeyboardButton(text="🔄 Ещё раз"),
    )
    return builder.as_markup(resize_keyboard=True)


def remove_reply_keyboard() -> ReplyKeyboardRemove:
    """Удаление reply-клавиатуры."""
    return ReplyKeyboardRemove()


# === ACCESSIBILITY HELPERS ===

def get_accessibility_hint() -> str:
    """Подсказка по accessibility для пользователей."""
    return (
        "♿ <b>Подсказки по доступности:</b>\n\n"
        "• Увеличить шрифт: Настройки Telegram → Размер текста\n"
        "• Голосовые ответы: просто запиши голосовое сообщение\n"
        "• Навигация: используй кнопки под полем ввода\n"
        "• TalkBack/VoiceOver: бот совместим с экранными читалками"
    )


def get_text_size_hint() -> str:
    """Подсказка про увеличение шрифта."""
    return (
        "💡 <i>Совет: если текст мелкий — зайди в Настройки Telegram → "
        "Размер текста чата и увеличь его.</i>"
    )

