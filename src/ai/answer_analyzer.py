"""
Анализатор ответов кандидата.
"""
import json
import logging
import os
from datetime import datetime
from json import JSONDecoder

from src.ai.client import chat_completion
from src.core.prompts.system import get_analysis_prompt

logger = logging.getLogger(__name__)

# Директория для debug-логов
DEBUG_LOG_DIR = "debug_logs"


def log_ai_response(prompt_type: str, response: str, success: bool) -> None:
    """
    Сохранить сырой ответ AI для отладки.
    
    Args:
        prompt_type: Тип промпта (analysis, question, report)
        response: Сырой ответ от AI
        success: Успешно ли распарсили
    """
    try:
        os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        status = "ok" if success else "fail"
        filename = f"{DEBUG_LOG_DIR}/{timestamp}_{prompt_type}_{status}.txt"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(response)
    except Exception as e:
        logger.warning(f"Failed to log AI response: {e}")


def robust_json_parse(text: str) -> dict:
    """
    Робастный парсинг JSON из ответа AI.
    
    Обрабатывает:
    - JSON в markdown блоках (```json ... ```)
    - JSON с trailing text (комментарии после JSON)
    - JSON с leading text (пояснения до JSON)
    
    Args:
        text: Сырой текст от AI
        
    Returns:
        Распарсенный словарь
        
    Raises:
        ValueError: Если не удалось найти валидный JSON
    """
    if not text or not text.strip():
        raise ValueError("Empty response")
    
    text = text.strip()
    
    # Стратегия 1: Убираем markdown code blocks
    if "```" in text:
        # Ищем ```json или просто ```
        import re
        code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
        if code_block_match:
            text = code_block_match.group(1).strip()
    
    # Стратегия 2: Прямой парсинг (если уже чистый JSON)
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    
    # Стратегия 3: JSONDecoder.raw_decode (игнорирует trailing data)
    try:
        decoder = JSONDecoder()
        # Ищем начало JSON объекта
        start_idx = text.find('{')
        if start_idx != -1:
            obj, end_idx = decoder.raw_decode(text, start_idx)
            if isinstance(obj, dict):
                return obj
    except json.JSONDecodeError:
        pass
    
    # Стратегия 4: Извлечение JSON с учётом вложенности
    brace_count = 0
    start_idx = None
    
    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx is not None:
                try:
                    candidate = text[start_idx:i+1]
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    # Продолжаем искать другой JSON
                    start_idx = None
                    continue
    
    # Ничего не сработало
    raise ValueError(f"No valid JSON found in response: {text[:200]}...")


# Дефолтный анализ на случай ошибки
DEFAULT_ANALYSIS = {
    "scores": {
        "depth": 5,
        "self_awareness": 5,
        "structure": 5,
        "honesty": 5,
        "expertise": 5,
    },
    "key_insights": ["Анализ недоступен"],
    "gaps": [],
    "hypothesis": "Требуется дополнительный анализ",
}


async def analyze_answer(question: str, answer: str, role: str) -> dict:
    """
    Проанализировать ответ кандидата.
    
    Args:
        question: Заданный вопрос
        answer: Ответ кандидата
        role: Роль (designer/product)
        
    Returns:
        Словарь с оценками и инсайтами
    """
    response = None
    
    try:
        messages = get_analysis_prompt(question, answer, role)
        
        response = await chat_completion(
            messages=messages,
            temperature=0.3,  # Более детерминированный анализ
            max_tokens=1000,
        )
        
        # Робастный парсинг JSON
        analysis = robust_json_parse(response)
        
        # Валидация структуры
        if "scores" not in analysis:
            raise ValueError("Missing 'scores' in analysis")
        
        # Валидация и нормализация значений (0-10)
        required_scores = ["depth", "self_awareness", "structure", "honesty", "expertise"]
        for key in required_scores:
            if key not in analysis["scores"]:
                analysis["scores"][key] = 5  # Дефолт если отсутствует
            else:
                value = analysis["scores"][key]
                # Проверяем тип и диапазон
                if not isinstance(value, (int, float)):
                    analysis["scores"][key] = 5
                else:
                    # Ограничиваем диапазон 0-10
                    analysis["scores"][key] = max(0, min(10, value))
        
        # Проверяем наличие других полей
        if "key_insights" not in analysis:
            analysis["key_insights"] = []
        if "gaps" not in analysis:
            analysis["gaps"] = []
        if "hypothesis" not in analysis:
            analysis["hypothesis"] = ""
        
        # Логируем успешный парсинг
        log_ai_response("analysis", response, success=True)
        
        return analysis
        
    except ValueError as e:
        logger.error(f"Failed to parse AI response: {e}")
        if response:
            log_ai_response("analysis", response, success=False)
        return DEFAULT_ANALYSIS
        
    except Exception as e:
        logger.error(f"Failed to analyze answer: {e}")
        if response:
            log_ai_response("analysis", response, success=False)
        return DEFAULT_ANALYSIS


def calculate_category_scores(analyses: list[dict]) -> dict:
    """
    Рассчитать итоговые баллы по категориям на основе всех анализов.
    
    Args:
        analyses: Список анализов всех ответов
        
    Returns:
        Словарь с итоговыми баллами по категориям
    """
    if not analyses:
        return {
            "hard_skills": 0,
            "soft_skills": 0,
            "thinking": 0,
            "mindset": 0,
            "total": 0,
        }
    
    # Собираем все оценки
    all_scores = {
        "depth": [],
        "self_awareness": [],
        "structure": [],
        "honesty": [],
        "expertise": [],
    }
    
    for analysis in analyses:
        scores = analysis.get("scores", {})
        for key in all_scores:
            if key in scores:
                all_scores[key].append(scores[key])
    
    # Средние значения
    avg = {k: sum(v) / len(v) if v else 5 for k, v in all_scores.items()}
    
    # Маппинг на категории (0-30, 0-25, 0-25, 0-20)
    # Hard Skills = expertise (30 баллов макс)
    hard_skills = round(avg["expertise"] * 3)  # 0-10 -> 0-30
    
    # Soft Skills = (self_awareness + honesty) / 2 (25 баллов макс)
    soft_skills = round((avg["self_awareness"] + avg["honesty"]) / 2 * 2.5)  # 0-10 -> 0-25
    
    # Thinking = (structure + depth) / 2 (25 баллов макс)
    thinking = round((avg["structure"] + avg["depth"]) / 2 * 2.5)  # 0-10 -> 0-25
    
    # Mindset = (self_awareness + honesty) / 2 (20 баллов макс)
    # Немного другой расчёт для разнообразия
    mindset = round((avg["self_awareness"] * 0.6 + avg["honesty"] * 0.4) * 2)  # 0-10 -> 0-20
    
    total = hard_skills + soft_skills + thinking + mindset
    
    return {
        "hard_skills": min(hard_skills, 30),
        "soft_skills": min(soft_skills, 25),
        "thinking": min(thinking, 25),
        "mindset": min(mindset, 20),
        "total": min(total, 100),
        "raw_averages": avg,  # Для отладки
    }

