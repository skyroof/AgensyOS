"""
Middleware для логирования всех событий.
"""
import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Логирование всех входящих событий."""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        start_time = time.time()
        
        # Логируем входящее событие
        user_info = self._get_user_info(event)
        event_type = self._get_event_type(event)
        
        logger.info(f"📥 {event_type} from {user_info}")
        
        try:
            result = await handler(event, data)
            
            duration = (time.time() - start_time) * 1000
            logger.info(f"✅ {event_type} handled in {duration:.0f}ms")
            
            return result
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"❌ {event_type} failed after {duration:.0f}ms: {e}")
            raise
    
    def _get_user_info(self, event: Update) -> str:
        """Извлечь информацию о пользователе."""
        user = None
        
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        
        if user:
            return f"User({user.id}, @{user.username or 'no_username'})"
        return "Unknown"
    
    def _get_event_type(self, event: Update) -> str:
        """Определить тип события."""
        if isinstance(event, Message):
            if event.text:
                if event.text.startswith("/"):
                    return f"Command: {event.text.split()[0]}"
                return f"Message: {event.text[:50]}..."
            if event.voice:
                return "Voice message"
            return "Message (other)"
        elif isinstance(event, CallbackQuery):
            return f"Callback: {event.data}"
        return "Unknown event"

