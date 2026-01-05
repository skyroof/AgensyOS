"""
PDP 3.0 — Интерактивный AI-коуч.

Генерирует 4-недельный план развития по модели 70/20/10.
- Неделя 1-3: Глубокое погружение в топ-3 навыка (по одному на неделю).
- Неделя 4: Интеграция и мастерство (микс всех навыков).

Структура дня:
- 15-30 минут
- Чёткий фокус (теория -> практика -> рефлексия)
- Геймификация (XP за выполнение)
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
import random

from src.ai.answer_analyzer import METRIC_NAMES_RU

# ==================== КОНСТАНТЫ ====================

TASK_TYPES = {
    "read": "📖 Чтение (10%)",
    "watch": "🎬 Просмотр (10%)",
    "practice": "💪 Практика (70%)",
    "reflect": "🪞 Рефлексия (70%)",
    "discuss": "💬 Обсуждение (20%)",
    "write": "✍️ Написание (70%)",
}

DAY_NAMES = {
    1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 7: "Вс",
}

# XP за типы задач
XP_REWARDS = {
    "read": 10,
    "watch": 10,
    "discuss": 20,
    "reflect": 15,
    "practice": 30,
    "write": 25,
}

# ==================== DATACLASSES ====================

@dataclass
class DailyTask:
    """Задача на день."""
    skill: str
    skill_name: str
    title: str
    description: str
    duration_minutes: int
    task_type: str  # read/watch/practice/reflect/discuss
    xp: int = 10
    resource_type: Optional[str] = None
    resource_title: Optional[str] = None
    resource_url: Optional[str] = None


@dataclass
class WeekPlan:
    """План на неделю."""
    week_number: int
    theme: str
    focus_skill: str
    goal: str
    days: dict[int, list[DailyTask]] = field(default_factory=dict)


@dataclass
class PdpPlan30:
    """Полный 30-дневный план."""
    focus_skills: list[str]  # Топ-3 навыка
    focus_skill_names: list[str]
    daily_time: int  # минут в день
    learning_style: str  # read/watch/do/mixed
    
    weeks: list[WeekPlan] = field(default_factory=list)
    
    # Метаданные
    total_tasks: int = 0
    total_xp: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


# ==================== БАЗА ШАБЛОНОВ ЗАДАЧ (GENERIC) ====================

# Шаблоны, которые адаптируются под любой навык
GENERIC_TASKS = {
    "read": [
        {
            "title": "Фундамент: {skill_name}",
            "desc": "Найди и прочитай топ-3 статьи по теме '{skill_name}' на Medium или VC.ru. Выпиши 3 ключевых инсайта.",
            "time": 20
        },
        {
            "title": "Методология экспертов",
            "desc": "Изучи, как '{skill_name}' применяют в топовых компаниях (Google, Amazon, Yandex). Найди один кейс.",
            "time": 25
        }
    ],
    "watch": [
        {
            "title": "Видео-разбор",
            "desc": "Посмотри TED Talks или доклад с конференции по теме '{skill_name}'. Запиши, что можно внедрить уже завтра.",
            "time": 20
        }
    ],
    "practice": [
        {
            "title": "Аудит текущей ситуации",
            "desc": "Проанализируй свою работу за последнюю неделю через призму '{skill_name}'. Где ты был хорош, а где просел?",
            "time": 15
        },
        {
            "title": "Микро-эксперимент",
            "desc": "Попробуй применить '{skill_name}' сегодня на одной встрече или задаче. Запиши результат.",
            "time": 30
        },
        {
            "title": "Разбор чужого кейса",
            "desc": "Возьми проект коллеги. Как бы ты улучшил его, используя '{skill_name}'?",
            "time": 25
        }
    ],
    "reflect": [
        {
            "title": "Дневник развития",
            "desc": "Ответь на вопрос: 'Что мешает мне проявлять {skill_name} на 10/10?'. Будь честен.",
            "time": 15
        },
        {
            "title": "Анализ барьеров",
            "desc": "Вспомни ситуацию, где тебе не хватило навыка '{skill_name}'. Как бы ты поступил сейчас?",
            "time": 20
        }
    ],
    "discuss": [
        {
            "title": "Обратная связь",
            "desc": "Спроси коллегу или руководителя: 'Как ты оцениваешь мой навык {skill_name}?'. Запиши фидбек.",
            "time": 15
        },
        {
            "title": "Teaching others",
            "desc": "Объясни суть навыка '{skill_name}' кому-то из команды или другу. Если понял он — понял и ты.",
            "time": 20
        }
    ]
}

# Специфичные задачи для конкретных метрик (Hardcoded Best Practices)
SPECIFIC_TASKS = {
    # === THINKING ===
    "depth": {
        "practice": [
            {"title": "Техника '5 почему'", "desc": "Возьми сложную проблему. Задай 'Почему?' 5 раз, чтобы найти корневую причину.", "time": 20},
            {"title": "Диаграмма Исикавы", "desc": "Построй Fishbone-диаграмму для текущего блокера в проекте.", "time": 25},
            {"title": "Second-Order Thinking", "desc": "Пропиши последствия своего решения: 1-й уровень (сразу), 2-й уровень (через месяц), 3-й уровень (через год).", "time": 20}
        ],
        "read": [
            {"title": "Mental Models: First Principles", "desc": "Прочитай про мышление от первых принципов (First Principles). Разложи проблему на атомы.", "time": 25}
        ]
    },
    "systems_thinking": {
        "read": [{"title": "Thinking in Systems", "desc": "Прочитай главу из Донеллы Медоуз про Feedback Loops.", "time": 30}],
        "practice": [
            {"title": "Карта связей", "desc": "Нарисуй системную карту своего продукта: элементы, связи, циклы.", "time": 30},
            {"title": "Поиск рычага", "desc": "Найди одну точку в системе, изменение которой даст максимальный эффект. Обоснуй.", "time": 25}
        ]
    },
    "structure": {
        "practice": [
            {"title": "MECE принцип", "desc": "Структурируй текущую задачу по принципу MECE (Mutually Exclusive, Collectively Exhaustive).", "time": 20},
            {"title": "Issue Tree", "desc": "Построй дерево проблем для текущего челленджа. Разбей большую задачу на подзадачи.", "time": 25}
        ],
        "write": [
            {"title": "One-Pager", "desc": "Опиши свою идею на одном листе А4: Проблема, Решение, Почему сейчас, Риски.", "time": 30}
        ]
    },
    "creativity": {
        "practice": [
            {"title": "Метод SCAMPER", "desc": "Возьми привычный процесс и прогони через SCAMPER (Substitute, Combine, Adapt, etc.).", "time": 25},
            {"title": "Crazy 8s", "desc": "Сложи лист А4 в 8 частей. За 8 минут нарисуй 8 вариантов решения одной задачи.", "time": 10},
            {"title": "Ролевая игра", "desc": "Как бы эту задачу решил Илон Маск? А как — твоя бабушка?", "time": 15}
        ]
    },

    # === SOFT SKILLS ===
    "articulation": {
        "practice": [
            {"title": "Метод 'Пирамида Минто'", "desc": "Перепиши последнее важное письмо, используя принцип пирамиды: главное — в начале.", "time": 20},
            {"title": "Elevator Pitch", "desc": "Запиши на диктофон 30-секундный рассказ о своем текущем проекте. Переслушай и улучши.", "time": 15},
            {"title": "ELI5 (Explain Like I'm 5)", "desc": "Попробуй объяснить сложный технический концепт простыми словами (без жаргона).", "time": 15}
        ]
    },
    "self_awareness": {
        "reflect": [
            {"title": "Окно Джохари", "desc": "Запиши 3 своих качества. Спроси коллегу, какие 3 качества он видит в тебе. Сравни.", "time": 20},
            {"title": "Анализ триггеров", "desc": "Вспомни момент, когда ты испытал сильную эмоцию на работе. Что именно её вызвало?", "time": 15}
        ],
        "discuss": [
            {"title": "Честный фидбек", "desc": "Попроси коллегу назвать одну твою зону роста. Просто выслушай, не защищаясь.", "time": 15}
        ]
    },
    "conflict_handling": {
        "practice": [
            {"title": "Я-сообщения", "desc": "Переформулируй претензию в формат 'Я чувствую..., когда..., потому что...'.", "time": 15},
            {"title": "Позиция vs Интерес", "desc": "В споре попробуй понять не 'что' человек требует, а 'почему' (его истинный интерес).", "time": 20}
        ]
    },

    # === HARD SKILLS ===
    "expertise": {
        "read": [
            {"title": "Industry Trends", "desc": "Прочитай отчет Gartner/McKinsey по твоему домену за этот год. Выдели 3 тренда.", "time": 30}
        ],
        "practice": [
            {"title": "Deep Dive", "desc": "Выбери одну узкую тему в своей области, где ты плаваешь. Изучи её за 30 минут.", "time": 30}
        ]
    },
    "methodology": {
        "practice": [
            {"title": "Review Process", "desc": "Проверь, соответствует ли твой текущий процесс стандартам (Agile, Design Thinking, etc.).", "time": 20}
        ]
    },
    "tools_proficiency": {
        "practice": [
            {"title": "Hotkeys Master", "desc": "Выучи 3 новых хоткея в твоем основном инструменте (Figma, Jira, IDE). Используй их весь день.", "time": 15},
            {"title": "New Feature", "desc": "Изучи одну функцию инструмента, которой ты никогда не пользовался.", "time": 20}
        ]
    },

    # === MINDSET ===
    "growth_orientation": {
        "reflect": [
            {"title": "Failures as Fuel", "desc": "Вспомни свою последнюю ошибку. Чему именно она тебя научила? Запиши 3 урока.", "time": 15}
        ]
    }
}


# ==================== ГЕНЕРАТОР ====================

def generate_pdp_plan(
    focus_skills: list[str],
    daily_time: int = 30,
    learning_style: str = "mixed"
) -> PdpPlan30:
    """
    Генерирует план на 30 дней.
    
    Стратегия:
    - Неделя 1: Навык 1 (Приоритет №1)
    - Неделя 2: Навык 2
    - Неделя 3: Навык 3
    - Неделя 4: Интеграция (Микс)
    """
    
    # Ensure we have at least 3 skills
    if not focus_skills:
        focus_skills = ["depth", "systems_thinking", "creativity"]
    
    # Pad with cycling if less than 3
    while len(focus_skills) < 3:
        focus_skills.extend(focus_skills)
    
    focus_skills = focus_skills[:3]
    
    skill_names = [METRIC_NAMES_RU.get(s, s) for s in focus_skills]
    
    plan = PdpPlan30(
        focus_skills=focus_skills,
        focus_skill_names=skill_names,
        daily_time=daily_time,
        learning_style=learning_style
    )
    
    # Генерация недель
    for week_num in range(1, 5):
        if week_num <= 3:
            # Тематическая неделя
            skill = focus_skills[week_num - 1]
            skill_name = METRIC_NAMES_RU.get(skill, skill)
            theme = f"Погружение в {skill_name}"
            goal = f"Освоить базовые принципы и внедрить в работу"
            
            week_plan = _generate_week_content(week_num, skill, skill_name, theme, goal)
        else:
            # Интеграционная неделя
            theme = "Мастерство и Интеграция"
            goal = "Объединить все навыки в единую систему"
            week_plan = _generate_integration_week(week_num, focus_skills)
            
        plan.weeks.append(week_plan)
        
        # Подсчет статистики
        for day_tasks in week_plan.days.values():
            plan.total_tasks += len(day_tasks)
            plan.total_xp += sum(t.xp for t in day_tasks)
            
    return plan


def _generate_week_content(week_num: int, skill: str, skill_name: str, theme: str, goal: str) -> WeekPlan:
    """Создает контент для одной недели фокуса на навыке."""
    week = WeekPlan(
        week_number=week_num,
        theme=theme,
        focus_skill=skill,
        goal=goal
    )
    
    # Структура недели по модели 70/20/10
    # Пн: Теория (10%) - Read/Watch
    # Вт: Теория + Практика - Watch/Practice
    # Ср: Практика (70%) - Practice
    # Чт: Практика (70%) - Practice/Write
    # Пт: Социальное (20%) - Discuss/Feedback
    # Сб: Рефлексия - Reflect
    # Вс: Отдых (или бонус)
    
    # Пн
    week.days[1] = [_create_task(skill, skill_name, "read")]
    
    # Вт
    week.days[2] = [_create_task(skill, skill_name, "watch")]
    
    # Ср
    week.days[3] = [_create_task(skill, skill_name, "practice")]
    
    # Чт
    week.days[4] = [_create_task(skill, skill_name, "practice", force_variant=1)]
    
    # Пт
    week.days[5] = [_create_task(skill, skill_name, "discuss")]
    
    # Сб
    week.days[6] = [_create_task(skill, skill_name, "reflect")]
    
    # Вс (Выходной, но можно добавить легкое чтение)
    # week.days[7] = [] 
    
    return week


def _generate_integration_week(week_num: int, skills: list[str]) -> WeekPlan:
    """Создает контент для 4-й недели (микс)."""
    week = WeekPlan(
        week_number=week_num,
        theme="Интеграция навыков",
        focus_skill="mixed",
        goal="Применить все изученное в комплексе"
    )
    
    # Ensure we have at least 3 skills, filling with duplicates if needed
    if not skills:
        skills = ["depth", "systems_thinking", "creativity"]
    
    # Handle cases with fewer than 3 skills by cycling
    extended_skills = skills * 3  # Ensure we have enough items
    s1, s2, s3 = extended_skills[0], extended_skills[1], extended_skills[2]
    
    n1 = METRIC_NAMES_RU.get(s1, s1)
    n2 = METRIC_NAMES_RU.get(s2, s2)
    n3 = METRIC_NAMES_RU.get(s3, s3)
    
    week.days[1] = [_create_task(s1, n1, "practice")]
    week.days[2] = [_create_task(s2, n2, "practice")]
    week.days[3] = [_create_task(s3, n3, "practice")]
    week.days[4] = [_create_task(s1, n1, "reflect")] # Рефлексия по первому
    week.days[5] = [_create_task(s2, n2, "discuss")] # Обсуждение второго
    week.days[6] = [_create_task(s3, n3, "write", variant_override="Напиши эссе/пост")]
    
    return week


def _create_task(
    skill: str, 
    skill_name: str, 
    task_type: str, 
    force_variant: int = 0,
    variant_override: str = None
) -> DailyTask:
    """Создает задачу, выбирая из специфичных или общих шаблонов."""
    
    template = None
    
    # 1. Пробуем найти специфичный шаблон
    if skill in SPECIFIC_TASKS and task_type in SPECIFIC_TASKS[skill]:
        candidates = SPECIFIC_TASKS[skill][task_type]
        if candidates:
            idx = force_variant % len(candidates)
            template = candidates[idx]
            
    # 2. Если нет, берем общий
    if not template and task_type in GENERIC_TASKS:
        candidates = GENERIC_TASKS[task_type]
        idx = force_variant % len(candidates)
        template = candidates[idx]
        
    # 3. Фолбек (совсем на всякий случай)
    if not template:
        template = {
            "title": f"Поработать над {skill_name}",
            "desc": f"Удели время развитию навыка {skill_name}. Запиши мысли.",
            "time": 20
        }
    
    # Форматируем строки
    title = template["title"].format(skill_name=skill_name)
    desc = template["desc"].format(skill_name=skill_name)
    
    if variant_override:
        title = variant_override
        
    return DailyTask(
        skill=skill,
        skill_name=skill_name,
        title=title,
        description=desc,
        duration_minutes=template.get("time", 20),
        task_type=task_type,
        xp=XP_REWARDS.get(task_type, 10)
    )


def format_pdp_plan_text(plan: PdpPlan30) -> str:
    """Форматирует текст описания плана."""
    skills_text = ", ".join(plan.focus_skill_names)
    
    return f"""📋 <b>Твой Персональный План Развития</b>

🎯 <b>Фокус на навыках:</b>
{skills_text}

⏱ <b>Время в день:</b> {plan.daily_time} минут
🏆 <b>Общий опыт (XP):</b> {plan.total_xp}
📅 <b>Длительность:</b> 4 недели

<b>Структура плана:</b>
• Неделя 1: Погружение в {plan.focus_skill_names[0]}
• Неделя 2: Погружение в {plan.focus_skill_names[1]}
• Неделя 3: Погружение в {plan.focus_skill_names[2]}
• Неделя 4: Интеграция и мастерство

<i>Каждый день — новая микро-задача для развития компетенций.</i>"""


def format_today_task(task: DailyTask, day_number: int, week_number: int) -> str:
    """Форматирует текст задачи на день."""
    type_emoji = TASK_TYPES.get(task.task_type, "📝").split()[0]
    
    return f"""📅 <b>Задача на сегодня (Неделя {week_number}, День {day_number})</b>

{type_emoji} <b>{task.title}</b>
<i>Навык: {task.skill_name}</i>

📝 <b>Что сделать:</b>
{task.description}

⏱ <b>Время:</b> {task.duration_minutes} мин
⭐ <b>Награда:</b> +{task.xp} XP

<i>Нажми "✅ Сделано", когда закончишь!</i>"""
