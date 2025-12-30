"""
Умное разбиение длинных сообщений для Telegram.

Telegram лимит: 4096 символов на сообщение.
Модуль обеспечивает:
- Разбиение по абзацам (предпочтительно)
- Сохранение целостности HTML тегов
- Не ломает слова
- Добавляет нумерацию частей (1/3, 2/3, 3/3)
- Retry при ошибках отправки
"""
import re
import asyncio
import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import Message
from aiogram.enums import ParseMode

logger = logging.getLogger(__name__)

# Telegram лимит 4096, оставляем запас для нумерации и форматирования
MAX_MESSAGE_LENGTH = 4000
SEND_DELAY = 0.3  # Задержка между частями (секунды)
MAX_RETRIES = 3  # Максимум попыток отправки

# HTML теги, поддерживаемые Telegram
ALLOWED_TAGS = ['b', 'i', 'u', 's', 'code', 'pre', 'a', 'tg-spoiler']


def _find_unclosed_tags(text: str) -> list[str]:
    """
    Найти незакрытые HTML теги в тексте.
    
    Returns:
        Список незакрытых тегов в порядке открытия
    """
    open_tags = []
    
    # Паттерн для HTML тегов
    tag_pattern = re.compile(r'<(/?)(\w+)(?:\s[^>]*)?>') 
    
    for match in tag_pattern.finditer(text):
        is_closing = match.group(1) == '/'
        tag_name = match.group(2).lower()
        
        if tag_name not in ALLOWED_TAGS:
            continue
            
        if is_closing:
            # Закрывающий тег — убираем из стека
            if open_tags and open_tags[-1] == tag_name:
                open_tags.pop()
        else:
            # Открывающий тег — добавляем в стек
            open_tags.append(tag_name)
    
    return open_tags


def _close_tags(tags: list[str]) -> str:
    """Сгенерировать закрывающие теги в обратном порядке."""
    return ''.join(f'</{tag}>' for tag in reversed(tags))


def _open_tags(tags: list[str]) -> str:
    """Сгенерировать открывающие теги."""
    return ''.join(f'<{tag}>' for tag in tags)


def _find_split_point(text: str, max_len: int) -> int:
    """
    Найти оптимальную точку разбиения текста.
    
    Приоритет:
    1. Двойной перенос строки (абзац) — \n\n
    2. Одинарный перенос строки — \n
    3. Пробел (не ломаем слова)
    4. Любой символ (крайний случай)
    
    Returns:
        Индекс точки разбиения
    """
    if len(text) <= max_len:
        return len(text)
    
    # Ищем в пределах max_len
    search_text = text[:max_len]
    
    # Приоритет 1: Двойной перенос строки (абзац)
    # Ищем последний \n\n в пределах 80% от max_len (чтобы не резать в самом конце)
    last_para = search_text.rfind('\n\n', 0, int(max_len * 0.9))
    if last_para > max_len * 0.3:  # Если нашли и это не слишком рано
        return last_para + 2  # +2 чтобы включить \n\n
    
    # Приоритет 2: Одинарный перенос строки
    last_newline = search_text.rfind('\n', 0, int(max_len * 0.95))
    if last_newline > max_len * 0.4:
        return last_newline + 1
    
    # Приоритет 3: Пробел (не ломаем слова)
    last_space = search_text.rfind(' ', 0, max_len)
    if last_space > max_len * 0.5:
        return last_space + 1
    
    # Приоритет 4: Точка, восклицательный или вопросительный знак
    for punct in ['. ', '! ', '? ']:
        last_punct = search_text.rfind(punct, 0, max_len)
        if last_punct > max_len * 0.4:
            return last_punct + 2
    
    # Крайний случай — режем по max_len
    return max_len


def split_message(
    text: str,
    max_len: int = MAX_MESSAGE_LENGTH,
    add_numbering: bool = True,
) -> list[str]:
    """
    Умное разбиение длинного сообщения на части.
    
    Особенности:
    - Не ломает HTML теги (<b>, </b> и т.д.)
    - Предпочитает разбивать по абзацам (\n\n)
    - Не ломает слова
    - Добавляет нумерацию (1/3), (2/3), (3/3)
    
    Args:
        text: Исходный текст
        max_len: Максимальная длина части (default: 4000)
        add_numbering: Добавлять ли нумерацию частей
    
    Returns:
        Список частей сообщения
    """
    if not text:
        return []
    
    text = text.strip()
    
    # Если текст короткий — возвращаем как есть
    if len(text) <= max_len:
        return [text]
    
    parts = []
    remaining = text
    unclosed_tags = []  # Теги, которые нужно перенести в следующую часть
    
    while remaining:
        # Учитываем место для открывающих тегов от предыдущей части
        prefix = _open_tags(unclosed_tags)
        available_len = max_len - len(prefix)
        
        if len(remaining) <= available_len:
            # Остаток помещается — добавляем и выходим
            parts.append(prefix + remaining)
            break
        
        # Находим точку разбиения
        split_point = _find_split_point(remaining, available_len)
        
        # Извлекаем часть
        part = remaining[:split_point]
        remaining = remaining[split_point:].lstrip()  # Убираем ведущие пробелы
        
        # Проверяем незакрытые теги
        all_text_so_far = prefix + part
        unclosed = _find_unclosed_tags(all_text_so_far)
        
        # Закрываем незакрытые теги в конце части
        if unclosed:
            part = part + _close_tags(unclosed)
        
        # Добавляем открывающие теги от предыдущей части
        parts.append(prefix + part)
        
        # Запоминаем незакрытые теги для следующей части
        unclosed_tags = unclosed
    
    # Добавляем нумерацию
    if add_numbering and len(parts) > 1:
        total = len(parts)
        parts = [f"<i>({i}/{total})</i>\n\n{part}" for i, part in enumerate(parts, 1)]
    
    # Логируем результат
    logger.info(f"[SPLIT] Message split into {len(parts)} parts: {[len(p) for p in parts]}")
    
    return parts


async def send_long_message(
    bot: Bot,
    chat_id: int,
    text: str,
    parse_mode: ParseMode = ParseMode.HTML,
    reply_markup=None,
    max_len: int = MAX_MESSAGE_LENGTH,
    delay: float = SEND_DELAY,
) -> list[Message]:
    """
    Отправить длинное сообщение, автоматически разбив на части.
    
    Особенности:
    - Автоматическое разбиение по абзацам
    - Сохранение HTML разметки
    - Retry при ошибках
    - Задержка между частями для rate limiting
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        text: Текст сообщения
        parse_mode: Режим парсинга (default: HTML)
        reply_markup: Клавиатура (добавляется только к последнему сообщению)
        max_len: Максимальная длина части
        delay: Задержка между частями
    
    Returns:
        Список отправленных сообщений
    """
    parts = split_message(text, max_len)
    sent_messages = []
    
    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1
        
        # Клавиатура только для последнего сообщения
        markup = reply_markup if is_last else None
        
        # Retry логика
        for attempt in range(MAX_RETRIES):
            try:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=part,
                    parse_mode=parse_mode,
                    reply_markup=markup,
                )
                sent_messages.append(msg)
                break
                
            except Exception as e:
                logger.warning(f"[SPLIT] Send attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
                
                if attempt == MAX_RETRIES - 1:
                    # Последняя попытка — пробуем без parse_mode
                    try:
                        # Убираем HTML теги
                        clean_text = re.sub(r'<[^>]+>', '', part)
                        msg = await bot.send_message(
                            chat_id=chat_id,
                            text=clean_text,
                            parse_mode=None,
                            reply_markup=markup,
                        )
                        sent_messages.append(msg)
                        logger.info("[SPLIT] Sent without HTML after retries")
                    except Exception as e2:
                        logger.error(f"[SPLIT] Failed to send part {i + 1}: {e2}")
                        raise
                else:
                    # Ждём перед retry
                    await asyncio.sleep(0.5 * (attempt + 1))
        
        # Задержка между частями (кроме последней)
        if not is_last and delay > 0:
            await asyncio.sleep(delay)
    
    return sent_messages


async def send_with_continuation(
    bot: Bot,
    chat_id: int,
    text: str,
    parse_mode: ParseMode = ParseMode.HTML,
    reply_markup=None,
    continuation_text: str = "⏬ <i>Продолжение...</i>",
) -> list[Message]:
    """
    Отправить длинное сообщение с текстом "Продолжение..." между частями.
    
    Улучшенный UX для длинных сообщений.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        text: Текст сообщения
        parse_mode: Режим парсинга
        reply_markup: Клавиатура (только для последнего)
        continuation_text: Текст между частями
    
    Returns:
        Список отправленных сообщений
    """
    parts = split_message(text, add_numbering=False)
    sent_messages = []
    
    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1
        is_first = i == 0
        
        # Добавляем "Продолжение..." в начало (кроме первой части)
        if not is_first:
            part = f"{continuation_text}\n\n{part}"
        
        # Клавиатура только для последнего сообщения
        markup = reply_markup if is_last else None
        
        try:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=part,
                parse_mode=parse_mode,
                reply_markup=markup,
            )
            sent_messages.append(msg)
        except Exception as e:
            logger.error(f"[SPLIT] Failed to send continuation part {i + 1}: {e}")
            # Пробуем без HTML
            try:
                clean_text = re.sub(r'<[^>]+>', '', part)
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=clean_text,
                    parse_mode=None,
                    reply_markup=markup,
                )
                sent_messages.append(msg)
            except Exception as e2:
                logger.error(f"[SPLIT] Complete failure for part {i + 1}: {e2}")
                raise
        
        # Задержка между частями
        if not is_last:
            await asyncio.sleep(SEND_DELAY)
    
    return sent_messages


def estimate_parts_count(text: str, max_len: int = MAX_MESSAGE_LENGTH) -> int:
    """
    Оценить количество частей для текста (без фактического разбиения).
    
    Полезно для UI — показать "(~3 сообщения)" перед отправкой.
    
    Args:
        text: Текст для оценки
        max_len: Максимальная длина части
    
    Returns:
        Примерное количество частей
    """
    if not text:
        return 0
    
    text_len = len(text)
    if text_len <= max_len:
        return 1
    
    # Грубая оценка: делим на max_len с запасом на нумерацию (~20 символов)
    effective_len = max_len - 20
    return (text_len // effective_len) + 1

