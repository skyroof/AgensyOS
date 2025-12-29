"""
Утилиты для accessibility.
"""
import re
from typing import Literal


def detect_language(text: str) -> Literal["ru", "en", "unknown"]:
    """
    Определение языка текста.
    
    Простая эвристика на основе частоты символов.
    
    Args:
        text: Текст для анализа
        
    Returns:
        "ru", "en" или "unknown"
    """
    if not text:
        return "unknown"
    
    # Убираем эмодзи и спецсимволы
    clean_text = re.sub(r'[^\w\s]', '', text.lower())
    
    if not clean_text:
        return "unknown"
    
    # Подсчитываем кириллицу и латиницу
    cyrillic_count = len(re.findall(r'[а-яё]', clean_text))
    latin_count = len(re.findall(r'[a-z]', clean_text))
    
    total = cyrillic_count + latin_count
    
    if total == 0:
        return "unknown"
    
    cyrillic_ratio = cyrillic_count / total
    
    if cyrillic_ratio > 0.7:
        return "ru"
    elif cyrillic_ratio < 0.3:
        return "en"
    else:
        # Смешанный текст — считаем по преобладанию
        return "ru" if cyrillic_ratio >= 0.5 else "en"


def get_language_specific_tip(language: str) -> str | None:
    """
    Подсказка для пользователей на другом языке.
    
    Args:
        language: Определённый язык ("ru", "en", "unknown")
        
    Returns:
        Подсказка или None
    """
    if language == "en":
        return (
            "🌐 <i>I see you're writing in English! "
            "The diagnostic works in English too — keep going!</i>"
        )
    return None


def get_first_time_accessibility_tip() -> str:
    """
    Подсказка для первого использования.
    Показывается один раз при первом ответе.
    """
    return (
        "💡 <i>Совет: если текст мелкий — зайди в Настройки Telegram → "
        "Размер текста. Голосовые ответы тоже работают!</i>"
    )


def get_screen_reader_text(element: str, context: str = "") -> str:
    """
    Генерация текста для экранных читалок.
    
    Добавляет alt-text для элементов интерфейса.
    
    Args:
        element: Тип элемента (button, progress, score, etc.)
        context: Дополнительный контекст
        
    Returns:
        Текст для экранной читалки
    """
    templates = {
        "progress_bar": f"Прогресс диагностики: {context}",
        "score": f"Общий балл: {context} из 100",
        "category_score": f"Балл за {context}",
        "question": f"Вопрос номер {context}",
        "answer_preview": "Предпросмотр вашего ответа",
        "button_confirm": "Кнопка подтверждения ответа",
        "button_edit": "Кнопка редактирования ответа",
        "button_pause": "Кнопка паузы диагностики",
    }
    
    return templates.get(element, context)


# Константы для accessibility
ACCESSIBILITY_FEATURES = {
    "voice_input": True,      # Голосовой ввод
    "no_time_limit": True,    # Без ограничения времени
    "session_persistence": True,  # Сохранение сессии
    "screen_reader_compatible": True,  # Совместимость с читалками
    "adjustable_text_size": True,  # Настройка размера текста (в Telegram)
    "keyboard_navigation": True,  # Навигация с клавиатуры
}

