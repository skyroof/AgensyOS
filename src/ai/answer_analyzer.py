"""
Анализатор ответов кандидата.
"""
import json
import logging

from src.ai.client import chat_completion
from src.core.prompts.system import get_analysis_prompt

logger = logging.getLogger(__name__)


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
    try:
        messages = get_analysis_prompt(question, answer, role)
        
        response = await chat_completion(
            messages=messages,
            temperature=0.3,  # Более детерминированный анализ
            max_tokens=1000,
        )
        
        # Парсим JSON из ответа
        # Иногда AI оборачивает в ```json ... ```
        clean_response = response.strip()
        if clean_response.startswith("```"):
            # Убираем markdown code block
            lines = clean_response.split("\n")
            clean_response = "\n".join(lines[1:-1])
        
        analysis = json.loads(clean_response)
        
        # Валидация структуры
        if "scores" not in analysis:
            raise ValueError("Missing 'scores' in analysis")
            
        return analysis
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        return DEFAULT_ANALYSIS
        
    except Exception as e:
        logger.error(f"Failed to analyze answer: {e}")
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

