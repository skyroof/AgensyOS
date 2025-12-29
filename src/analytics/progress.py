"""
Трекинг прогресса — сравнение между диагностиками.

Включает:
- Сравнение первой и последней диагностики
- Динамика по категориям (Hard/Soft/Thinking/Mindset)
- Улучшившиеся и ухудшившиеся метрики
- Рекомендации на основе динамики
- Визуализация тренда (текстовая)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import DiagnosticSession
from src.ai.answer_analyzer import (
    ALL_METRICS,
    METRIC_NAMES_RU,
    METRIC_CATEGORIES,
    calculate_category_scores,
)

logger = logging.getLogger(__name__)


@dataclass
class ProgressReport:
    """Отчёт о прогрессе между диагностиками."""
    
    # Есть ли данные для сравнения
    has_progress_data: bool = False
    
    # Количество диагностик
    sessions_count: int = 0
    
    # Даты
    first_date: Optional[datetime] = None
    last_date: Optional[datetime] = None
    days_between: int = 0
    
    # === ДИНАМИКА ОБЩЕГО СКОРА ===
    first_score: int = 0
    last_score: int = 0
    score_change: int = 0  # Положительное = рост
    score_change_percent: float = 0.0
    
    # Тренд: growing / stable / declining
    score_trend: str = "stable"
    trend_emoji: str = "➡️"
    trend_description: str = ""
    
    # === ДИНАМИКА ПО КАТЕГОРИЯМ ===
    # {"hard_skills": +5, "soft_skills": -2, ...}
    category_changes: dict[str, int] = field(default_factory=dict)
    
    # Первые и последние значения по категориям
    first_categories: dict[str, int] = field(default_factory=dict)
    last_categories: dict[str, int] = field(default_factory=dict)
    
    # === ДИНАМИКА ПО МЕТРИКАМ ===
    # {"depth": +1.5, "creativity": -0.5, ...}
    metric_changes: dict[str, float] = field(default_factory=dict)
    
    # Топ улучшений и ухудшений
    improved_metrics: list[str] = field(default_factory=list)  # Топ-3 роста
    declined_metrics: list[str] = field(default_factory=list)  # Топ-3 падения
    stable_metrics: list[str] = field(default_factory=list)  # Без изменений
    
    # === ИСТОРИЯ БАЛЛОВ ===
    # Для построения графика: [(date, score), ...]
    score_history: list[tuple[datetime, int]] = field(default_factory=list)
    
    # === РЕКОМЕНДАЦИИ ===
    recommendations: list[str] = field(default_factory=list)
    
    # === ИНСАЙТЫ ===
    insights: list[str] = field(default_factory=list)


async def get_user_progress(
    session: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> ProgressReport:
    """
    Получить отчёт о прогрессе пользователя.
    
    Args:
        session: Сессия БД
        user_id: ID пользователя в БД
        limit: Максимум диагностик для анализа
    
    Returns:
        ProgressReport с полной аналитикой
    """
    result = ProgressReport()
    
    # Получаем завершённые сессии пользователя
    query = (
        select(DiagnosticSession)
        .where(
            DiagnosticSession.user_id == user_id,
            DiagnosticSession.status == "completed",
            DiagnosticSession.total_score.isnot(None),
        )
        .order_by(DiagnosticSession.completed_at.asc())
        .limit(limit)
    )
    
    query_result = await session.execute(query)
    sessions = list(query_result.scalars().all())
    
    result.sessions_count = len(sessions)
    
    if len(sessions) < 2:
        # Недостаточно данных для сравнения
        result.has_progress_data = False
        if len(sessions) == 1:
            result.first_score = sessions[0].total_score
            result.last_score = sessions[0].total_score
            result.first_date = sessions[0].completed_at
            result.last_date = sessions[0].completed_at
            result.score_history = [(sessions[0].completed_at, sessions[0].total_score)]
        return result
    
    result.has_progress_data = True
    
    first_session = sessions[0]
    last_session = sessions[-1]
    
    # === БАЗОВЫЕ ДАННЫЕ ===
    result.first_date = first_session.completed_at
    result.last_date = last_session.completed_at
    result.days_between = (last_session.completed_at - first_session.completed_at).days if first_session.completed_at and last_session.completed_at else 0
    
    result.first_score = first_session.total_score
    result.last_score = last_session.total_score
    result.score_change = last_session.total_score - first_session.total_score
    
    if first_session.total_score > 0:
        result.score_change_percent = (result.score_change / first_session.total_score) * 100
    
    # === ИСТОРИЯ БАЛЛОВ ===
    result.score_history = [
        (s.completed_at, s.total_score)
        for s in sessions
        if s.completed_at and s.total_score
    ]
    
    # === ТРЕНД ===
    if result.score_change > 5:
        result.score_trend = "growing"
        result.trend_emoji = "📈"
        result.trend_description = "Отличная динамика роста!"
    elif result.score_change < -5:
        result.score_trend = "declining"
        result.trend_emoji = "📉"
        result.trend_description = "Есть снижение — стоит обратить внимание"
    else:
        result.score_trend = "stable"
        result.trend_emoji = "➡️"
        result.trend_description = "Стабильный уровень"
    
    # === КАТЕГОРИИ ===
    result.first_categories = {
        "hard_skills": first_session.hard_skills_score or 0,
        "soft_skills": first_session.soft_skills_score or 0,
        "thinking": first_session.thinking_score or 0,
        "mindset": first_session.mindset_score or 0,
    }
    
    result.last_categories = {
        "hard_skills": last_session.hard_skills_score or 0,
        "soft_skills": last_session.soft_skills_score or 0,
        "thinking": last_session.thinking_score or 0,
        "mindset": last_session.mindset_score or 0,
    }
    
    result.category_changes = {
        cat: result.last_categories[cat] - result.first_categories[cat]
        for cat in result.first_categories
    }
    
    # === МЕТРИКИ ===
    first_metrics = _extract_metrics_from_session(first_session)
    last_metrics = _extract_metrics_from_session(last_session)
    
    result.metric_changes = {
        metric: last_metrics.get(metric, 5) - first_metrics.get(metric, 5)
        for metric in ALL_METRICS
    }
    
    # Топ улучшений (положительные изменения)
    sorted_improvements = sorted(
        [(m, c) for m, c in result.metric_changes.items() if c > 0.5],
        key=lambda x: x[1],
        reverse=True
    )
    result.improved_metrics = [m for m, _ in sorted_improvements[:3]]
    
    # Топ ухудшений (отрицательные изменения)
    sorted_declines = sorted(
        [(m, c) for m, c in result.metric_changes.items() if c < -0.5],
        key=lambda x: x[1]
    )
    result.declined_metrics = [m for m, _ in sorted_declines[:3]]
    
    # Стабильные метрики
    result.stable_metrics = [
        m for m, c in result.metric_changes.items()
        if -0.5 <= c <= 0.5
    ]
    
    # === РЕКОМЕНДАЦИИ ===
    result.recommendations = _generate_progress_recommendations(result)
    
    # === ИНСАЙТЫ ===
    result.insights = _generate_progress_insights(result, sessions)
    
    return result


def _extract_metrics_from_session(session: DiagnosticSession) -> dict[str, float]:
    """Извлечь средние метрики из сессии."""
    analysis_history = session.analysis_history or []
    
    if not analysis_history:
        return {m: 5.0 for m in ALL_METRICS}
    
    all_scores = {metric: [] for metric in ALL_METRICS}
    
    for analysis in analysis_history:
        scores = analysis.get("scores", {})
        for metric in ALL_METRICS:
            if metric in scores:
                all_scores[metric].append(scores[metric])
    
    return {
        k: sum(v) / len(v) if v else 5.0
        for k, v in all_scores.items()
    }


def _generate_progress_recommendations(report: ProgressReport) -> list[str]:
    """Сгенерировать рекомендации на основе динамики."""
    recommendations = []
    
    # По общему тренду
    if report.score_trend == "growing":
        recommendations.append(
            "🚀 Продолжай в том же духе! Твой подход к развитию работает."
        )
    elif report.score_trend == "declining":
        recommendations.append(
            "🎯 Рекомендую пересмотреть подход к подготовке. "
            "Возможно, стоит сфокусироваться на практике."
        )
    else:
        recommendations.append(
            "💡 Для роста попробуй выйти из зоны комфорта — "
            "возьми более сложные задачи или новые проекты."
        )
    
    # По ухудшившимся метрикам
    if report.declined_metrics:
        worst_metric = report.declined_metrics[0]
        metric_name = METRIC_NAMES_RU.get(worst_metric, worst_metric)
        
        advice_map = {
            "depth": "Практикуй технику '5 почему' для глубокого анализа",
            "structure": "Используй фреймворки (MECE, пирамида Минто) для структурирования",
            "creativity": "Пробуй техники латерального мышления и brainstorming",
            "systems_thinking": "Рисуй системные карты для понимания взаимосвязей",
            "expertise": "Углубляй экспертизу через практику и изучение кейсов",
            "methodology": "Освой 1-2 новых методологии и применяй на проектах",
            "tools_proficiency": "Выдели время на изучение продвинутых техник в инструментах",
            "articulation": "Практикуй презентации и письменную коммуникацию",
            "self_awareness": "Запрашивай регулярный feedback от коллег",
            "conflict_handling": "Изучи техники медиации и активного слушания",
            "honesty": "Практикуй открытость — начни с анализа своих ошибок на ретро",
            "growth_orientation": "Создай личный learning plan с конкретными целями",
        }
        
        advice = advice_map.get(worst_metric, f"Уделяй больше внимания развитию: {metric_name}")
        recommendations.append(f"📈 {metric_name}: {advice}")
    
    # По улучшившимся метрикам
    if report.improved_metrics:
        best_metric = report.improved_metrics[0]
        metric_name = METRIC_NAMES_RU.get(best_metric, best_metric)
        change = report.metric_changes.get(best_metric, 0)
        recommendations.append(
            f"⭐ Отличный рост в '{metric_name}' (+{change:.1f})! "
            f"Продолжай развивать эту сильную сторону."
        )
    
    # По периоду
    if report.days_between > 60:
        recommendations.append(
            "⏰ Между диагностиками прошло больше 2 месяцев — "
            "рекомендую проходить чаще для отслеживания прогресса."
        )
    elif report.days_between < 7:
        recommendations.append(
            "📅 Диагностики слишком часто — между ними должно пройти время на практику."
        )
    
    return recommendations[:4]  # Максимум 4 рекомендации


def _generate_progress_insights(
    report: ProgressReport,
    sessions: list[DiagnosticSession],
) -> list[str]:
    """Сгенерировать инсайты о прогрессе."""
    insights = []
    
    # Основной инсайт по изменению
    if report.score_change > 0:
        insights.append(
            f"{report.trend_emoji} Твой балл вырос на <b>{report.score_change}</b> "
            f"({report.first_score} → {report.last_score})"
        )
    elif report.score_change < 0:
        insights.append(
            f"{report.trend_emoji} Балл снизился на <b>{abs(report.score_change)}</b> "
            f"({report.first_score} → {report.last_score})"
        )
    else:
        insights.append(
            f"{report.trend_emoji} Балл стабилен: <b>{report.last_score}</b>"
        )
    
    # По категориям
    best_category = max(report.category_changes.items(), key=lambda x: x[1])
    worst_category = min(report.category_changes.items(), key=lambda x: x[1])
    
    category_names = {
        "hard_skills": "Hard Skills",
        "soft_skills": "Soft Skills",
        "thinking": "Мышление",
        "mindset": "Mindset",
    }
    
    if best_category[1] > 2:
        insights.append(
            f"💪 Лучший рост в <b>{category_names[best_category[0]]}</b>: +{best_category[1]}"
        )
    
    if worst_category[1] < -2:
        insights.append(
            f"📉 Снижение в <b>{category_names[worst_category[0]]}</b>: {worst_category[1]}"
        )
    
    # По количеству диагностик
    if report.sessions_count >= 5:
        insights.append(f"📊 Ты прошёл уже <b>{report.sessions_count}</b> диагностик — отличный трек!")
    elif report.sessions_count >= 3:
        insights.append(f"📊 У тебя <b>{report.sessions_count}</b> диагностики — хорошая база для анализа")
    
    # По периоду
    if report.days_between > 0:
        if report.days_between >= 30:
            months = report.days_between // 30
            insights.append(f"⏱️ Период анализа: ~{months} мес.")
        else:
            insights.append(f"⏱️ Период анализа: {report.days_between} дней")
    
    return insights


def format_progress_text(report: ProgressReport) -> str:
    """
    Форматировать отчёт о прогрессе для Telegram.
    
    Returns:
        HTML-форматированный текст
    """
    if not report.has_progress_data:
        if report.sessions_count == 1:
            return f"""📊 <b>ПРОГРЕСС</b>

У тебя пока только <b>1 диагностика</b> (балл: {report.first_score}/100).

Пройди ещё одну через некоторое время, чтобы отслеживать прогресс!
Рекомендуемый интервал: 2-4 недели."""
        else:
            return """📊 <b>ПРОГРЕСС</b>

Нет завершённых диагностик для анализа."""
    
    # Инсайты
    insights_text = "\n".join(f"• {i}" for i in report.insights)
    
    # График (текстовый)
    graph = _generate_text_graph(report.score_history)
    
    # Изменения по категориям
    category_lines = []
    category_names = {
        "hard_skills": "🔧 Hard Skills",
        "soft_skills": "🤝 Soft Skills",
        "thinking": "🧠 Мышление",
        "mindset": "💫 Mindset",
    }
    
    for cat, name in category_names.items():
        first = report.first_categories.get(cat, 0)
        last = report.last_categories.get(cat, 0)
        change = report.category_changes.get(cat, 0)
        
        if change > 0:
            arrow = "↑"
        elif change < 0:
            arrow = "↓"
        else:
            arrow = "→"
        
        category_lines.append(f"{name}: {first} → {last} ({arrow}{abs(change)})")
    
    categories_text = "\n".join(category_lines)
    
    # Улучшения и ухудшения
    changes_text = ""
    if report.improved_metrics:
        improved_names = [METRIC_NAMES_RU.get(m, m) for m in report.improved_metrics[:3]]
        changes_text += f"\n✅ <b>Улучшилось:</b> {', '.join(improved_names)}"
    
    if report.declined_metrics:
        declined_names = [METRIC_NAMES_RU.get(m, m) for m in report.declined_metrics[:3]]
        changes_text += f"\n⚠️ <b>Снизилось:</b> {', '.join(declined_names)}"
    
    # Рекомендации
    recommendations_text = "\n".join(f"• {r}" for r in report.recommendations)
    
    return f"""📊 <b>ПРОГРЕСС</b>

{insights_text}

<b>📈 ДИНАМИКА БАЛЛОВ</b>
{graph}

<b>📋 ПО КАТЕГОРИЯМ</b>
{categories_text}
{changes_text}

<b>💡 РЕКОМЕНДАЦИИ</b>
{recommendations_text}"""


def _generate_text_graph(score_history: list[tuple[datetime, int]]) -> str:
    """Сгенерировать текстовый график баллов."""
    if not score_history:
        return "Нет данных"
    
    if len(score_history) == 1:
        return f"• {score_history[0][1]}/100"
    
    # Простой текстовый график
    lines = []
    
    for i, (date, score) in enumerate(score_history):
        # Формируем бар
        bar_length = score // 5  # 20 символов максимум
        bar = "█" * bar_length + "░" * (20 - bar_length)
        
        # Дата
        date_str = date.strftime("%d.%m") if date else f"#{i+1}"
        
        # Стрелка для показа изменения
        if i > 0:
            prev_score = score_history[i-1][1]
            if score > prev_score:
                arrow = " ↑"
            elif score < prev_score:
                arrow = " ↓"
            else:
                arrow = ""
        else:
            arrow = ""
        
        lines.append(f"<code>{date_str} {bar} {score}{arrow}</code>")
    
    return "\n".join(lines)


def format_progress_short(report: ProgressReport) -> str:
    """Краткий формат для шапки."""
    if not report.has_progress_data:
        return ""
    
    if report.score_change > 0:
        return f"📈 +{report.score_change} с первой диагностики"
    elif report.score_change < 0:
        return f"📉 {report.score_change} с первой диагностики"
    else:
        return f"➡️ Стабильный результат"

