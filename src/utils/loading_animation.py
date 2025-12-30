"""
Модуль анимации загрузки для Telegram бота.
Streaming UI — улучшает воспринимаемую скорость.
"""
import asyncio
from typing import Callable, Optional
from aiogram import Bot
from aiogram.types import Message
from aiogram.enums import ChatAction


# Фреймы анимации "думающего AI"
THINKING_FRAMES = [
    "🧠 AI анализирует",
    "🧠 AI анализирует.",
    "🧠 AI анализирует..",
    "🧠 AI анализирует...",
]

# Прогресс-бар стили
PROGRESS_STYLES = {
    "analyzing": [
        ("░░░░░░░░░░", "0%", "Читаю ответ..."),
        ("▓░░░░░░░░░", "10%", "Анализирую глубину..."),
        ("▓▓░░░░░░░░", "20%", "Оцениваю структуру..."),
        ("▓▓▓░░░░░░░", "30%", "Выявляю инсайты..."),
        ("▓▓▓▓░░░░░░", "40%", "Формирую оценку..."),
        ("▓▓▓▓▓░░░░░", "50%", "Сопоставляю с метриками..."),
        ("▓▓▓▓▓▓░░░░", "60%", "Подготавливаю следующий вопрос..."),
        ("▓▓▓▓▓▓▓░░░", "70%", "Генерирую вопрос..."),
        ("▓▓▓▓▓▓▓▓░░", "80%", "Оптимизирую формулировку..."),
        ("▓▓▓▓▓▓▓▓▓░", "90%", "Почти готово..."),
        ("▓▓▓▓▓▓▓▓▓▓", "100%", "Готово!"),
    ],
    "report": [
        ("░░░░░░░░░░", "0%", "Собираю данные..."),
        ("▓▓░░░░░░░░", "20%", "Анализирую ответы..."),
        ("▓▓▓▓░░░░░░", "40%", "Вычисляю метрики..."),
        ("▓▓▓▓▓▓░░░░", "60%", "Формирую профиль..."),
        ("▓▓▓▓▓▓▓▓░░", "80%", "Генерирую отчёт..."),
        ("▓▓▓▓▓▓▓▓▓▓", "100%", "Финализирую..."),
    ],
    "pdf": [
        ("░░░░░░░░░░", "0%", "Подготовка данных..."),
        ("▓▓▓░░░░░░░", "30%", "Рисую графики..."),
        ("▓▓▓▓▓▓░░░░", "60%", "Собираю страницы..."),
        ("▓▓▓▓▓▓▓▓▓░", "90%", "Финализирую PDF..."),
        ("▓▓▓▓▓▓▓▓▓▓", "100%", "Готово!"),
    ],
}


class LoadingAnimation:
    """Анимация загрузки с прогресс-баром."""
    
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        message: Message,
        style: str = "analyzing",
        update_interval: float = 2.0,
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.message = message
        self.style = style
        self.update_interval = update_interval
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._current_step = 0
    
    async def start(self):
        """Запуск анимации в фоне."""
        self._running = True
        self._task = asyncio.create_task(self._animate())
    
    async def stop(self):
        """Остановка анимации."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _animate(self):
        """Основной цикл анимации."""
        progress = PROGRESS_STYLES.get(self.style, PROGRESS_STYLES["analyzing"])
        
        try:
            while self._running and self._current_step < len(progress):
                bar, pct, status = progress[self._current_step]
                
                # Отправляем typing action
                await self.bot.send_chat_action(self.chat_id, ChatAction.TYPING)
                
                # Обновляем сообщение
                try:
                    await self.message.edit_text(
                        f"🧠 <b>{status}</b>\n\n"
                        f"<code>{bar}</code> {pct}"
                    )
                except Exception:
                    pass  # Сообщение могло быть уже изменено
                
                self._current_step += 1
                await asyncio.sleep(self.update_interval)
                
        except asyncio.CancelledError:
            pass
    
    def advance(self, steps: int = 1):
        """Принудительный переход на N шагов вперёд."""
        self._current_step = min(
            self._current_step + steps,
            len(PROGRESS_STYLES.get(self.style, [])) - 1
        )


async def show_thinking_animation(
    bot: Bot,
    chat_id: int,
    message: Message,
    duration: float = 10.0,
) -> None:
    """
    Показывает анимацию "AI думает" с меняющимися точками.
    
    Args:
        bot: Бот
        chat_id: ID чата
        message: Сообщение для редактирования
        duration: Длительность анимации в секундах
    """
    frame_idx = 0
    start_time = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - start_time < duration:
        frame = THINKING_FRAMES[frame_idx % len(THINKING_FRAMES)]
        try:
            await message.edit_text(frame)
        except Exception:
            pass
        
        await bot.send_chat_action(chat_id, ChatAction.TYPING)
        frame_idx += 1
        await asyncio.sleep(0.5)


def format_time_remaining(seconds: int) -> str:
    """Форматирует оставшееся время."""
    if seconds <= 5:
        return "почти готово"
    elif seconds <= 10:
        return "~10 сек"
    elif seconds <= 30:
        return f"~{seconds // 10 * 10} сек"
    else:
        minutes = seconds // 60
        return f"~{minutes} мин"

