"""
Middleware для обработки ошибок.
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Update, Message, CallbackQuery

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """Глобальный обработчик ошибок."""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            # Игнорируем ошибки тайм-аута callback и другие частые сетевые проблемы
            error_str = str(e).lower()
            if isinstance(e, TelegramBadRequest) and (
                "query is too old" in error_str or 
                "timeout" in error_str or
                "message is not modified" in error_str or
                "bot_response_timeout" in error_str
            ):
                logger.warning(f"Ignored Telegram API error: {e}")
                return None

            logger.exception(f"Unhandled error: {e}")
            
            # Пытаемся отправить сообщение об ошибке пользователю
            try:
                if isinstance(event, Message):
                    await event.answer(
                        "😔 Что-то пошло не так.\n"
                        "Попробуй перезапустить бота: /start"
                    )
                elif isinstance(event, CallbackQuery):
                    # Показываем алерт
                    try:
                        await event.answer("Что-то сломалось 😔", show_alert=True)
                    except Exception:
                        pass
                    
                    # Если есть сообщение, обновляем его
                    if event.message:
                        # Импорт внутри метода, чтобы избежать циклических импортов
                        from src.bot.keyboards.inline import get_back_to_menu_keyboard
                        
                        error_text = (
                            "<b>😔 Ой, что-то пошло не так...</b>\n\n"
                            "Мы уже знаем об ошибке и чиним её.\n"
                            "Попробуй вернуться в меню или начать заново."
                        )
                        
                        try:
                            await event.message.edit_text(
                                error_text,
                                reply_markup=get_back_to_menu_keyboard()
                            )
                        except Exception:
                            # Если не получилось отредактировать (например, сообщение слишком старое)
                            await event.message.answer(
                                error_text,
                                reply_markup=get_back_to_menu_keyboard()
                            )
            except Exception:
                # Если даже отправить сообщение не вышло — просто логируем
                pass
            
            return None

