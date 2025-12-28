"""
Обработчик голосовых сообщений.
"""
import logging
import tempfile
import os
from pathlib import Path

from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from src.bot.states import DiagnosticStates
from src.core.config import get_settings

router = Router(name="voice")
logger = logging.getLogger(__name__)


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


@router.message(DiagnosticStates.answering, F.voice)
async def process_voice_answer(message: Message, state: FSMContext, bot: Bot):
    """Обработка голосового сообщения как ответа."""
    
    # Показываем, что обрабатываем
    processing_msg = await message.answer("🎤 Распознаю голосовое сообщение...")
    
    try:
        # Транскрибируем
        text = await transcribe_voice(bot, message.voice.file_id)
        
        if not text:
            await processing_msg.edit_text(
                "❌ Не удалось распознать голосовое сообщение.\n\n"
                "Попробуй отправить текстом или запиши ещё раз."
            )
            return
        
        # Показываем распознанный текст
        await processing_msg.edit_text(
            f"🎤 Распознано:\n<i>{text[:500]}{'...' if len(text) > 500 else ''}</i>\n\n"
            "🧠 Анализирую ответ..."
        )
        
        # Имитируем текстовое сообщение и передаём в основной обработчик
        # Создаём новое сообщение с текстом
        message.text = text
        
        # Импортируем и вызываем основной обработчик
        from src.bot.handlers.diagnostic import process_answer
        
        # Удаляем сообщение о распознавании (process_answer создаст своё)
        await processing_msg.delete()
        
        # Вызываем обработчик текстового ответа
        await process_answer(message, state, bot)
        
    except Exception as e:
        logger.error(f"Voice processing failed: {e}")
        await processing_msg.edit_text(
            "❌ Ошибка обработки голосового сообщения.\n"
            "Попробуй отправить ответ текстом."
        )

