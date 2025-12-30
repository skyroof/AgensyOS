"""
Расчёт динамики развития между диагностиками.

Анализирует:
- Изменение баллов между сессиями
- Рост/падение по категориям
- Streak (серия улучшений)
- Рекорды пользователя
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SessionSummary:
    """Краткая информация о сессии для сравнения."""
    id: int
    completed_at: datetime
    role: str
    role_name: str
    experience_name: str
    total_score: int
    hard_skills: int
    soft_skills: int
    thinking: int
    mindset: int


@dataclass
class DynamicsResult:
    """Результат расчёта динамики между двумя сессиями."""
    
    # Основные изменения
    total_delta: int  # +7 / -3
    hard_skills_delta: int
    soft_skills_delta: int
    thinking_delta: int
    mindset_delta: int
    
    # Дни между сессиями
    days_between: int
    
    # Что улучшилось / ухудшилось
    improved_categories: list[str] = field(default_factory=list)  # ["Hard Skills +5", "Thinking +3"]
    declined_categories: list[str] = field(default_factory=list)  # ["Mindset -2"]
    
    # Общая оценка
    trend: str = "stable"  # "up" / "down" / "stable"
    trend_emoji: str = "➡️"
    trend_description: str = ""


@dataclass
class UserDynamics:
    """Полная динамика пользователя за все сессии."""
    
    # Количество диагностик
    total_sessions: int
    
    # Текущий streak (серия улучшений)
    improvement_streak: int  # 3 = три диагностики подряд с ростом
    
    # Рекорды
    best_score: int
    best_score_date: Optional[datetime]
    
    # Общий прогресс (первая vs последняя)
    overall_progress: int  # +15 / -5
    
    # Средние изменения между сессиями
    average_delta: float
    
    # Последняя динамика (если есть >=2 сессий)
    last_dynamics: Optional[DynamicsResult] = None
    
    # История сессий
    sessions: list[SessionSummary] = field(default_factory=list)


def session_to_summary(session) -> SessionSummary:
    """Конвертировать DiagnosticSession в SessionSummary."""
    # Защита от None в completed_at — используем started_at как fallback
    completed = session.completed_at or session.started_at or datetime.now()
    
    return SessionSummary(
        id=session.id,
        completed_at=completed,
        role=session.role,
        role_name=session.role_name,
        experience_name=session.experience_name,
        total_score=session.total_score or 0,
        hard_skills=session.hard_skills_score or 0,
        soft_skills=session.soft_skills_score or 0,
        thinking=session.thinking_score or 0,
        mindset=session.mindset_score or 0,
    )


def calculate_dynamics(newer: SessionSummary, older: SessionSummary) -> DynamicsResult:
    """
    Рассчитать динамику между двумя сессиями.
    
    Args:
        newer: Более новая сессия
        older: Более старая сессия
    
    Returns:
        DynamicsResult с детальным анализом изменений
    """
    # Дельты
    total_delta = newer.total_score - older.total_score
    hs_delta = newer.hard_skills - older.hard_skills
    ss_delta = newer.soft_skills - older.soft_skills
    th_delta = newer.thinking - older.thinking
    ms_delta = newer.mindset - older.mindset
    
    # Дни между сессиями
    days = (newer.completed_at - older.completed_at).days
    
    # Улучшения/ухудшения по категориям
    improved = []
    declined = []
    
    deltas = [
        ("Hard Skills", hs_delta),
        ("Soft Skills", ss_delta),
        ("Thinking", th_delta),
        ("Mindset", ms_delta),
    ]
    
    for cat, delta in deltas:
        if delta > 0:
            improved.append(f"{cat} +{delta}")
        elif delta < 0:
            declined.append(f"{cat} {delta}")
    
    # Определяем тренд
    if total_delta > 5:
        trend = "up"
        trend_emoji = "📈"
        trend_description = "Отличный прогресс!"
    elif total_delta > 0:
        trend = "up"
        trend_emoji = "⬆️"
        trend_description = "Есть рост"
    elif total_delta < -5:
        trend = "down"
        trend_emoji = "📉"
        trend_description = "Снижение результатов"
    elif total_delta < 0:
        trend = "down"
        trend_emoji = "⬇️"
        trend_description = "Небольшое снижение"
    else:
        trend = "stable"
        trend_emoji = "➡️"
        trend_description = "Стабильный результат"
    
    return DynamicsResult(
        total_delta=total_delta,
        hard_skills_delta=hs_delta,
        soft_skills_delta=ss_delta,
        thinking_delta=th_delta,
        mindset_delta=ms_delta,
        days_between=days,
        improved_categories=improved,
        declined_categories=declined,
        trend=trend,
        trend_emoji=trend_emoji,
        trend_description=trend_description,
    )


def calculate_user_dynamics(sessions: list) -> UserDynamics:
    """
    Рассчитать полную динамику пользователя.
    
    Args:
        sessions: Список DiagnosticSession (отсортирован от новых к старым)
    
    Returns:
        UserDynamics с полным анализом
    """
    if not sessions:
        return UserDynamics(
            total_sessions=0,
            improvement_streak=0,
            best_score=0,
            best_score_date=None,
            overall_progress=0,
            average_delta=0.0,
            sessions=[],
        )
    
    # Конвертируем в summary
    summaries = [session_to_summary(s) for s in sessions]
    
    # Базовые метрики
    total_sessions = len(summaries)
    best = max(summaries, key=lambda s: s.total_score)
    
    # Считаем streak (серию улучшений с конца)
    streak = 0
    if len(summaries) >= 2:
        for i in range(len(summaries) - 1):
            newer = summaries[i]
            older = summaries[i + 1]
            if newer.total_score > older.total_score:
                streak += 1
            else:
                break  # Серия прервалась
    
    # Общий прогресс (первая vs последняя)
    overall_progress = 0
    if len(summaries) >= 2:
        newest = summaries[0]
        oldest = summaries[-1]
        overall_progress = newest.total_score - oldest.total_score
    
    # Средняя дельта между сессиями
    deltas = []
    for i in range(len(summaries) - 1):
        delta = summaries[i].total_score - summaries[i + 1].total_score
        deltas.append(delta)
    avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
    
    # Последняя динамика
    last_dynamics = None
    if len(summaries) >= 2:
        last_dynamics = calculate_dynamics(summaries[0], summaries[1])
    
    return UserDynamics(
        total_sessions=total_sessions,
        improvement_streak=streak,
        best_score=best.total_score,
        best_score_date=best.completed_at,
        overall_progress=overall_progress,
        average_delta=round(avg_delta, 1),
        last_dynamics=last_dynamics,
        sessions=summaries,
    )


def format_dynamics_text(dynamics: UserDynamics) -> str:
    """
    Форматировать динамику для отправки в Telegram.
    """
    if dynamics.total_sessions == 0:
        return "📊 <b>История диагностик</b>\n\nУ тебя пока нет завершённых диагностик.\n\n<i>Пройди первую диагностику — /start</i>"
    
    # Заголовок
    text = f"""📊 <b>ИСТОРИЯ ДИАГНОСТИК</b>

<b>Всего пройдено:</b> {dynamics.total_sessions}
<b>Лучший результат:</b> {dynamics.best_score}/100"""
    
    if dynamics.best_score_date:
        date_str = dynamics.best_score_date.strftime("%d.%m.%Y")
        text += f" ({date_str})"
    
    # Общий прогресс
    if dynamics.total_sessions >= 2:
        progress_emoji = "📈" if dynamics.overall_progress > 0 else "📉" if dynamics.overall_progress < 0 else "➡️"
        progress_sign = "+" if dynamics.overall_progress > 0 else ""
        text += f"\n<b>Общий прогресс:</b> {progress_emoji} {progress_sign}{dynamics.overall_progress}"
        
        if dynamics.improvement_streak > 0:
            text += f"\n<b>Серия улучшений:</b> 🔥 {dynamics.improvement_streak}"
    
    # Последняя динамика
    if dynamics.last_dynamics:
        d = dynamics.last_dynamics
        text += f"\n\n<b>Последнее изменение:</b>"
        
        sign = "+" if d.total_delta > 0 else ""
        text += f"\n{d.trend_emoji} Общий балл: {sign}{d.total_delta} ({d.trend_description})"
        
        if d.improved_categories:
            text += f"\n🟢 Рост: {', '.join(d.improved_categories)}"
        if d.declined_categories:
            text += f"\n🔴 Снижение: {', '.join(d.declined_categories)}"
        
        text += f"\n<i>Дней между диагностиками: {d.days_between}</i>"
    
    # График (ASCII)
    text += "\n\n<b>📈 Динамика:</b>\n<code>"
    
    # Показываем последние 5 сессий (от старой к новой)
    recent = dynamics.sessions[:5][::-1]  # Переворачиваем для хронологии
    
    for s in recent:
        date_str = s.completed_at.strftime("%d.%m")
        bar_len = s.total_score // 10  # 10 символов = 100 баллов
        bar = "█" * bar_len + "░" * (10 - bar_len)
        text += f"{date_str}: {bar} {s.total_score}\n"
    
    text += "</code>"
    
    # Призыв к действию
    if dynamics.total_sessions == 1:
        text += "\n\n<i>Пройди вторую диагностику через 2-4 недели, чтобы увидеть прогресс!</i>"
    
    return text


def format_session_card(s: SessionSummary, index: int = 1) -> str:
    """Форматировать карточку одной сессии."""
    date_str = s.completed_at.strftime("%d.%m.%Y")
    
    # Уровень
    if s.total_score >= 80:
        level = "Senior/Lead"
    elif s.total_score >= 60:
        level = "Middle+"
    elif s.total_score >= 40:
        level = "Middle"
    else:
        level = "Junior"
    
    return f"""<b>{index}. {s.role_name}</b> • {date_str}
   📊 {s.total_score}/100 ({level})
   🔧 HS:{s.hard_skills} | 🗣 SS:{s.soft_skills} | 🧠 TH:{s.thinking} | 💡 MS:{s.mindset}"""

