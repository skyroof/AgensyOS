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
                        "❌ Произошла ошибка. Попробуй ещё раз или нажми /start для перезапуска."
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer("❌ Ошибка. Попробуй ещё раз.", show_alert=True)
                    if event.message:
                        from src.bot.keyboards.inline import get_back_to_menu_keyboard
                        await event.message.answer(
                            "❌ Произошла ошибка.",
                            reply_markup=get_back_to_menu_keyboard(),
                        )
            except Exception:
                pass
            
            return None

