"""
Обработчик голосовых сообщений с улучшенным UX.
"""
import logging
import tempfile
import os
import asyncio

from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.bot.states import DiagnosticStates
from src.bot.keyboards.inline import get_pause_keyboard
from src.core.config import get_settings

router = Router(name="voice")
logger = logging.getLogger(__name__)

# Минимальная длительность голосового (в секундах)
MIN_VOICE_DURATION = 3
# Рекомендуемая длительность для хорошего ответа
RECOMMENDED_VOICE_DURATION = 15


async def transcribe_voice(bot: Bot, file_id: str) -> str | None:
    """
    Транскрибировать голосовое сообщение через OpenAI Whisper API.
    
    Args:
        bot: Экземпляр бота
        file_id: ID файла в Telegram
        
    Returns:
        Текст или None если не удалось
    """
    from openai import AsyncOpenAI
    import httpx
    
    settings = get_settings()
    
    try:
        # Скачиваем файл
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        # Создаём временный файл
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Скачиваем через бота
            await bot.download_file(file_path, tmp_path)
            
            # Отправляем на транскрибацию
            client = AsyncOpenAI(
                api_key=settings.routerai_api_key,
                base_url=settings.routerai_base_url,
                timeout=httpx.Timeout(120.0),
            )
            
            with open(tmp_path, "rb") as audio_file:
                transcript = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru",
                )
            
            return transcript.text
            
        finally:
            # Удаляем временный файл
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        logger.error(f"Voice transcription failed: {e}")
        return None


def get_voice_quality_hint(duration: int, text_length: int | None) -> str | None:
    """
    Генерация подсказки по качеству голосового сообщения.
    
    Args:
        duration: Длительность в секундах
        text_length: Длина распознанного текста (или None если не распознано)
    
    Returns:
        Подсказка или None
    """
    # Слишком короткое
    if duration < MIN_VOICE_DURATION:
        return "⚡ <i>Очень короткое сообщение. Расскажи подробнее для точного анализа!</i>"
    
    # Не распознано или очень мало текста
    if text_length is None or text_length < 20:
        return "🔇 <i>Не удалось разобрать. Попробуй записать в тихом месте или чётче.</i>"
    
    # Короткий ответ
    if duration < 10 and text_length < 100:
        return "💡 <i>Можешь рассказать подробнее — это улучшит анализ!</i>"
    
    # Отличный развёрнутый ответ
    if duration >= RECOMMENDED_VOICE_DURATION and text_length and text_length > 200:
        return "✨ <i>Отличное развёрнутое голосовое!</i>"
    
    return None


def get_voice_keyboard():
    """Клавиатура для подтверждения голосового (с опцией редактирования)."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_voice"),
        InlineKeyboardButton(text="✏️ Исправить текст", callback_data="edit_voice"),
    )
    builder.row(
        InlineKeyboardButton(text="🎤 Перезаписать", callback_data="rerecord_voice"),
        InlineKeyboardButton(text="⏸️ Пауза", callback_data="pause_session"),
    )
    return builder.as_markup()


@router.message(DiagnosticStates.answering, F.voice)
async def process_voice_answer(message: Message, state: FSMContext, bot: Bot):
    """Обработка голосового сообщения как ответа."""
    from src.bot.handlers.diagnostic import cancel_reminder, get_typing_hint
    
    # Отменяем таймер напоминания
    cancel_reminder(message.chat.id)
    
    duration = message.voice.duration or 0
    
    # Проверяем минимальную длительность
    if duration < MIN_VOICE_DURATION:
        await message.answer(
            f"🎤 Голосовое слишком короткое ({duration} сек).\n\n"
            "Расскажи подробнее — хотя бы 10-15 секунд для хорошего анализа."
        )
        return
    
    # Показываем прогресс расшифровки
    progress_msg = await message.answer(
        "🎤 <b>Расшифровываю голосовое...</b>\n\n"
        f"<code>▓░░░░░░░░░</code> Получаю файл..."
    )
    
    try:
        # Анимация прогресса
        async def update_progress():
            stages = [
                ("▓▓▓░░░░░░░", "Загружаю аудио..."),
                ("▓▓▓▓▓░░░░░", "Распознаю речь..."),
                ("▓▓▓▓▓▓▓░░░", "Обрабатываю текст..."),
            ]
            for bar, status in stages:
                await asyncio.sleep(1.5)
                try:
                    await progress_msg.edit_text(
                        f"🎤 <b>Расшифровываю голосовое...</b>\n\n"
                        f"<code>{bar}</code> {status}"
                    )
                except Exception:
                    pass
        
        progress_task = asyncio.create_task(update_progress())
        
        # Транскрибируем
        text = await transcribe_voice(bot, message.voice.file_id)
        
        # Останавливаем анимацию
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass
        
        # Проверяем результат
        if not text or len(text.strip()) < 10:
            hint = get_voice_quality_hint(duration, len(text) if text else 0)
            await progress_msg.edit_text(
                "❌ <b>Не удалось распознать голосовое</b>\n\n"
                f"{hint or ''}\n\n"
                "💡 <b>Советы:</b>\n"
                "• Запиши в тихом месте\n"
                "• Говори чётко и не слишком быстро\n"
                "• Или напиши ответ текстом"
            )
            return
        
        # Получаем подсказку по качеству
        quality_hint = get_voice_quality_hint(duration, len(text))
        typing_hint = get_typing_hint(len(text))
        
        # Сохраняем распознанный текст как черновик
        await state.update_data(
            draft_answer=text,
            voice_original=True,  # Флаг что ответ из голосового
        )
        
        # Показываем preview с кнопками
        preview_text = text[:400] + "..." if len(text) > 400 else text
        
        await progress_msg.edit_text(
            f"🎤 <b>Вот что я услышал:</b>\n\n"
            f"<i>«{preview_text}»</i>\n\n"
            f"{quality_hint or typing_hint}\n\n"
            f"Всё правильно?",
            reply_markup=get_voice_keyboard(),
        )
        
        await state.set_state(DiagnosticStates.confirming_answer)
        
    except Exception as e:
        logger.error(f"Voice processing failed: {e}")
        await progress_msg.edit_text(
            "❌ Ошибка обработки голосового сообщения.\n\n"
            "Попробуй:\n"
            "• Записать ещё раз\n"
            "• Или отправить ответ текстом"
        )


@router.callback_query(F.data == "confirm_voice")
async def confirm_voice_answer(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение голосового ответа — передаём в основной обработчик."""
    # Валидация будет внутри confirm_answer
    from src.bot.handlers.diagnostic import confirm_answer
    
    # Передаём в основной обработчик подтверждения
    # Меняем callback_data чтобы основной handler его обработал
    callback.data = "confirm_answer"
    await confirm_answer(callback, state, bot)


@router.callback_query(F.data == "edit_voice")
async def edit_voice_text(callback: CallbackQuery, state: FSMContext):
    """Редактирование распознанного текста."""
    data = await state.get_data()
    
    # Проверка сессии
    if "current_question" not in data:
         await callback.answer("Сессия истекла. Начни заново.", show_alert=True)
         return

    current_text = data.get("draft_answer", "")
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование ответа</b>\n\n"
        f"Текущий текст:\n<i>«{current_text[:300]}...»</i>\n\n"
        f"Отправь исправленную версию текстом.\n"
        f"<i>Можешь скопировать и отредактировать выше.</i>"
    )
    
    await state.set_state(DiagnosticStates.answering)
    await callback.answer("✏️ Отправь исправленный текст")


@router.callback_query(F.data == "rerecord_voice")
async def rerecord_voice(callback: CallbackQuery, state: FSMContext):
    """Перезапись голосового."""
    data = await state.get_data()
    
    # Проверка сессии
    if "current_question" not in data:
         await callback.answer("Сессия истекла. Начни заново.", show_alert=True)
         return

    current = data.get("current_question", 1)
    question = data.get("current_question_text", "")
    
    await callback.message.edit_text(
        f"🎤 <b>Перезапись</b>\n\n"
        f"<b>Вопрос {current}/10:</b>\n{question}\n\n"
        f"Запиши новое голосовое сообщение.\n"
        f"<i>Или напиши ответ текстом.</i>"
    )
    
    await state.set_state(DiagnosticStates.answering)
    await callback.answer("🎤 Запиши новое голосовое")
