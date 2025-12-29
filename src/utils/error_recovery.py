"""
Error Recovery UX — обработка ошибок с хорошим пользовательским опытом.
"""
import asyncio
import logging
from typing import Callable, TypeVar, Any
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorType(Enum):
    """Типы ошибок для пользовательских сообщений."""
    AI_TIMEOUT = "ai_timeout"
    AI_OVERLOADED = "ai_overloaded"
    AI_ERROR = "ai_error"
    NETWORK_ERROR = "network_error"
    DATABASE_ERROR = "database_error"
    UNKNOWN = "unknown"


# Пользовательские сообщения об ошибках
ERROR_MESSAGES = {
    ErrorType.AI_TIMEOUT: {
        "title": "⏳ AI думает дольше обычного",
        "description": "Запрос обрабатывается. Подожди ещё немного...",
        "action": "Если ждёшь больше минуты — нажми кнопку ниже.",
    },
    ErrorType.AI_OVERLOADED: {
        "title": "🔄 AI-сервис перегружен",
        "description": "Сейчас много запросов. Твой ответ сохранён.",
        "action": "Попробуй через 30 секунд или нажми кнопку.",
    },
    ErrorType.AI_ERROR: {
        "title": "⚠️ Что-то пошло не так",
        "description": "AI временно недоступен. Не переживай — твой ответ сохранён!",
        "action": "Нажми кнопку чтобы попробовать ещё раз.",
    },
    ErrorType.NETWORK_ERROR: {
        "title": "📡 Проблемы с соединением",
        "description": "Проверь интернет-соединение. Твой ответ сохранён локально.",
        "action": "Нажми кнопку когда соединение восстановится.",
    },
    ErrorType.DATABASE_ERROR: {
        "title": "💾 Ошибка сохранения",
        "description": "Не удалось сохранить данные. Диагностика продолжится.",
        "action": "Результаты могут быть неполными.",
    },
    ErrorType.UNKNOWN: {
        "title": "❌ Произошла ошибка",
        "description": "Что-то пошло не так. Попробуй ещё раз.",
        "action": "Если проблема повторяется — напиши /start",
    },
}


def get_error_message(error_type: ErrorType) -> str:
    """Получить форматированное сообщение об ошибке."""
    msg = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES[ErrorType.UNKNOWN])
    return (
        f"{msg['title']}\n\n"
        f"{msg['description']}\n\n"
        f"<i>{msg['action']}</i>"
    )


def classify_error(exception: Exception) -> ErrorType:
    """
    Классификация ошибки по типу исключения.
    
    Args:
        exception: Пойманное исключение
        
    Returns:
        Тип ошибки для пользователя
    """
    error_str = str(exception).lower()
    error_type = type(exception).__name__.lower()
    
    # Таймауты
    if "timeout" in error_str or "timed out" in error_str:
        return ErrorType.AI_TIMEOUT
    
    # Перегрузка
    if "rate limit" in error_str or "429" in error_str or "overloaded" in error_str:
        return ErrorType.AI_OVERLOADED
    
    # Сетевые ошибки
    if any(x in error_str for x in ["connection", "network", "dns", "refused"]):
        return ErrorType.NETWORK_ERROR
    
    if "httpx" in error_type or "aiohttp" in error_type:
        return ErrorType.NETWORK_ERROR
    
    # Ошибки БД
    if any(x in error_type for x in ["sqlalchemy", "database", "postgres", "sqlite"]):
        return ErrorType.DATABASE_ERROR
    
    # AI ошибки
    if any(x in error_str for x in ["openai", "api", "model", "completion"]):
        return ErrorType.AI_ERROR
    
    return ErrorType.UNKNOWN


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    on_retry: Callable[[int, Exception], Any] | None = None,
    **kwargs,
) -> T:
    """
    Выполнить функцию с экспоненциальным backoff при ошибках.
    
    Args:
        func: Асинхронная функция для выполнения
        *args: Позиционные аргументы
        max_retries: Максимальное количество попыток
        initial_delay: Начальная задержка (сек)
        max_delay: Максимальная задержка (сек)
        backoff_factor: Множитель задержки
        on_retry: Callback при каждой повторной попытке
        **kwargs: Именованные аргументы
        
    Returns:
        Результат функции
        
    Raises:
        Exception: Если все попытки исчерпаны
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries - 1:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                
                if on_retry:
                    try:
                        await on_retry(attempt + 1, e) if asyncio.iscoroutinefunction(on_retry) else on_retry(attempt + 1, e)
                    except Exception:
                        pass
                
                await asyncio.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(f"All {max_retries} attempts failed: {e}")
    
    raise last_exception


def get_retry_keyboard(action: str = "retry_last_action"):
    """Клавиатура с кнопкой повтора."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Попробовать ещё раз", callback_data=action),
    )
    builder.row(
        InlineKeyboardButton(text="⏸️ Пауза", callback_data="pause_session"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"),
    )
    return builder.as_markup()


def get_timeout_keyboard(action: str = "retry_last_action"):
    """Клавиатура для таймаута."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏳ Подождать ещё", callback_data="wait_more"),
        InlineKeyboardButton(text="🔄 Повторить", callback_data=action),
    )
    builder.row(
        InlineKeyboardButton(text="⏸️ Пауза", callback_data="pause_session"),
    )
    return builder.as_markup()


# === PROGRESS MESSAGES FOR LONG OPERATIONS ===

WAITING_MESSAGES = [
    "🧠 AI анализирует твой ответ...",
    "🔍 Копаюсь в деталях...",
    "📊 Обрабатываю информацию...",
    "💭 Думаю над следующим вопросом...",
    "✨ Почти готово...",
]


async def show_waiting_animation(
    message,
    timeout: float = 60.0,
    update_interval: float = 10.0,
):
    """
    Показать анимацию ожидания с обновляемыми сообщениями.
    
    Args:
        message: Сообщение для обновления
        timeout: Максимальное время ожидания
        update_interval: Интервал обновления сообщения
    """
    import random
    
    elapsed = 0
    message_idx = 0
    
    while elapsed < timeout:
        await asyncio.sleep(update_interval)
        elapsed += update_interval
        
        # Обновляем сообщение
        msg_text = WAITING_MESSAGES[message_idx % len(WAITING_MESSAGES)]
        progress = int(elapsed / timeout * 100)
        
        try:
            await message.edit_text(
                f"{msg_text}\n\n"
                f"<code>{'▓' * (progress // 10)}{'░' * (10 - progress // 10)}</code> {progress}%"
            )
        except Exception:
            pass
        
        message_idx += 1


# === USER-FRIENDLY ERROR FORMATTING ===

def format_technical_error(exception: Exception, include_details: bool = False) -> str:
    """
    Форматирование технической ошибки для пользователя.
    
    Args:
        exception: Исключение
        include_details: Включать ли технические детали
        
    Returns:
        Форматированное сообщение
    """
    error_type = classify_error(exception)
    base_message = get_error_message(error_type)
    
    if include_details:
        # Для отладки
        return (
            f"{base_message}\n\n"
            f"<code>Debug: {type(exception).__name__}: {str(exception)[:100]}</code>"
        )
    
    return base_message

