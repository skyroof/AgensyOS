"""
Middleware для обработки ошибок.
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
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
                    await event.answer("Что-то сломалось 😔", show_alert=True)
                    
                    # Если есть сообщение, обновляем его
                    if event.message:
                        # Импорт внутри метода, чтобы избежать циклических импортов
                        from src.bot.keyboards.inline import get_back_to_menu_keyboard
                        
                        try:
                            await event.message.edit_text(
                                "<b>😔 Ой, что-то пошло не так...</b>\n\n"
                                "Мы уже знаем об ошибке и чиним её.\n"
                                "Попробуй вернуться в меню или начать заново.",
                                reply_markup=get_back_to_menu_keyboard()
                            )
                        except Exception:
                            # Если не получилось отредактировать (например, сообщение слишком старое)
                            await event.message.answer(
                                "<b>😔 Ой, что-то пошло не так...</b>\n\n"
                                "Попробуй вернуться в меню или начать заново.",
                                reply_markup=get_back_to_menu_keyboard()
                            )
            except Exception:
                # Если даже отправить сообщение не вышло — просто логируем
                pass
            
            return None

