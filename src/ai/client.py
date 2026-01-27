"""
AI клиент для RouterAI (OpenAI-совместимый API).
"""
import logging
import json
import asyncio
import time
from datetime import datetime
from pathlib import Path
import httpx
from openai import AsyncOpenAI

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Настройки retry
MAX_RETRIES = 3
INITIAL_DELAY = 1.0  # секунды
MAX_DELAY = 30.0  # максимальная задержка
BACKOFF_MULTIPLIER = 2.0

# Директория для debug логов
# DEBUG_LOGS_DIR = Path("debug_logs")


def _log_ai_interaction(
    messages: list[dict],
    response: str | None,
    status: str,
    error: str | None = None,
    duration_ms: float | None = None,
):
    """
    Логировать взаимодействие с AI.
    
    Args:
        messages: Отправленные сообщения (промпт)
        response: Ответ AI (или None при ошибке)
        status: "success" или "error"
        error: Текст ошибки (если есть)
        duration_ms: Время выполнения в мс
    """
    # Логируем только в debug режиме
    if not get_settings().debug:
        return

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "duration_ms": duration_ms,
        "prompt": messages,
        "response": response,
        "error": error,
    }
    
    try:
        # В Docker логах это будет JSON строка
        logger.debug(f"AI Interaction: {json.dumps(log_entry, ensure_ascii=False)}")
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
        
        # Создаём httpx клиент с таймаутами (90 сек max, 10 сек connect)
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(90.0, connect=10.0),
            follow_redirects=True,
        )
        
        _client = AsyncOpenAI(
            api_key=settings.routerai_api_key,
            base_url=settings.routerai_base_url,
            http_client=http_client,
            max_retries=3,
        )
    
    return _client


class AIServiceError(Exception):
    """Ошибка AI сервиса после всех retry."""
    def __init__(self, message: str, is_timeout: bool = False, attempts: int = 0):
        super().__init__(message)
        self.is_timeout = is_timeout
        self.attempts = attempts


async def chat_completion(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    retry: bool = True,
    response_format: dict | None = None,
) -> str:
    """
    Отправить запрос к AI и получить ответ с retry логикой.
    
    Args:
        messages: Список сообщений в формате OpenAI
        temperature: Креативность (0-1)
        max_tokens: Максимум токенов в ответе
        retry: Использовать retry с exponential backoff
        response_format: Формат ответа (например, {"type": "json_object"})
        
    Returns:
        Текст ответа от AI
        
    Raises:
        AIServiceError: Если все попытки неудачны
    """
    settings = get_settings()
    client = get_ai_client()
    
    max_attempts = MAX_RETRIES if retry else 1
    delay = INITIAL_DELAY
    last_error = None
    is_timeout = False
    
    for attempt in range(1, max_attempts + 1):
        start_time = time.perf_counter()
        
        try:
            logger.debug(f"AI request attempt {attempt}/{max_attempts}: model={settings.ai_model}")
            
            response = await client.chat.completions.create(
                model=settings.ai_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
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
            
        except httpx.TimeoutException as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            is_timeout = True
            last_error = f"Timeout after {duration_ms/1000:.1f}s"
            logger.warning(f"AI timeout (attempt {attempt}/{max_attempts}): {e}")
            
            _log_ai_interaction(
                messages=messages,
                response=None,
                status=f"timeout_attempt_{attempt}",
                error=str(e),
                duration_ms=duration_ms,
            )
            
        except httpx.ConnectError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            last_error = f"Connection error: {e}"
            logger.warning(f"AI connection error (attempt {attempt}/{max_attempts}): {e}")
            
            _log_ai_interaction(
                messages=messages,
                response=None,
                status=f"connect_error_attempt_{attempt}",
                error=str(e),
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            last_error = f"{type(e).__name__}: {e}"
            logger.warning(f"AI error (attempt {attempt}/{max_attempts}): {e}")
            
            _log_ai_interaction(
                messages=messages,
                response=None,
                status=f"error_attempt_{attempt}",
                error=last_error,
                duration_ms=duration_ms,
            )
        
        # Exponential backoff перед следующей попыткой
        if attempt < max_attempts:
            logger.info(f"Retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
            delay = min(delay * BACKOFF_MULTIPLIER, MAX_DELAY)
    
    # Все попытки исчерпаны
    logger.error(f"AI request failed after {max_attempts} attempts: {last_error}")
    raise AIServiceError(
        f"AI недоступен после {max_attempts} попыток: {last_error}",
        is_timeout=is_timeout,
        attempts=max_attempts,
    )


async def stream_chat_completion(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    retry: bool = True,
):
    """
    Потоковая генерация ответа (generator).
    
    Args:
        messages: Список сообщений
        temperature: Креативность
        max_tokens: Максимум токенов
        retry: Использовать retry (только для инициализации соединения)
        
    Yields:
        Кусочки текста (chunks)
    """
    settings = get_settings()
    client = get_ai_client()
    
    max_attempts = MAX_RETRIES if retry else 1
    delay = INITIAL_DELAY
    last_error = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(f"AI stream attempt {attempt}/{max_attempts}")
            
            stream = await client.chat.completions.create(
                model=settings.ai_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            
            return  # Успешное завершение
            
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.warning(f"AI stream error (attempt {attempt}/{max_attempts}): {e}")
            
            if attempt < max_attempts:
                await asyncio.sleep(delay)
                delay = min(delay * BACKOFF_MULTIPLIER, MAX_DELAY)
    
    # Если все попытки неудачны, выбрасываем ошибку
    # Но так как это генератор, caller должен обработать исключение при итерации
    raise AIServiceError(
        f"AI stream failed after {max_attempts} attempts: {last_error}",
        attempts=max_attempts,
    )
