"""
Генератор детального AI-отчёта.
"""
import logging
from src.ai.client import chat_completion
from src.ai.answer_analyzer import calculate_category_scores

logger = logging.getLogger(__name__)


REPORT_SYSTEM_PROMPT = """Ты — эксперт по оценке специалистов с 20-летним опытом в HR и найме.
Твоя задача — написать глубокий, проницательный отчёт о кандидате на основе его ответов.

ФОРМАТ ОТЧЁТА (строго следуй структуре):

1. **ОБЩЕЕ ВПЕЧАТЛЕНИЕ** (2-3 предложения)
Краткая характеристика кандидата как специалиста.

2. **СИЛЬНЫЕ СТОРОНЫ** (3-5 пунктов)
Конкретные сильные качества с примерами из ответов.

3. **ЗОНЫ РАЗВИТИЯ** (3-5 пунктов)
Конкретные области для улучшения с рекомендациями.

4. **HARD SKILLS** (2-3 предложения)
Оценка технических компетенций.

5. **SOFT SKILLS** (2-3 предложения)
Оценка коммуникативных навыков и работы с людьми.

6. **МЫШЛЕНИЕ** (2-3 предложения)
Оценка системности, структурности, глубины рассуждений.

7. **MINDSET** (2-3 предложения)
Оценка ценностей, мотивации, зрелости.

8. **РЕКОМЕНДАЦИИ ПО РАЗВИТИЮ** (3 конкретных совета)
Что конкретно делать для роста.

9. **ИТОГОВЫЙ ВЕРДИКТ** (1-2 коротких предложения)
Кратко: на какой уровень подходит и почему.

ПРАВИЛА:
- Пиши на русском языке
- Будь конкретным — ссылайся на реальные ответы
- Избегай общих фраз и воды
- Будь честным, но конструктивным
- Не используй emoji
- Используй HTML теги для форматирования: <b>жирный</b>, <i>курсив</i>
- НЕ используй markdown (# ## * и т.д.) — только HTML"""


async def generate_detailed_report(
    role: str,
    role_name: str,
    experience: str,
    conversation_history: list[dict],
    analysis_history: list[dict],
) -> str:
    """
    Сгенерировать детальный AI-отчёт.
    
    Args:
        role: Роль (designer/product)
        role_name: Название роли
        experience: Уровень опыта
        conversation_history: История вопросов и ответов
        analysis_history: История анализов
        
    Returns:
        Текст детального отчёта
    """
    # Рассчитываем баллы
    scores = calculate_category_scores(analysis_history)
    
    # Формируем контекст диалога
    dialog_text = ""
    for i, item in enumerate(conversation_history, 1):
        dialog_text += f"\n\nВОПРОС {i}: {item['question']}\nОТВЕТ: {item['answer']}"
    
    # Собираем все инсайты из анализов
    all_insights = []
    all_gaps = []
    for analysis in analysis_history:
        all_insights.extend(analysis.get("key_insights", []))
        all_gaps.extend(analysis.get("gaps", []))
    
    user_prompt = f"""Проанализируй кандидата и напиши детальный отчёт.

ПРОФИЛЬ КАНДИДАТА:
- Роль: {role_name}
- Заявленный опыт: {experience}

БАЛЛЫ (рассчитаны на основе анализа ответов):
- Hard Skills: {scores['hard_skills']}/30
- Soft Skills: {scores['soft_skills']}/25
- Thinking: {scores['thinking']}/25
- Mindset: {scores['mindset']}/20
- ИТОГО: {scores['total']}/100

КЛЮЧЕВЫЕ НАБЛЮДЕНИЯ ИЗ АНАЛИЗА:
{chr(10).join('- ' + i for i in all_insights[:10]) if all_insights else '- Нет данных'}

ВЫЯВЛЕННЫЕ ПРОБЕЛЫ:
{chr(10).join('- ' + g for g in all_gaps[:5]) if all_gaps else '- Не выявлено'}

ПОЛНЫЙ ДИАЛОГ:
{dialog_text}

Напиши детальный отчёт согласно формату."""

    try:
        report = await chat_completion(
            messages=[
                {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,  # Более стабильный вывод
            max_tokens=4000,  # Увеличено для полного отчёта
        )
        
        # Проверяем, что отчёт не обрезан (заканчивается точкой или закрывающим тегом)
        report = report.strip()
        if report and not report.endswith(('.', '!', '?', '>', '»')):
            # Добавляем многоточие если обрезано
            report += "..."
            logger.warning("Report appears to be truncated, added ellipsis")
        
        return report
        
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        # Возвращаем базовый отчёт
        return generate_fallback_report(role_name, experience, scores, all_insights, all_gaps)


def generate_fallback_report(
    role_name: str,
    experience: str,
    scores: dict,
    insights: list[str],
    gaps: list[str],
) -> str:
    """Fallback отчёт если AI недоступен."""
    
    total = scores["total"]
    if total >= 80:
        level = "Senior / Lead"
    elif total >= 60:
        level = "Middle+"
    elif total >= 40:
        level = "Middle"
    else:
        level = "Junior / Junior+"
    
    insights_text = "\n".join(f"• {i}" for i in insights[:5]) if insights else "• Данные недоступны"
    gaps_text = "\n".join(f"• {g}" for g in gaps[:3]) if gaps else "• Не выявлено"
    
    return f"""<b>ОТЧЁТ О ДИАГНОСТИКЕ</b>

<b>Профиль:</b> {role_name}
<b>Опыт:</b> {experience}
<b>Оценка уровня:</b> {level}

<b>Баллы:</b>
• Hard Skills: {scores['hard_skills']}/30
• Soft Skills: {scores['soft_skills']}/25
• Thinking: {scores['thinking']}/25
• Mindset: {scores['mindset']}/20
• <b>Итого: {total}/100</b>

<b>Ключевые наблюдения:</b>
{insights_text}

<b>Зоны развития:</b>
{gaps_text}

<i>Детальный AI-анализ временно недоступен.</i>"""


def split_message(text: str, max_length: int = 4000) -> list[str]:
    """
    Разбить длинное сообщение на части для Telegram.
    
    Telegram limit: 4096 символов.
    Оставляем запас для форматирования.
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина части
        
    Returns:
        Список частей сообщения
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    # Разбиваем по параграфам
    paragraphs = text.split("\n\n")
    
    for paragraph in paragraphs:
        # Если параграф сам по себе слишком длинный
        if len(paragraph) > max_length:
            # Сначала сохраняем текущую часть
            if current_part:
                parts.append(current_part.strip())
                current_part = ""
            
            # Разбиваем длинный параграф по предложениям
            sentences = paragraph.replace(". ", ".\n").split("\n")
            for sentence in sentences:
                if len(current_part) + len(sentence) + 2 <= max_length:
                    current_part += sentence + " "
                else:
                    if current_part:
                        parts.append(current_part.strip())
                    current_part = sentence + " "
        else:
            # Проверяем, поместится ли параграф
            if len(current_part) + len(paragraph) + 2 <= max_length:
                current_part += paragraph + "\n\n"
            else:
                # Сохраняем текущую часть и начинаем новую
                if current_part:
                    parts.append(current_part.strip())
                current_part = paragraph + "\n\n"
    
    # Добавляем остаток
    if current_part:
        parts.append(current_part.strip())
    
    return parts

