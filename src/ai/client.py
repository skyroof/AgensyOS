"""
AI клиент для RouterAI (OpenAI-совместимый API).
"""
import logging
import httpx
from openai import AsyncOpenAI

from src.core.config import get_settings

logger = logging.getLogger(__name__)

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
    settings = get_settings()
    client = get_ai_client()
    
    logger.debug(f"Sending request to AI: model={settings.ai_model}, messages_count={len(messages)}")
    
    try:
        response = await client.chat.completions.create(
            model=settings.ai_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        result = response.choices[0].message.content
        logger.debug(f"AI response received: {len(result)} chars")
        
        return result
        
    except httpx.ConnectError as e:
        logger.error(f"Connection error to {settings.routerai_base_url}: {e}")
        raise
        
    except httpx.TimeoutException as e:
        logger.error(f"Timeout error: {e}")
        raise
        
    except Exception as e:
        logger.error(f"AI API error ({type(e).__name__}): {e}")
        raise
