"""
PDP 2.0 — Генератор 30-дневного плана развития.

Создаёт детальный план с:
- Фокусом на 2-3 навыка
- Ежедневными микро-задачами (15-30 мин)
- Недельной структурой
- Конкретными ресурсами и действиями
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

from src.ai.answer_analyzer import METRIC_NAMES_RU
from src.analytics.pdp import RESOURCES_DB, ACTIONS_DB, Resource


# ==================== ТИПЫ ЗАДАЧ ====================

TASK_TYPES = {
    "read": "📖 Чтение",
    "watch": "🎬 Просмотр",
    "practice": "💪 Практика",
    "reflect": "🪞 Рефлексия",
    "discuss": "💬 Обсуждение",
    "write": "✍️ Написание",
}

DAY_NAMES = {
    1: "Пн",
    2: "Вт",
    3: "Ср",
    4: "Чт",
    5: "Пт",
    6: "Сб",
    7: "Вс",
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
    resource_type: Optional[str] = None
    resource_title: Optional[str] = None
    resource_url: Optional[str] = None


@dataclass
class WeeklyGoal:
    """Цель недели."""
    skill: str
    skill_name: str
    goal: str
    result: str  # Измеримый результат недели


@dataclass
class WeekPlan:
    """План на неделю."""
    week_number: int
    theme: str
    goal: WeeklyGoal
    days: dict[int, list[DailyTask]] = field(default_factory=dict)  # day -> tasks


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
    created_at: datetime = field(default_factory=datetime.utcnow)


# ==================== БАЗА МИКРО-ЗАДАЧ ====================

# Шаблоны задач по типам и навыкам
TASK_TEMPLATES = {
    "depth": {
        "read": [
            DailyTask(
                skill="depth",
                skill_name="Глубина анализа",
                title="Изучить технику '5 почему'",
                description="Прочитай статью о технике '5 почему' (Root Cause Analysis). Запиши 3 ключевых принципа.",
                duration_minutes=20,
                task_type="read",
                resource_type="article",
                resource_title="5 Whys: The Ultimate Root Cause Analysis Tool",
                resource_url="https://www.mindtools.com/a3mi00v/5-whys",
            ),
            DailyTask(
                skill="depth",
                skill_name="Глубина анализа",
                title="Глава из 'Thinking, Fast and Slow'",
                description="Прочитай введение и главу 1. Выпиши 2 примера когнитивных искажений.",
                duration_minutes=30,
                task_type="read",
                resource_type="book",
                resource_title="Thinking, Fast and Slow — Daniel Kahneman",
            ),
        ],
        "practice": [
            DailyTask(
                skill="depth",
                skill_name="Глубина анализа",
                title="Применить '5 почему' к рабочей проблеме",
                description="Выбери текущую рабочую проблему. Задай вопрос 'Почему?' минимум 5 раз. Запиши цепочку причин.",
                duration_minutes=15,
                task_type="practice",
            ),
            DailyTask(
                skill="depth",
                skill_name="Глубина анализа",
                title="Fishbone-диаграмма",
                description="Нарисуй диаграмму Исикавы для проблемы из проекта. Выдели минимум 4 категории причин.",
                duration_minutes=25,
                task_type="practice",
            ),
        ],
        "reflect": [
            DailyTask(
                skill="depth",
                skill_name="Глубина анализа",
                title="Рефлексия: мои паттерны анализа",
                description="Ответь письменно: Какие проблемы я обычно анализирую поверхностно? Почему? Что мешает копать глубже?",
                duration_minutes=15,
                task_type="reflect",
            ),
        ],
    },
    
    "systems_thinking": {
        "read": [
            DailyTask(
                skill="systems_thinking",
                skill_name="Системное мышление",
                title="Введение в системное мышление",
                description="Прочитай главу 1 'Thinking in Systems'. Выпиши определения: система, stock, flow, feedback loop.",
                duration_minutes=30,
                task_type="read",
                resource_type="book",
                resource_title="Thinking in Systems — Donella Meadows",
            ),
            DailyTask(
                skill="systems_thinking",
                skill_name="Системное мышление",
                title="Feedback loops",
                description="Изучи концепции reinforcing и balancing loops. Найди по 2 примера каждого в своей работе.",
                duration_minutes=25,
                task_type="read",
            ),
        ],
        "practice": [
            DailyTask(
                skill="systems_thinking",
                skill_name="Системное мышление",
                title="Системная карта проекта",
                description="Нарисуй системную карту своего текущего проекта. Покажи основные элементы и связи между ними.",
                duration_minutes=30,
                task_type="practice",
            ),
            DailyTask(
                skill="systems_thinking",
                skill_name="Системное мышление",
                title="Second-Order Thinking",
                description="Выбери решение, которое планируешь принять. Ответь: 'А что будет потом?' для каждого последствия — минимум 3 уровня.",
                duration_minutes=20,
                task_type="practice",
            ),
        ],
        "reflect": [
            DailyTask(
                skill="systems_thinking",
                skill_name="Системное мышление",
                title="Где я не вижу систему?",
                description="Подумай о последнем неожиданном результате в работе. Какие системные факторы ты упустил?",
                duration_minutes=15,
                task_type="reflect",
            ),
        ],
    },
    
    "creativity": {
        "practice": [
            DailyTask(
                skill="creativity",
                skill_name="Креативность",
                title="10 идей на случайную тему",
                description="Открой генератор случайных слов. За 10 минут сгенерируй 10 идей, связывающих это слово с твоей работой.",
                duration_minutes=15,
                task_type="practice",
            ),
            DailyTask(
                skill="creativity",
                skill_name="Креативность",
                title="Crazy 8s",
                description="Выбери текущую задачу. За 8 минут набросай 8 разных решений (по 1 минуте на каждое).",
                duration_minutes=15,
                task_type="practice",
            ),
            DailyTask(
                skill="creativity",
                skill_name="Креативность",
                title="Constraint-based design",
                description="Реши задачу с ограничениями: 'без бюджета', 'за 1 день', 'без кода'. Как это меняет решение?",
                duration_minutes=20,
                task_type="practice",
            ),
        ],
        "read": [
            DailyTask(
                skill="creativity",
                skill_name="Креативность",
                title="Техники латерального мышления",
                description="Изучи 3 техники из книги 'Lateral Thinking'. Выбери одну для применения завтра.",
                duration_minutes=25,
                task_type="read",
                resource_type="book",
                resource_title="Lateral Thinking — Edward de Bono",
            ),
        ],
    },
    
    "articulation": {
        "practice": [
            DailyTask(
                skill="articulation",
                skill_name="Чёткость мышления",
                title="Elevator Pitch",
                description="Подготовь 30-секундную версию своего текущего проекта. Запиши на диктофон и переслушай.",
                duration_minutes=15,
                task_type="practice",
            ),
            DailyTask(
                skill="articulation",
                skill_name="Чёткость мышления",
                title="Объясни сложное просто",
                description="Выбери сложную концепцию из работы. Объясни её так, чтобы понял школьник. Запиши.",
                duration_minutes=20,
                task_type="practice",
            ),
        ],
        "read": [
            DailyTask(
                skill="articulation",
                skill_name="Чёткость мышления",
                title="Пирамида Минто",
                description="Изучи принцип пирамиды: сначала вывод, потом аргументы. Примени к следующему письму/сообщению.",
                duration_minutes=25,
                task_type="read",
                resource_type="book",
                resource_title="Пирамида Минто — Барбара Минто",
            ),
        ],
        "reflect": [
            DailyTask(
                skill="articulation",
                skill_name="Чёткость мышления",
                title="Анализ своих объяснений",
                description="Вспомни последний раз, когда тебя не поняли. Что пошло не так? Как бы ты объяснил сейчас?",
                duration_minutes=15,
                task_type="reflect",
            ),
        ],
    },
    
    "self_awareness": {
        "practice": [
            DailyTask(
                skill="self_awareness",
                skill_name="Самоосознание",
                title="360° feedback — подготовка",
                description="Составь список из 5 коллег для обратной связи. Подготовь 3 вопроса: что хорошо, что улучшить, что удивляет.",
                duration_minutes=20,
                task_type="practice",
            ),
            DailyTask(
                skill="self_awareness",
                skill_name="Самоосознание",
                title="Дневник рефлексии",
                description="Запиши ответы: Что сегодня получилось? Что не получилось? Что узнал о себе?",
                duration_minutes=10,
                task_type="practice",
            ),
        ],
        "reflect": [
            DailyTask(
                skill="self_awareness",
                skill_name="Самоосознание",
                title="Мои триггеры",
                description="Когда я раздражаюсь на работе? Что стоит за этим? Какая потребность не удовлетворена?",
                duration_minutes=15,
                task_type="reflect",
            ),
            DailyTask(
                skill="self_awareness",
                skill_name="Самоосознание",
                title="Мои сильные стороны",
                description="Напиши 5 своих сильных сторон. Для каждой — конкретный пример проявления.",
                duration_minutes=15,
                task_type="reflect",
            ),
        ],
    },
    
    "structure": {
        "practice": [
            DailyTask(
                skill="structure",
                skill_name="Структурность",
                title="MECE-декомпозиция",
                description="Возьми текущую задачу. Разбей на части по MECE: взаимоисключающие и исчерпывающие.",
                duration_minutes=20,
                task_type="practice",
            ),
            DailyTask(
                skill="structure",
                skill_name="Структурность",
                title="Issue Tree",
                description="Построй дерево проблем для сложного вопроса. Минимум 3 уровня вглубь.",
                duration_minutes=25,
                task_type="practice",
            ),
        ],
        "read": [
            DailyTask(
                skill="structure",
                skill_name="Структурность",
                title="Frameworks от McKinsey",
                description="Изучи 3 классических фреймворка: MECE, Issue Trees, Hypothesis-Driven. Выбери один для практики.",
                duration_minutes=30,
                task_type="read",
            ),
        ],
    },
    
    "expertise": {
        "practice": [
            DailyTask(
                skill="expertise",
                skill_name="Экспертиза",
                title="Разбор кейса лидера индустрии",
                description="Выбери продукт/проект лидера в твоей области. Разбери: что, почему, как. Запиши 3 инсайта.",
                duration_minutes=30,
                task_type="practice",
            ),
            DailyTask(
                skill="expertise",
                skill_name="Экспертиза",
                title="Teach-back",
                description="Объясни коллеге концепцию, которую недавно изучил. Обучая — учишься глубже.",
                duration_minutes=20,
                task_type="practice",
            ),
        ],
        "read": [
            DailyTask(
                skill="expertise",
                skill_name="Экспертиза",
                title="Статья от эксперта",
                description="Прочитай статью лидера мнений в твоей области. Выпиши 3 применимых идеи.",
                duration_minutes=25,
                task_type="read",
            ),
        ],
    },
    
    "growth_orientation": {
        "practice": [
            DailyTask(
                skill="growth_orientation",
                skill_name="Ориентация на рост",
                title="Stretch-задача",
                description="Выбери задачу на 20% сложнее твоего текущего уровня. Запиши план, как её решить.",
                duration_minutes=20,
                task_type="practice",
            ),
            DailyTask(
                skill="growth_orientation",
                skill_name="Ориентация на рост",
                title="Learning journal",
                description="Запиши 3 новые вещи, которые узнал сегодня. Что удивило? Что хочешь изучить глубже?",
                duration_minutes=10,
                task_type="practice",
            ),
        ],
        "reflect": [
            DailyTask(
                skill="growth_orientation",
                skill_name="Ориентация на рост",
                title="Fixed vs Growth mindset",
                description="Вспомни ситуацию, когда сдался. Как бы ты отреагировал с growth mindset? Перепиши сценарий.",
                duration_minutes=15,
                task_type="reflect",
            ),
        ],
    },
    
    "honesty": {
        "practice": [
            DailyTask(
                skill="honesty",
                skill_name="Интеллектуальная честность",
                title="Pre-mortem",
                description="Для текущего проекта представь, что он провалился. Что пошло не так? Запиши 5 причин.",
                duration_minutes=20,
                task_type="practice",
            ),
            DailyTask(
                skill="honesty",
                skill_name="Интеллектуальная честность",
                title="Fail Friday (личная версия)",
                description="Запиши одну свою ошибку на этой неделе. Что узнал? Что сделаешь по-другому?",
                duration_minutes=15,
                task_type="practice",
            ),
        ],
        "read": [
            DailyTask(
                skill="honesty",
                skill_name="Интеллектуальная честность",
                title="Radical Candor — введение",
                description="Прочитай введение. Выпиши разницу между честностью и токсичностью.",
                duration_minutes=25,
                task_type="read",
                resource_type="book",
                resource_title="Radical Candor — Kim Scott",
            ),
        ],
    },
    
    "conflict_handling": {
        "read": [
            DailyTask(
                skill="conflict_handling",
                skill_name="Работа с конфликтами",
                title="Техники сложных разговоров",
                description="Изучи технику 'STATE' из Crucial Conversations. Запиши пример применения.",
                duration_minutes=25,
                task_type="read",
                resource_type="book",
                resource_title="Crucial Conversations",
            ),
        ],
        "practice": [
            DailyTask(
                skill="conflict_handling",
                skill_name="Работа с конфликтами",
                title="Ролевая игра",
                description="С коллегой/другом отрепетируй сложный разговор, который откладываешь. Получи feedback.",
                duration_minutes=30,
                task_type="practice",
            ),
        ],
        "reflect": [
            DailyTask(
                skill="conflict_handling",
                skill_name="Работа с конфликтами",
                title="Анализ прошлого конфликта",
                description="Вспомни недавний конфликт. Что сработало? Что нет? Как бы ты поступил сейчас?",
                duration_minutes=15,
                task_type="reflect",
            ),
        ],
    },
    
    "methodology": {
        "read": [
            DailyTask(
                skill="methodology",
                skill_name="Методология",
                title="Введение в Design Thinking",
                description="Изучи 5 этапов Design Thinking: Empathize, Define, Ideate, Prototype, Test.",
                duration_minutes=25,
                task_type="read",
            ),
        ],
        "practice": [
            DailyTask(
                skill="methodology",
                skill_name="Методология",
                title="Мини-спринт",
                description="Примени упрощённую версию Design Sprint к маленькой задаче: 1 час вместо 5 дней.",
                duration_minutes=30,
                task_type="practice",
            ),
        ],
    },
    
    "tools_proficiency": {
        "practice": [
            DailyTask(
                skill="tools_proficiency",
                skill_name="Владение инструментами",
                title="Новая фича в основном инструменте",
                description="Изучи одну продвинутую функцию твоего главного инструмента (Figma/Amplitude/etc). Примени.",
                duration_minutes=25,
                task_type="practice",
            ),
            DailyTask(
                skill="tools_proficiency",
                skill_name="Владение инструментами",
                title="Автоматизация рутины",
                description="Найди повторяющееся действие в работе. Изучи, как его автоматизировать.",
                duration_minutes=30,
                task_type="practice",
            ),
        ],
    },
}


# ==================== ГЕНЕРАТОР ====================

def _get_tasks_for_skill(
    skill: str,
    task_types: list[str],
    count: int = 3,
) -> list[DailyTask]:
    """Получить задачи для навыка определённых типов."""
    skill_tasks = TASK_TEMPLATES.get(skill, {})
    result = []
    
    for task_type in task_types:
        type_tasks = skill_tasks.get(task_type, [])
        result.extend(type_tasks)
    
    return result[:count]


def _build_week_plan(
    week_num: int,
    focus_skills: list[str],
    daily_time: int,
    learning_style: str,
) -> WeekPlan:
    """
    Построить план на одну неделю.
    
    Логика:
    - Неделя 1: Основы, знакомство с концепциями (больше read)
    - Неделя 2: Первые практики (read + practice)
    - Неделя 3: Углубление (practice + reflect)
    - Неделя 4: Закрепление и рефлексия (practice + reflect + discuss)
    """
    # Определяем баланс типов задач по неделям
    week_focus = {
        1: ["read", "read", "practice", "read", "reflect"],  # Основы
        2: ["read", "practice", "practice", "read", "reflect"],  # Практика
        3: ["practice", "practice", "reflect", "practice", "read"],  # Углубление
        4: ["practice", "reflect", "practice", "reflect", "practice"],  # Закрепление
    }
    
    # Учитываем стиль обучения
    style_adjustments = {
        "read": ["read", "read", "read", "reflect", "practice"],
        "watch": ["watch", "read", "practice", "reflect", "practice"],
        "do": ["practice", "practice", "practice", "reflect", "read"],
        "mixed": None,  # Без изменений
    }
    
    types_per_day = style_adjustments.get(learning_style) or week_focus.get(week_num, week_focus[1])
    
    # Темы недель
    week_themes = {
        1: "Знакомство с концепциями",
        2: "Первые шаги на практике",
        3: "Углубление и эксперименты",
        4: "Закрепление и рефлексия",
    }
    
    # Создаём план
    main_skill = focus_skills[0] if focus_skills else "depth"
    main_skill_name = METRIC_NAMES_RU.get(main_skill, main_skill)
    
    plan = WeekPlan(
        week_number=week_num,
        theme=week_themes.get(week_num, f"Неделя {week_num}"),
        goal=WeeklyGoal(
            skill=main_skill,
            skill_name=main_skill_name,
            goal=f"Освоить базовые практики {main_skill_name.lower()}",
            result=f"Применить 3 техники {main_skill_name.lower()} в работе",
        ),
        days={},
    )
    
    # Распределяем навыки по дням (чередуем)
    for day in range(1, 6):  # Пн-Пт (рабочие дни)
        skill_idx = (day - 1) % len(focus_skills)
        skill = focus_skills[skill_idx]
        
        task_type = types_per_day[(day - 1) % len(types_per_day)]
        
        # Получаем задачу
        tasks = _get_tasks_for_skill(skill, [task_type, "practice"], count=1)
        
        if tasks:
            # Адаптируем время
            task = tasks[0]
            # Создаём копию с адаптированным временем
            adapted_task = DailyTask(
                skill=task.skill,
                skill_name=task.skill_name,
                title=task.title,
                description=task.description,
                duration_minutes=min(task.duration_minutes, daily_time),
                task_type=task.task_type,
                resource_type=task.resource_type,
                resource_title=task.resource_title,
                resource_url=task.resource_url,
            )
            plan.days[day] = [adapted_task]
        else:
            # Fallback — генерируем базовую задачу
            skill_name = METRIC_NAMES_RU.get(skill, skill)
            plan.days[day] = [DailyTask(
                skill=skill,
                skill_name=skill_name,
                title=f"Практика {skill_name}",
                description=f"Уделите {daily_time} минут развитию навыка {skill_name}.",
                duration_minutes=daily_time,
                task_type="practice",
            )]
    
    # Выходные — легче
    for day in [6, 7]:  # Сб-Вс
        skill = focus_skills[0]
        skill_name = METRIC_NAMES_RU.get(skill, skill)
        plan.days[day] = [DailyTask(
            skill=skill,
            skill_name=skill_name,
            title="Рефлексия недели" if day == 7 else "Свободная практика",
            description="Что получилось на этой неделе? Что было сложно? Что хочешь изменить?" if day == 7 
                       else f"Выбери любую практику по {skill_name} из этой недели и повтори.",
            duration_minutes=15,
            task_type="reflect" if day == 7 else "practice",
        )]
    
    return plan


def generate_pdp_plan(
    focus_skills: list[str],
    daily_time: int = 30,
    learning_style: str = "mixed",
) -> PdpPlan30:
    """
    Сгенерировать 30-дневный план развития.
    
    Args:
        focus_skills: Топ-3 навыка для развития
        daily_time: Минут в день (15/30/60)
        learning_style: read/watch/do/mixed
    
    Returns:
        PdpPlan30 с 4 неделями плана
    """
    # Ограничиваем до 3 навыков
    focus_skills = focus_skills[:3]
    if not focus_skills:
        focus_skills = ["depth"]  # Fallback
    
    # Названия навыков
    focus_skill_names = [METRIC_NAMES_RU.get(s, s) for s in focus_skills]
    
    # Генерируем 4 недели
    weeks = []
    for week_num in range(1, 5):
        week = _build_week_plan(week_num, focus_skills, daily_time, learning_style)
        weeks.append(week)
    
    # Считаем общее количество задач
    total_tasks = sum(
        len(tasks) 
        for week in weeks 
        for tasks in week.days.values()
    )
    
    return PdpPlan30(
        focus_skills=focus_skills,
        focus_skill_names=focus_skill_names,
        daily_time=daily_time,
        learning_style=learning_style,
        weeks=weeks,
        total_tasks=total_tasks,
    )


def format_pdp_plan_text(plan: PdpPlan30, week_num: int = 1) -> str:
    """
    Форматировать план для Telegram (одна неделя).
    """
    if week_num < 1 or week_num > len(plan.weeks):
        return "❌ Неделя не найдена"
    
    week = plan.weeks[week_num - 1]
    
    # Заголовок
    text = f"""🎯 <b>ПЛАН РАЗВИТИЯ — НЕДЕЛЯ {week_num}/4</b>

<b>Тема:</b> {week.theme}
<b>Фокус:</b> {', '.join(plan.focus_skill_names)}
<b>Время в день:</b> {plan.daily_time} мин

"""
    
    # Цель недели
    text += f"""<b>🏆 Цель недели:</b>
{week.goal.goal}
<b>Результат:</b> {week.goal.result}

"""
    
    # Задачи по дням
    text += "<b>📅 ЗАДАЧИ:</b>\n\n"
    
    for day in range(1, 8):
        day_name = DAY_NAMES.get(day, str(day))
        tasks = week.days.get(day, [])
        
        if tasks:
            task = tasks[0]
            type_emoji = TASK_TYPES.get(task.task_type, "📌").split()[0]
            text += f"<b>{day_name}:</b> {type_emoji} {task.title} ({task.duration_minutes} мин)\n"
        else:
            text += f"<b>{day_name}:</b> 🔲 —\n"
    
    return text


def format_today_task(plan: PdpPlan30, week: int, day: int) -> str:
    """Форматировать задачу на сегодня."""
    if week < 1 or week > len(plan.weeks):
        return "❌ План не найден"
    
    week_plan = plan.weeks[week - 1]
    tasks = week_plan.days.get(day, [])
    
    if not tasks:
        return "🎉 На сегодня задач нет! Отдыхай или практикуй по желанию."
    
    task = tasks[0]
    day_name = DAY_NAMES.get(day, str(day))
    type_name = TASK_TYPES.get(task.task_type, "📌 Задача")
    
    text = f"""📅 <b>ЗАДАЧА НА СЕГОДНЯ</b>
<i>Неделя {week}/4, {day_name}</i>

<b>{type_name}</b>
<b>{task.title}</b>

{task.description}

⏱ <b>Время:</b> {task.duration_minutes} мин
🎯 <b>Навык:</b> {task.skill_name}
"""
    
    if task.resource_title:
        text += f"\n📚 <b>Ресурс:</b> {task.resource_title}"
        if task.resource_url:
            text += f"\n🔗 {task.resource_url}"
    
    return text

