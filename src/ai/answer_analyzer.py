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
        import re
        # Ищем ```json ... ``` (жадный поиск до последнего ```)
        code_block_match = re.search(r'```(?:json)?\s*\n([\s\S]+?)\n```', text)
        if code_block_match:
            text = code_block_match.group(1).strip()
        else:
            # Попробуем без переноса строки
            code_block_match = re.search(r'```(?:json)?\s*([\s\S]+?)```', text)
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


# Все 12 метрик
ALL_METRICS = [
    # Hard Skills
    "expertise",
    "methodology", 
    "tools_proficiency",
    # Soft Skills
    "articulation",
    "self_awareness",
    "conflict_handling",
    # Thinking
    "depth",
    "structure",
    "systems_thinking",
    "creativity",
    # Mindset
    "honesty",
    "growth_orientation",
]

# Все паттерны поведения
ALL_PATTERNS = ["rehearsed", "evasive", "overconfident", "defensive", "authentic"]

# Русские названия паттернов
PATTERN_NAMES_RU = {
    "rehearsed": "🎭 Заученный ответ",
    "evasive": "🌊 Уклончивость",
    "overconfident": "💪 Самоуверенность",
    "defensive": "🛡️ Защитная позиция",
    "authentic": "💎 Аутентичность",
}

# Влияние паттернов на метрики (корректировки)
PATTERN_ADJUSTMENTS = {
    "rehearsed": {"honesty": -1, "self_awareness": -1},
    "evasive": {"honesty": -2, "depth": -1},
    "overconfident": {"self_awareness": -2, "growth_orientation": -1},
    "defensive": {"honesty": -1, "self_awareness": -1, "growth_orientation": -1},
    "authentic": {"honesty": +1, "self_awareness": +1},  # Позитивный бонус
}

# Русские названия метрик для отчёта
METRIC_NAMES_RU = {
    # Hard Skills
    "expertise": "Экспертиза",
    "methodology": "Методологии",
    "tools_proficiency": "Инструменты",
    # Soft Skills
    "articulation": "Ясность речи",
    "self_awareness": "Самоосознание",
    "conflict_handling": "Работа с конфликтами",
    # Thinking
    "depth": "Глубина анализа",
    "structure": "Структурность",
    "systems_thinking": "Системное мышление",
    "creativity": "Креативность",
    # Mindset
    "honesty": "Честность",
    "growth_orientation": "Ориентация на рост",
}

# Группировка метрик по категориям
METRIC_CATEGORIES = {
    "hard_skills": {
        "name": "🔧 Hard Skills",
        "metrics": ["expertise", "methodology", "tools_proficiency"],
        "max_score": 30,
    },
    "soft_skills": {
        "name": "🤝 Soft Skills", 
        "metrics": ["articulation", "self_awareness", "conflict_handling"],
        "max_score": 25,
    },
    "thinking": {
        "name": "🧠 Мышление",
        "metrics": ["depth", "structure", "systems_thinking", "creativity"],
        "max_score": 25,
    },
    "mindset": {
        "name": "💫 Mindset",
        "metrics": ["honesty", "growth_orientation"],
        "max_score": 20,
    },
}

# Дефолтный анализ на случай ошибки
DEFAULT_ANALYSIS = {
    "scores": {metric: 5 for metric in ALL_METRICS},
    "patterns": {pattern: False for pattern in ALL_PATTERNS},
    "detected_patterns": [],
    "key_insights": ["Анализ недоступен"],
    "gaps": [],
    "red_flags": [],
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
        
        # Валидация и нормализация значений (0-10) для всех 12 метрик
        for metric in ALL_METRICS:
            if metric not in analysis["scores"]:
                analysis["scores"][metric] = 5  # Дефолт если отсутствует
            else:
                value = analysis["scores"][metric]
                # Проверяем тип и диапазон
                if not isinstance(value, (int, float)):
                    analysis["scores"][metric] = 5
                else:
                    # Ограничиваем диапазон 0-10
                    analysis["scores"][metric] = max(0, min(10, value))
        
        # Проверяем наличие других полей
        if "key_insights" not in analysis:
            analysis["key_insights"] = []
        if "gaps" not in analysis:
            analysis["gaps"] = []
        if "red_flags" not in analysis:
            analysis["red_flags"] = []
        if "hypothesis" not in analysis:
            analysis["hypothesis"] = ""
        
        # === ОБРАБОТКА ПАТТЕРНОВ ===
        if "patterns" not in analysis:
            analysis["patterns"] = {p: False for p in ALL_PATTERNS}
        else:
            # Валидация паттернов
            for pattern in ALL_PATTERNS:
                if pattern not in analysis["patterns"]:
                    analysis["patterns"][pattern] = False
                elif not isinstance(analysis["patterns"][pattern], bool):
                    analysis["patterns"][pattern] = False
        
        # Применяем корректировки на основе паттернов
        detected_patterns = []
        for pattern, is_detected in analysis["patterns"].items():
            if is_detected and pattern in PATTERN_ADJUSTMENTS:
                detected_patterns.append(pattern)
                adjustments = PATTERN_ADJUSTMENTS[pattern]
                for metric, delta in adjustments.items():
                    if metric in analysis["scores"]:
                        new_value = analysis["scores"][metric] + delta
                        analysis["scores"][metric] = max(0, min(10, new_value))
        
        # Логируем найденные паттерны
        if detected_patterns:
            logger.info(f"Detected patterns: {detected_patterns}")
            analysis["detected_patterns"] = detected_patterns
        else:
            analysis["detected_patterns"] = []
        
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
    
    12 метрик → 4 категории:
    - Hard Skills (30): expertise, methodology, tools_proficiency
    - Soft Skills (25): articulation, self_awareness, conflict_handling
    - Thinking (25): depth, structure, systems_thinking, creativity
    - Mindset (20): honesty, growth_orientation
    
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
    
    # Собираем все оценки по 12 метрикам
    all_scores = {metric: [] for metric in ALL_METRICS}
    
    for analysis in analyses:
        scores = analysis.get("scores", {})
        for metric in ALL_METRICS:
            if metric in scores:
                all_scores[metric].append(scores[metric])
    
    # Средние значения для каждой метрики
    avg = {k: sum(v) / len(v) if v else 5 for k, v in all_scores.items()}
    
    # === МАППИНГ НА КАТЕГОРИИ ===
    
    # Hard Skills (30 баллов) = среднее из 3 метрик × 3
    hard_skills_avg = (avg["expertise"] + avg["methodology"] + avg["tools_proficiency"]) / 3
    hard_skills = round(hard_skills_avg * 3)  # 0-10 -> 0-30
    
    # Soft Skills (25 баллов) = среднее из 3 метрик × 2.5
    soft_skills_avg = (avg["articulation"] + avg["self_awareness"] + avg["conflict_handling"]) / 3
    soft_skills = round(soft_skills_avg * 2.5)  # 0-10 -> 0-25
    
    # Thinking (25 баллов) = среднее из 4 метрик × 2.5
    thinking_avg = (avg["depth"] + avg["structure"] + avg["systems_thinking"] + avg["creativity"]) / 4
    thinking = round(thinking_avg * 2.5)  # 0-10 -> 0-25
    
    # Mindset (20 баллов) = среднее из 2 метрик × 2
    mindset_avg = (avg["honesty"] + avg["growth_orientation"]) / 2
    mindset = round(mindset_avg * 2)  # 0-10 -> 0-20
    
    total = hard_skills + soft_skills + thinking + mindset
    
    return {
        "hard_skills": min(hard_skills, 30),
        "soft_skills": min(soft_skills, 25),
        "thinking": min(thinking, 25),
        "mindset": min(mindset, 20),
        "total": min(total, 100),
        "raw_averages": avg,  # Все 12 метрик для детального отчёта
    }


# Ожидаемые баллы для каждого уровня опыта
EXPERIENCE_BASELINES = {
    "junior": {
        "expected_total": 35,  # Ожидаемый балл для Junior
        "exceeds_threshold": 50,  # Если выше — превышает ожидания
        "below_threshold": 25,  # Если ниже — ниже ожиданий
        "level_name": "Junior",
    },
    "middle": {
        "expected_total": 55,
        "exceeds_threshold": 70,
        "below_threshold": 40,
        "level_name": "Middle",
    },
    "senior": {
        "expected_total": 70,
        "exceeds_threshold": 85,
        "below_threshold": 55,
        "level_name": "Senior",
    },
    "lead": {
        "expected_total": 80,
        "exceeds_threshold": 90,
        "below_threshold": 65,
        "level_name": "Lead",
    },
}


def calibrate_scores(scores: dict, experience: str) -> dict:
    """
    Калибровать оценки относительно ожиданий для уровня опыта.
    
    Args:
        scores: Словарь с баллами из calculate_category_scores()
        experience: Уровень опыта (junior/middle/senior/lead)
        
    Returns:
        Словарь с добавленной калибровкой:
        - expectation: "exceeds" / "meets" / "below"
        - expectation_ru: русское описание
        - expected_total: ожидаемый балл для этого уровня
        - delta: разница с ожиданием
        - percentile_in_level: условный перцентиль внутри уровня
    """
    baseline = EXPERIENCE_BASELINES.get(experience, EXPERIENCE_BASELINES["middle"])
    total = scores.get("total", 0)
    
    # Определяем соответствие ожиданиям
    if total >= baseline["exceeds_threshold"]:
        expectation = "exceeds"
        expectation_ru = "🚀 Превышает ожидания"
        expectation_emoji = "🟢"
    elif total >= baseline["below_threshold"]:
        expectation = "meets"
        expectation_ru = "✅ Соответствует уровню"
        expectation_emoji = "🟡"
    else:
        expectation = "below"
        expectation_ru = "📈 Есть зоны для роста"
        expectation_emoji = "🟠"
    
    # Рассчитываем дельту относительно ожидания
    delta = total - baseline["expected_total"]
    delta_text = f"+{delta}" if delta > 0 else str(delta)
    
    # Условный перцентиль внутри уровня (0-100)
    # Формула: (total - below) / (exceeds - below) * 100
    range_size = baseline["exceeds_threshold"] - baseline["below_threshold"]
    if range_size > 0:
        percentile = ((total - baseline["below_threshold"]) / range_size) * 100
        percentile = max(0, min(100, percentile))
    else:
        percentile = 50
    
    # Добавляем калибровку к существующим scores
    calibrated = scores.copy()
    calibrated.update({
        "experience": experience,
        "experience_level": baseline["level_name"],
        "expectation": expectation,
        "expectation_ru": expectation_ru,
        "expectation_emoji": expectation_emoji,
        "expected_total": baseline["expected_total"],
        "delta": delta,
        "delta_text": delta_text,
        "percentile_in_level": round(percentile),
    })
    
    return calibrated

