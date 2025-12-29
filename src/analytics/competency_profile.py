"""
Профиль компетенций — глубокий анализ на основе диагностики.

Включает:
- Детальные оценки по 12 метрикам
- Топ-3 сильных стороны и зоны роста
- Психологический профиль (стили мышления и коммуникации)
- Персонализированный план развития
- Рекомендуемые ресурсы
"""
from dataclasses import dataclass, field
from typing import Optional
import re

from src.ai.answer_analyzer import (
    ALL_METRICS,
    METRIC_NAMES_RU,
    METRIC_CATEGORIES,
    PATTERN_NAMES_RU,
)


@dataclass
class CompetencyProfile:
    """Полный профиль компетенций на основе диагностики."""
    
    # === БАЗОВЫЕ ДАННЫЕ ===
    role: str  # designer / product
    role_name: str  # Дизайнер / Продакт-менеджер
    experience: str  # junior / middle / senior / lead
    experience_name: str  # до 1 года / 1-3 года / ...
    total_score: int  # 0-100
    
    # === ДЕТАЛЬНЫЕ ОЦЕНКИ ПО КАТЕГОРИЯМ ===
    # Каждая категория содержит метрики со значениями 0-10
    hard_skills: dict[str, float] = field(default_factory=dict)
    soft_skills: dict[str, float] = field(default_factory=dict)
    thinking: dict[str, float] = field(default_factory=dict)
    mindset: dict[str, float] = field(default_factory=dict)
    
    # Баллы по категориям (0-30, 0-25, 0-25, 0-20)
    hard_skills_score: int = 0
    soft_skills_score: int = 0
    thinking_score: int = 0
    mindset_score: int = 0
    
    # === ТОП СИЛЬНЫХ СТОРОН И ЗОН РОСТА ===
    strengths: list[str] = field(default_factory=list)  # Топ-3 метрики
    strengths_descriptions: list[str] = field(default_factory=list)
    growth_areas: list[str] = field(default_factory=list)  # Топ-3 метрики
    growth_areas_descriptions: list[str] = field(default_factory=list)
    
    # === ВЫЯВЛЕННЫЕ ПАТТЕРНЫ ===
    detected_patterns: list[str] = field(default_factory=list)
    
    # === ПСИХОЛОГИЧЕСКИЙ ПРОФИЛЬ ===
    thinking_style: str = "balanced"  # analytical / creative / strategic / tactical / balanced
    thinking_style_description: str = ""
    
    communication_style: str = "balanced"  # direct / diplomatic / reserved / balanced
    communication_style_description: str = ""
    
    decision_style: str = "balanced"  # data_driven / intuitive / collaborative / balanced
    decision_style_description: str = ""
    
    motivation_driver: str = "growth"  # growth / impact / recognition / stability / mastery
    motivation_description: str = ""
    
    # === УРОВЕНЬ ===
    level: str = "Middle"  # Junior / Junior+ / Middle / Middle+ / Senior / Lead
    level_match: str = "meets"  # exceeds / meets / below
    level_match_description: str = ""
    
    # === ПЛАН РАЗВИТИЯ ===
    development_plan: list[str] = field(default_factory=list)  # 3-5 конкретных рекомендаций
    
    # === РЕКОМЕНДУЕМЫЕ РЕСУРСЫ ===
    recommended_resources: list[dict] = field(default_factory=list)
    # Формат: {"type": "book/course/practice", "title": "...", "reason": "..."}
    
    def get_level_emoji(self) -> str:
        """Эмодзи для уровня."""
        level_emojis = {
            "Junior": "🌱",
            "Junior+": "🌱",
            "Middle": "📈",
            "Middle+": "💪",
            "Senior": "🏆",
            "Lead": "👑",
        }
        return level_emojis.get(self.level, "📊")
    
    def get_match_emoji(self) -> str:
        """Эмодзи для соответствия уровню."""
        match_emojis = {
            "exceeds": "🚀",
            "meets": "✅",
            "below": "📈",
        }
        return match_emojis.get(self.level_match, "📊")


# === ОПИСАНИЯ ДЛЯ МЕТРИК ===

STRENGTH_DESCRIPTIONS = {
    "expertise": "Глубокое понимание предметной области, способность решать сложные профессиональные задачи",
    "methodology": "Владение современными методологиями и фреймворками, системный подход к работе",
    "tools_proficiency": "Уверенное владение профессиональными инструментами, высокая продуктивность",
    "articulation": "Ясное и структурированное изложение мыслей, убедительная коммуникация",
    "self_awareness": "Честная самооценка, понимание своих сильных сторон и зон развития",
    "conflict_handling": "Умение эффективно разрешать конфликты и находить win-win решения",
    "depth": "Способность к глубокому анализу, выявление неочевидных связей и причин",
    "structure": "Логичное и последовательное мышление, умение декомпозировать задачи",
    "systems_thinking": "Видение системы целиком, понимание взаимосвязей между элементами",
    "creativity": "Генерация нестандартных идей, инновационный подход к решению задач",
    "honesty": "Искренность и аутентичность, готовность признавать ошибки",
    "growth_orientation": "Активное стремление к развитию, обучение на опыте",
}

GROWTH_DESCRIPTIONS = {
    "expertise": "Углубить знания в предметной области, изучить best practices индустрии",
    "methodology": "Освоить современные методологии, внедрить системный подход",
    "tools_proficiency": "Расширить инструментарий, освоить продвинутые техники",
    "articulation": "Развить навыки презентации и аргументации",
    "self_awareness": "Практиковать рефлексию, собирать обратную связь",
    "conflict_handling": "Изучить техники медиации и переговоров",
    "depth": "Развивать аналитическое мышление, практиковать root cause analysis",
    "structure": "Освоить фреймворки структурирования (MECE, пирамида Минто)",
    "systems_thinking": "Изучать системный подход, практиковать systems mapping",
    "creativity": "Развивать креативность через design thinking и латеральное мышление",
    "honesty": "Практиковать открытость, создавать культуру психологической безопасности",
    "growth_orientation": "Выстроить систему личного развития, найти менторов",
}


# === СТИЛИ И ИХ ДЕТЕКЦИЯ ===

THINKING_STYLES = {
    "analytical": {
        "name": "Аналитический",
        "description": "Ты предпочитаешь глубокий анализ данных, логические выводы и обоснованные решения. "
                       "Сильная сторона — способность разобраться в сложных вопросах. "
                       "Риск — иногда можешь затягивать с решениями в погоне за идеальной информацией.",
        "indicators": {"depth": 7, "structure": 7, "systems_thinking": 6},
    },
    "creative": {
        "name": "Креативный",
        "description": "Ты генерируешь нестандартные идеи и видишь возможности там, где другие видят ограничения. "
                       "Сильная сторона — инновационность. "
                       "Риск — идеи могут быть оторваны от реальности без должной проверки.",
        "indicators": {"creativity": 7, "depth": 5},
    },
    "strategic": {
        "name": "Стратегический",
        "description": "Ты мыслишь на уровне системы и видишь долгосрочные последствия решений. "
                       "Сильная сторона — способность выстраивать видение. "
                       "Риск — иногда можешь упускать тактические детали.",
        "indicators": {"systems_thinking": 7, "depth": 6},
    },
    "tactical": {
        "name": "Тактический",
        "description": "Ты фокусируешься на конкретных задачах и эффективном исполнении. "
                       "Сильная сторона — результативность. "
                       "Риск — можешь упустить стратегический контекст.",
        "indicators": {"expertise": 7, "methodology": 6},
    },
    "balanced": {
        "name": "Сбалансированный",
        "description": "Ты гибко адаптируешь стиль мышления под задачу — "
                       "можешь и глубоко анализировать, и генерировать идеи, и мыслить системно.",
        "indicators": {},
    },
}

COMMUNICATION_STYLES = {
    "direct": {
        "name": "Прямой",
        "description": "Ты говоришь чётко и по делу, не боишься озвучивать непопулярные мнения. "
                       "Сильная сторона — ясность. Риск — может восприниматься как резкость.",
        "indicators": {"articulation": 7, "honesty": 7},
    },
    "diplomatic": {
        "name": "Дипломатичный",
        "description": "Ты умеешь находить общий язык с разными людьми и строить мосты между позициями. "
                       "Сильная сторона — гармония. Риск — иногда можешь избегать важных разговоров.",
        "indicators": {"conflict_handling": 7, "self_awareness": 6},
    },
    "reserved": {
        "name": "Сдержанный",
        "description": "Ты предпочитаешь наблюдать и обдумывать, прежде чем высказываться. "
                       "Сильная сторона — взвешенность. Риск — голос может быть не услышан.",
        "indicators": {"depth": 6, "articulation": 4},
    },
    "balanced": {
        "name": "Адаптивный",
        "description": "Ты гибко подстраиваешь стиль коммуникации под ситуацию и аудиторию.",
        "indicators": {},
    },
}

DECISION_STYLES = {
    "data_driven": {
        "name": "Основан на данных",
        "description": "Ты принимаешь решения на основе фактов, метрик и исследований.",
        "indicators": {"methodology": 7, "structure": 7},
    },
    "intuitive": {
        "name": "Интуитивный",
        "description": "Ты доверяешь экспертной интуиции, сформированной опытом.",
        "indicators": {"expertise": 7, "creativity": 6},
    },
    "collaborative": {
        "name": "Коллаборативный",
        "description": "Ты предпочитаешь принимать решения совместно с командой.",
        "indicators": {"conflict_handling": 6, "self_awareness": 6},
    },
    "balanced": {
        "name": "Смешанный",
        "description": "Ты комбинируешь данные, интуицию и мнение команды.",
        "indicators": {},
    },
}

MOTIVATION_DRIVERS = {
    "growth": {
        "name": "Рост и развитие",
        "description": "Тебя мотивирует постоянное обучение и расширение компетенций.",
        "indicators": {"growth_orientation": 7},
    },
    "impact": {
        "name": "Влияние и результат",
        "description": "Тебя мотивирует видеть реальный эффект своей работы для пользователей и бизнеса.",
        "indicators": {"systems_thinking": 7, "depth": 6},
    },
    "mastery": {
        "name": "Мастерство",
        "description": "Тебя мотивирует достижение экспертного уровня в своей области.",
        "indicators": {"expertise": 7, "methodology": 6},
    },
    "recognition": {
        "name": "Признание",
        "description": "Тебя мотивирует признание результатов и вклада.",
        "indicators": {"articulation": 7},
    },
    "stability": {
        "name": "Стабильность",
        "description": "Тебя мотивирует предсказуемость и структурированность процессов.",
        "indicators": {"structure": 7, "methodology": 6},
    },
}


# === РЕСУРСЫ ДЛЯ РАЗВИТИЯ ===

DEVELOPMENT_RESOURCES = {
    # Hard Skills
    "expertise": {
        "designer": [
            {"type": "book", "title": "Don't Make Me Think — Steve Krug", "reason": "Основы UX-мышления"},
            {"type": "course", "title": "Google UX Design Certificate", "reason": "Системное обучение UX"},
            {"type": "practice", "title": "Ежедневный UI challenge (Daily UI)", "reason": "Практика дизайна"},
        ],
        "product": [
            {"type": "book", "title": "Inspired — Marty Cagan", "reason": "Библия продакт-менеджмента"},
            {"type": "course", "title": "Reforge Product Strategy", "reason": "Продвинутая стратегия продукта"},
            {"type": "practice", "title": "Разбор продуктовых кейсов (Lenny's Newsletter)", "reason": "Насмотренность"},
        ],
    },
    "methodology": {
        "designer": [
            {"type": "book", "title": "Sprint — Jake Knapp", "reason": "Дизайн-спринты"},
            {"type": "course", "title": "IDEO Design Thinking", "reason": "Методология Design Thinking"},
        ],
        "product": [
            {"type": "book", "title": "Lean Analytics — Alistair Croll", "reason": "Метрики и аналитика"},
            {"type": "course", "title": "Product Analytics Micro-Certification", "reason": "Работа с данными"},
        ],
    },
    "tools_proficiency": {
        "designer": [
            {"type": "course", "title": "Figma Advanced Techniques", "reason": "Прокачка основного инструмента"},
            {"type": "practice", "title": "Создание дизайн-системы с нуля", "reason": "Практика систем"},
        ],
        "product": [
            {"type": "course", "title": "SQL для продактов", "reason": "Самостоятельная работа с данными"},
            {"type": "practice", "title": "A/B тестирование на реальных фичах", "reason": "Эксперименты"},
        ],
    },
    # Soft Skills
    "articulation": [
        {"type": "book", "title": "Пирамида Минто — Барбара Минто", "reason": "Структурирование мыслей"},
        {"type": "practice", "title": "Еженедельные презентации (toastmasters)", "reason": "Навык публичных выступлений"},
    ],
    "self_awareness": [
        {"type": "book", "title": "Insight — Tasha Eurich", "reason": "Развитие самоосознания"},
        {"type": "practice", "title": "Регулярные 360° ревью", "reason": "Обратная связь от окружающих"},
    ],
    "conflict_handling": [
        {"type": "book", "title": "Crucial Conversations", "reason": "Техники сложных разговоров"},
        {"type": "practice", "title": "Практика NVC (ненасильственное общение)", "reason": "Конструктивный диалог"},
    ],
    # Thinking
    "depth": [
        {"type": "book", "title": "Thinking, Fast and Slow — Kahneman", "reason": "Понимание когнитивных искажений"},
        {"type": "practice", "title": "5 Whys для каждой проблемы", "reason": "Root cause analysis"},
    ],
    "structure": [
        {"type": "book", "title": "The Pyramid Principle — Barbara Minto", "reason": "Структурное мышление"},
        {"type": "practice", "title": "MECE-декомпозиция задач", "reason": "Системность в работе"},
    ],
    "systems_thinking": [
        {"type": "book", "title": "Thinking in Systems — Donella Meadows", "reason": "Основы системного мышления"},
        {"type": "practice", "title": "Создание системных карт (causal loop diagrams)", "reason": "Визуализация систем"},
    ],
    "creativity": [
        {"type": "book", "title": "Lateral Thinking — Edward de Bono", "reason": "Техники креативности"},
        {"type": "practice", "title": "Brainstorming с ограничениями (Crazy 8s)", "reason": "Генерация идей"},
    ],
    # Mindset
    "honesty": [
        {"type": "book", "title": "Radical Candor — Kim Scott", "reason": "Культура честной обратной связи"},
        {"type": "practice", "title": "Проводить ретроспективы с анализом своих ошибок", "reason": "Практика честности"},
    ],
    "growth_orientation": [
        {"type": "book", "title": "Mindset — Carol Dweck", "reason": "Growth vs Fixed mindset"},
        {"type": "practice", "title": "Learning journal + weekly reflection", "reason": "Систематизация обучения"},
    ],
}


def _detect_style(
    scores: dict[str, float],
    styles: dict,
    threshold: float = 6.5,
) -> tuple[str, str]:
    """
    Определить стиль на основе индикаторов.
    
    Returns:
        (style_key, description)
    """
    # Берём первый ключ как дефолт (вместо несуществующего "balanced")
    default_key = next(iter(styles.keys()))
    best_match = None
    best_score = 0
    
    for style_key, style_data in styles.items():
        indicators = style_data.get("indicators", {})
        if not indicators:
            continue
        
        # Считаем совпадение индикаторов
        match_score = 0
        total_indicators = 0
        
        for metric, min_value in indicators.items():
            if metric in scores:
                total_indicators += 1
                if scores[metric] >= min_value:
                    match_score += 1
                elif scores[metric] >= min_value - 1:
                    match_score += 0.5
        
        if total_indicators > 0:
            match_ratio = match_score / total_indicators
            if match_ratio > best_score and match_ratio >= 0.6:
                best_score = match_ratio
                best_match = style_key
    
    # Если не нашли подходящий стиль, используем дефолтный
    if best_match is None:
        best_match = default_key
    
    style_data = styles.get(best_match, {})
    return best_match, style_data.get("description", "")


def _get_top_metrics(
    scores: dict[str, float],
    n: int = 3,
    ascending: bool = False,
) -> list[str]:
    """Получить топ-N метрик по значению."""
    sorted_metrics = sorted(
        [(k, v) for k, v in scores.items() if k in ALL_METRICS],
        key=lambda x: x[1],
        reverse=not ascending,
    )
    return [m[0] for m in sorted_metrics[:n]]


def _determine_level(total_score: int, experience: str) -> tuple[str, str, str]:
    """
    Определить уровень и соответствие.
    
    Returns:
        (level, match, match_description)
    """
    # Ожидаемые баллы по уровням
    expectations = {
        "junior": {"min": 20, "expected": 35, "max": 50},
        "middle": {"min": 40, "expected": 55, "max": 70},
        "senior": {"min": 55, "expected": 70, "max": 85},
        "lead": {"min": 65, "expected": 80, "max": 95},
    }
    
    # Определяем реальный уровень по баллу
    if total_score >= 80:
        actual_level = "Senior" if total_score < 90 else "Lead"
    elif total_score >= 65:
        actual_level = "Senior" if total_score >= 75 else "Middle+"
    elif total_score >= 50:
        actual_level = "Middle+" if total_score >= 60 else "Middle"
    elif total_score >= 35:
        actual_level = "Middle" if total_score >= 45 else "Junior+"
    else:
        actual_level = "Junior+" if total_score >= 25 else "Junior"
    
    # Определяем соответствие заявленному опыту
    exp_data = expectations.get(experience, expectations["middle"])
    
    if total_score >= exp_data["max"]:
        match = "exceeds"
        match_desc = f"🚀 Результат значительно превышает ожидания для уровня {experience}"
    elif total_score >= exp_data["expected"]:
        match = "meets"
        match_desc = f"✅ Результат соответствует уровню {experience}"
    elif total_score >= exp_data["min"]:
        match = "meets"
        match_desc = f"📊 Результат в рамках ожиданий для {experience}, есть потенциал роста"
    else:
        match = "below"
        match_desc = f"📈 Результат ниже ожиданий для {experience}, рекомендуется сфокусироваться на развитии"
    
    return actual_level, match, match_desc


def _generate_development_plan(
    growth_areas: list[str],
    role: str,
    experience: str,
) -> list[str]:
    """Сгенерировать персонализированный план развития."""
    plan = []
    
    # Базовые рекомендации по зонам роста
    area_recommendations = {
        "expertise": {
            "junior": "Сфокусируйся на изучении основ профессии через практику и менторство",
            "middle": "Углубляй экспертизу в своей нише, изучай смежные области",
            "senior": "Развивай T-shaped профиль: глубокая экспертиза + широкий кругозор",
            "lead": "Делись экспертизой через менторство и создание контента",
        },
        "methodology": {
            "junior": "Освой 1-2 базовых фреймворка (Design Thinking / Agile) и применяй на практике",
            "middle": "Экспериментируй с разными методологиями, найди свой стиль",
            "senior": "Адаптируй методологии под контекст, создавай гибридные подходы",
            "lead": "Выстраивай процессы в команде, обучай других методологиям",
        },
        "articulation": {
            "junior": "Практикуйся в презентациях, записывай и анализируй своё выступление",
            "middle": "Развивай навык storytelling, учись продавать идеи",
            "senior": "Адаптируй коммуникацию под разные аудитории (C-level, разработчики, клиенты)",
            "lead": "Развивай публичные выступления, выстраивай нарратив команды",
        },
        "depth": {
            "junior": "Задавай вопрос 'Почему?' минимум 5 раз к каждой проблеме",
            "middle": "Используй root cause analysis, ищи системные причины",
            "senior": "Развивай аналитическое мышление через сложные кейсы",
            "lead": "Обучай команду глубокому анализу, создавай культуру inquiry",
        },
        "systems_thinking": {
            "junior": "Изучай бизнес-контекст своих задач, общайся с другими командами",
            "middle": "Рисуй системные карты, ищи неочевидные взаимосвязи",
            "senior": "Мысли на уровне продукта/бизнеса, а не отдельных фич",
            "lead": "Выстраивай системы и процессы, думай об организации в целом",
        },
        "growth_orientation": {
            "junior": "Создай learning plan на 6 месяцев с конкретными целями",
            "middle": "Найди ментора, регулярно рефлексируй над прогрессом",
            "senior": "Выходи из зоны комфорта, бери челленджи в новых областях",
            "lead": "Развивай других, учись через менторство",
        },
        "honesty": {
            "junior": "Практикуй открытость: признавай, когда чего-то не знаешь",
            "middle": "Делись своими ошибками на ретроспективах, нормализуй это",
            "senior": "Создавай культуру психологической безопасности в команде",
            "lead": "Будь примером уязвимости и честности для команды",
        },
        "self_awareness": {
            "junior": "Запрашивай регулярный feedback, веди дневник рефлексии",
            "middle": "Проводи 360° ревью, работай с коучем или ментором",
            "senior": "Развивай эмоциональный интеллект, изучай свои триггеры",
            "lead": "Практикуй servant leadership, осознавай своё влияние на команду",
        },
    }
    
    for area in growth_areas[:3]:
        recommendations = area_recommendations.get(area, {})
        rec = recommendations.get(experience, recommendations.get("middle", ""))
        if rec:
            plan.append(rec)
    
    # Добавляем общую рекомендацию
    if experience == "junior":
        plan.append("🎯 Главный фокус: набирай практический опыт и учись у сильных специалистов")
    elif experience == "middle":
        plan.append("🎯 Главный фокус: углубляй экспертизу и развивай soft skills для перехода на senior")
    elif experience == "senior":
        plan.append("🎯 Главный фокус: развивай influence и готовься к leadership роли")
    else:  # lead
        plan.append("🎯 Главный фокус: масштабируй себя через команду, развивай стратегическое мышление")
    
    return plan


def _get_recommended_resources(
    growth_areas: list[str],
    role: str,
) -> list[dict]:
    """Получить рекомендуемые ресурсы для развития."""
    resources = []
    
    for area in growth_areas[:3]:
        area_resources = DEVELOPMENT_RESOURCES.get(area, [])
        
        # Если есть специфичные для роли
        if isinstance(area_resources, dict):
            role_resources = area_resources.get(role, area_resources.get("designer", []))
        else:
            role_resources = area_resources
        
        for res in role_resources[:1]:  # Берём по 1 ресурсу на зону
            resources.append(res)
    
    return resources


def build_profile(
    role: str,
    role_name: str,
    experience: str,
    experience_name: str,
    scores: dict,
    analysis_history: list[dict],
) -> CompetencyProfile:
    """
    Построить полный профиль компетенций на основе диагностики.
    
    Args:
        role: Роль (designer/product)
        role_name: Название роли
        experience: Уровень опыта (junior/middle/senior/lead)
        experience_name: Название уровня опыта
        scores: Словарь с баллами из calculate_category_scores()
        analysis_history: История анализов всех ответов
    
    Returns:
        CompetencyProfile с полным анализом
    """
    # Извлекаем сырые средние
    raw_averages = scores.get("raw_averages", {})
    
    # Если нет raw_averages — вычисляем из analysis_history
    if not raw_averages and analysis_history:
        all_scores = {metric: [] for metric in ALL_METRICS}
        for analysis in analysis_history:
            for metric in ALL_METRICS:
                if metric in analysis.get("scores", {}):
                    all_scores[metric].append(analysis["scores"][metric])
        raw_averages = {k: sum(v) / len(v) if v else 5 for k, v in all_scores.items()}
    
    # Группируем по категориям
    hard_skills = {m: raw_averages.get(m, 5) for m in ["expertise", "methodology", "tools_proficiency"]}
    soft_skills = {m: raw_averages.get(m, 5) for m in ["articulation", "self_awareness", "conflict_handling"]}
    thinking = {m: raw_averages.get(m, 5) for m in ["depth", "structure", "systems_thinking", "creativity"]}
    mindset = {m: raw_averages.get(m, 5) for m in ["honesty", "growth_orientation"]}
    
    # Топ сильных сторон и зон роста
    strengths = _get_top_metrics(raw_averages, n=3, ascending=False)
    growth_areas = _get_top_metrics(raw_averages, n=3, ascending=True)
    
    # Описания для сильных сторон
    strengths_descriptions = [
        f"<b>{METRIC_NAMES_RU.get(m, m)}</b>: {STRENGTH_DESCRIPTIONS.get(m, '')}"
        for m in strengths
    ]
    
    growth_areas_descriptions = [
        f"<b>{METRIC_NAMES_RU.get(m, m)}</b>: {GROWTH_DESCRIPTIONS.get(m, '')}"
        for m in growth_areas
    ]
    
    # Собираем паттерны из анализов
    detected_patterns = []
    for analysis in analysis_history:
        patterns = analysis.get("detected_patterns", [])
        detected_patterns.extend(patterns)
    detected_patterns = list(set(detected_patterns))  # Убираем дубли
    
    # Определяем стили
    thinking_style, thinking_desc = _detect_style(raw_averages, THINKING_STYLES)
    comm_style, comm_desc = _detect_style(raw_averages, COMMUNICATION_STYLES)
    decision_style, decision_desc = _detect_style(raw_averages, DECISION_STYLES)
    
    # Определяем мотивацию
    motivation, motivation_desc = _detect_style(raw_averages, MOTIVATION_DRIVERS)
    
    # Определяем уровень
    total_score = scores.get("total", 50)
    level, level_match, level_match_desc = _determine_level(total_score, experience)
    
    # Генерируем план развития
    development_plan = _generate_development_plan(growth_areas, role, experience)
    
    # Подбираем ресурсы
    recommended_resources = _get_recommended_resources(growth_areas, role)
    
    return CompetencyProfile(
        role=role,
        role_name=role_name,
        experience=experience,
        experience_name=experience_name,
        total_score=total_score,
        hard_skills=hard_skills,
        soft_skills=soft_skills,
        thinking=thinking,
        mindset=mindset,
        hard_skills_score=scores.get("hard_skills", 0),
        soft_skills_score=scores.get("soft_skills", 0),
        thinking_score=scores.get("thinking", 0),
        mindset_score=scores.get("mindset", 0),
        strengths=strengths,
        strengths_descriptions=strengths_descriptions,
        growth_areas=growth_areas,
        growth_areas_descriptions=growth_areas_descriptions,
        detected_patterns=detected_patterns,
        thinking_style=thinking_style,
        thinking_style_description=thinking_desc,
        communication_style=comm_style,
        communication_style_description=comm_desc,
        decision_style=decision_style,
        decision_style_description=decision_desc,
        motivation_driver=motivation,
        motivation_description=motivation_desc,
        level=level,
        level_match=level_match,
        level_match_description=level_match_desc,
        development_plan=development_plan,
        recommended_resources=recommended_resources,
    )


def format_profile_text(profile: CompetencyProfile) -> str:
    """
    Форматировать профиль для отправки в Telegram.
    
    Returns:
        Отформатированный HTML-текст
    """
    # Стили
    thinking_style_name = THINKING_STYLES.get(profile.thinking_style, {}).get("name", "Сбалансированный")
    comm_style_name = COMMUNICATION_STYLES.get(profile.communication_style, {}).get("name", "Адаптивный")
    motivation_name = MOTIVATION_DRIVERS.get(profile.motivation_driver, {}).get("name", "Рост")
    
    # Паттерны
    patterns_text = ""
    if profile.detected_patterns:
        pattern_names = [PATTERN_NAMES_RU.get(p, p) for p in profile.detected_patterns]
        patterns_text = f"\n<b>Выявленные паттерны:</b> {', '.join(pattern_names)}"
    
    # Ресурсы
    resources_text = ""
    if profile.recommended_resources:
        resources_lines = []
        for res in profile.recommended_resources[:3]:
            emoji = {"book": "📚", "course": "🎓", "practice": "🔧"}.get(res.get("type", ""), "📌")
            resources_lines.append(f"  {emoji} {res.get('title', '')} — <i>{res.get('reason', '')}</i>")
        resources_text = "\n".join(resources_lines)
    
    # Формируем match description без эмодзи (эмодзи уже есть в уровне)
    match_text = f"<i>{profile.level_match_description}</i>" if profile.level_match_description else ""
    
    return f"""🎯 <b>ПРОФИЛЬ КОМПЕТЕНЦИЙ</b>

{profile.get_level_emoji()} <b>Уровень:</b> {profile.level}
{match_text}

<b>Сильные стороны:</b>
{''.join(f"• {d}" + chr(10) for d in profile.strengths_descriptions)}
<b>Зоны развития:</b>
{''.join(f"• {d}" + chr(10) for d in profile.growth_areas_descriptions)}

<b>Психологический профиль:</b>
• Мышление: {thinking_style_name}
• Коммуникация: {comm_style_name}
• Мотиватор: {motivation_name}
{patterns_text}

<b>План развития:</b>
{''.join(f"• {item}" + chr(10) for item in profile.development_plan)}
<b>Ресурсы:</b>
{resources_text}"""


def format_profile_short(profile: CompetencyProfile) -> str:
    """Краткий формат профиля для PDF или summary."""
    thinking_style_name = THINKING_STYLES.get(profile.thinking_style, {}).get("name", "Сбалансированный")
    comm_style_name = COMMUNICATION_STYLES.get(profile.communication_style, {}).get("name", "Адаптивный")
    
    strengths_names = [METRIC_NAMES_RU.get(s, s) for s in profile.strengths]
    growth_names = [METRIC_NAMES_RU.get(g, g) for g in profile.growth_areas]
    
    return f"""Уровень: {profile.level} ({profile.total_score}/100)
Сильные стороны: {', '.join(strengths_names)}
Зоны развития: {', '.join(growth_names)}
Стиль мышления: {thinking_style_name}
Коммуникация: {comm_style_name}"""



