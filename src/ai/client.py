"""
AI клиент для RouterAI (OpenAI-совместимый API).
"""
import logging
import json
import os
from datetime import datetime
from pathlib import Path
import httpx
from openai import AsyncOpenAI

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Директория для debug логов
DEBUG_LOGS_DIR = Path("debug_logs")


def _ensure_debug_dir():
    """Создать директорию для логов если её нет."""
    DEBUG_LOGS_DIR.mkdir(exist_ok=True)


def _log_ai_interaction(
    messages: list[dict],
    response: str | None,
    status: str,
    error: str | None = None,
    duration_ms: float | None = None,
):
    """
    Логировать взаимодействие с AI в файл.
    
    Args:
        messages: Отправленные сообщения (промпт)
        response: Ответ AI (или None при ошибке)
        status: "success" или "error"
        error: Текст ошибки (если есть)
        duration_ms: Время выполнения в мс
    """
    _ensure_debug_dir()
    
    timestamp = datetime.now()
    filename = timestamp.strftime("%Y-%m-%d_%H-%M-%S") + f"_{status}.json"
    filepath = DEBUG_LOGS_DIR / filename
    
    log_entry = {
        "timestamp": timestamp.isoformat(),
        "status": status,
        "duration_ms": duration_ms,
        "prompt": messages,
        "response": response,
        "error": error,
    }
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(log_entry, f, ensure_ascii=False, indent=2)
        logger.debug(f"AI interaction logged to {filepath}")
    except Exception as e:
        logger.warning(f"Failed to log AI interaction: {e}")

# Глобальный клиент (переиспользуем соединения)
_client: AsyncOpenAI | None = None


def get_ai_client() -> AsyncOpenAI:
    """Получить клиент для RouterAI."""
    global _client
    
    if _client is None:
        settings = get_settings()
        
        logger.info(f"Initializing AI client: base_url={settings.routerai_base_url}, model={settings.ai_model}")
        
        # Создаём httpx клиент с таймаутами
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=30.0),
            follow_redirects=True,
        )
        
        _client = AsyncOpenAI(
            api_key=settings.routerai_api_key,
            base_url=settings.routerai_base_url,
            http_client=http_client,
            max_retries=3,
        )
    
    return _client


async def chat_completion(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """
    Отправить запрос к AI и получить ответ.
    
    Args:
        messages: Список сообщений в формате OpenAI
        temperature: Креативность (0-1)
        max_tokens: Максимум токенов в ответе
        
    Returns:
        Текст ответа от AI
    """
    import time
    
    settings = get_settings()
    client = get_ai_client()
    
    logger.debug(f"Sending request to AI: model={settings.ai_model}, messages_count={len(messages)}")
    
    start_time = time.perf_counter()
    
    try:
        response = await client.chat.completions.create(
            model=settings.ai_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        result = response.choices[0].message.content
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        logger.debug(f"AI response received: {len(result)} chars in {duration_ms:.0f}ms")
        
        # Логируем успешный запрос
        _log_ai_interaction(
            messages=messages,
            response=result,
            status="success",
            duration_ms=duration_ms,
        )
        
        return result
        
    except httpx.ConnectError as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Connection error to {settings.routerai_base_url}: {e}")
        _log_ai_interaction(
            messages=messages,
            response=None,
            status="error",
            error=f"ConnectError: {e}",
            duration_ms=duration_ms,
        )
        raise
        
    except httpx.TimeoutException as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Timeout error: {e}")
        _log_ai_interaction(
            messages=messages,
            response=None,
            status="error",
            error=f"TimeoutException: {e}",
            duration_ms=duration_ms,
        )
        raise
        
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"AI API error ({type(e).__name__}): {e}")
        _log_ai_interaction(
            messages=messages,
            response=None,
            status="error",
            error=f"{type(e).__name__}: {e}",
            duration_ms=duration_ms,
        )
        raise
