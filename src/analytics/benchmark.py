"""
Бенчмаркинг — сравнение результатов с аналогичными специалистами.

Включает:
- Расчёт перцентиля среди всех пользователей
- Сравнение по роли (designer / product)
- Сравнение по уровню опыта (junior / middle / senior / lead)
- Генерация инсайтов на основе сравнения
"""
import logging
from dataclasses import dataclass, field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import DiagnosticSession

logger = logging.getLogger(__name__)


# Минимальное количество сессий для статистической значимости
MIN_SESSIONS_FOR_STATS = 5  # Для MVP, потом увеличим до 50


@dataclass
class BenchmarkResult:
    """Результат бенчмаркинга."""
    
    # Есть ли достаточно данных для статистики
    has_enough_data: bool = False
    
    # Общий перцентиль (0-100, где 100 = лучший)
    overall_percentile: int = 50
    overall_total_sessions: int = 0
    
    # Перцентиль по роли
    role_percentile: int = 50
    role_total_sessions: int = 0
    role_name: str = ""
    
    # Перцентиль по уровню опыта
    experience_percentile: int = 50
    experience_total_sessions: int = 0
    experience_name: str = ""
    
    # Перцентиль по роли + опыту (самое точное сравнение)
    combined_percentile: int = 50
    combined_total_sessions: int = 0
    
    # Средние баллы для сравнения
    avg_score_overall: float = 50.0
    avg_score_role: float = 50.0
    avg_score_experience: float = 50.0
    avg_score_combined: float = 50.0
    
    # Инсайты
    insights: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь для PDF генератора."""
        best_pct, _ = self.get_best_percentile()
        
        return {
            "avg_score": self.avg_score_combined if self.has_enough_data else 50.0,
            "percentile": best_pct,
            "total_sessions": self.overall_total_sessions,
            "role_percentile": self.role_percentile,
            "insights": self.insights,
            "has_data": self.has_enough_data,
        }
    
    def get_best_percentile(self) -> tuple[int, str]:
        """
        Получить лучший (наиболее значимый) перцентиль.
        
        Приоритет: combined > role > experience > overall
        """
        if self.combined_total_sessions >= MIN_SESSIONS_FOR_STATS:
            return self.combined_percentile, f"{self.role_name} с опытом {self.experience_name}"
        elif self.role_total_sessions >= MIN_SESSIONS_FOR_STATS:
            return self.role_percentile, self.role_name
        elif self.experience_total_sessions >= MIN_SESSIONS_FOR_STATS:
            return self.experience_percentile, f"специалистов с опытом {self.experience_name}"
        elif self.overall_total_sessions >= MIN_SESSIONS_FOR_STATS:
            return self.overall_percentile, "всех специалистов"
        else:
            return 50, ""


async def calculate_percentile(
    session: AsyncSession,
    user_score: int,
    role: str | None = None,
    experience: str | None = None,
) -> tuple[int, int]:
    """
    Рассчитать перцентиль пользователя.
    
    Args:
        session: Сессия БД
        user_score: Балл пользователя
        role: Фильтр по роли (опционально)
        experience: Фильтр по опыту (опционально)
    
    Returns:
        (percentile, total_sessions) — перцентиль и общее число сессий
    """
    # Базовый запрос: завершённые сессии с баллом
    query = select(DiagnosticSession.total_score).where(
        DiagnosticSession.status == "completed",
        DiagnosticSession.total_score.isnot(None),
    )
    
    # Добавляем фильтры
    if role:
        query = query.where(DiagnosticSession.role == role)
    if experience:
        query = query.where(DiagnosticSession.experience == experience)
    
    result = await session.execute(query)
    all_scores = [row[0] for row in result.fetchall()]
    
    if not all_scores:
        return 50, 0
    
    total = len(all_scores)
    
    # Считаем сколько результатов ниже нашего
    below_count = sum(1 for s in all_scores if s < user_score)
    
    # Перцентиль: процент результатов, которые мы превзошли
    percentile = int((below_count / total) * 100)
    
    return percentile, total


async def calculate_average_score(
    session: AsyncSession,
    role: str | None = None,
    experience: str | None = None,
) -> tuple[float, int]:
    """
    Рассчитать средний балл.
    
    Returns:
        (average_score, total_sessions)
    """
    query = select(func.avg(DiagnosticSession.total_score)).where(
        DiagnosticSession.status == "completed",
        DiagnosticSession.total_score.isnot(None),
    )
    
    if role:
        query = query.where(DiagnosticSession.role == role)
    if experience:
        query = query.where(DiagnosticSession.experience == experience)
    
    result = await session.execute(query)
    avg = result.scalar()
    
    # Считаем количество
    count_query = select(func.count(DiagnosticSession.id)).where(
        DiagnosticSession.status == "completed",
        DiagnosticSession.total_score.isnot(None),
    )
    if role:
        count_query = count_query.where(DiagnosticSession.role == role)
    if experience:
        count_query = count_query.where(DiagnosticSession.experience == experience)
    
    count_result = await session.execute(count_query)
    count = count_result.scalar() or 0
    
    return float(avg) if avg else 50.0, count


async def get_benchmark(
    session: AsyncSession,
    user_score: int,
    role: str,
    role_name: str,
    experience: str,
    experience_name: str,
) -> BenchmarkResult:
    """
    Получить полный бенчмарк для пользователя.
    
    Args:
        session: Сессия БД
        user_score: Балл пользователя
        role: Роль (designer/product)
        role_name: Название роли
        experience: Уровень опыта (junior/middle/senior/lead)
        experience_name: Название уровня
    
    Returns:
        BenchmarkResult с полной аналитикой
    """
    result = BenchmarkResult(
        role_name=role_name,
        experience_name=experience_name,
    )
    
    # 1. Общий перцентиль (все сессии)
    overall_pct, overall_total = await calculate_percentile(session, user_score)
    result.overall_percentile = overall_pct
    result.overall_total_sessions = overall_total
    
    avg_overall, _ = await calculate_average_score(session)
    result.avg_score_overall = avg_overall
    
    # 2. По роли
    role_pct, role_total = await calculate_percentile(session, user_score, role=role)
    result.role_percentile = role_pct
    result.role_total_sessions = role_total
    
    avg_role, _ = await calculate_average_score(session, role=role)
    result.avg_score_role = avg_role
    
    # 3. По опыту
    exp_pct, exp_total = await calculate_percentile(session, user_score, experience=experience)
    result.experience_percentile = exp_pct
    result.experience_total_sessions = exp_total
    
    avg_exp, _ = await calculate_average_score(session, experience=experience)
    result.avg_score_experience = avg_exp
    
    # 4. По роли + опыту (самое точное)
    combined_pct, combined_total = await calculate_percentile(
        session, user_score, role=role, experience=experience
    )
    result.combined_percentile = combined_pct
    result.combined_total_sessions = combined_total
    
    avg_combined, _ = await calculate_average_score(session, role=role, experience=experience)
    result.avg_score_combined = avg_combined
    
    # Достаточно ли данных?
    result.has_enough_data = overall_total >= MIN_SESSIONS_FOR_STATS
    
    # Генерируем инсайты
    result.insights = _generate_benchmark_insights(result, user_score)
    
    return result


def _generate_benchmark_insights(result: BenchmarkResult, user_score: int) -> list[str]:
    """Сгенерировать инсайты на основе бенчмарка."""
    insights = []
    
    # Выбираем лучший перцентиль для основного инсайта
    best_pct, comparison_group = result.get_best_percentile()
    
    if not comparison_group:
        insights.append("📊 Пока недостаточно данных для сравнения — ты среди первых!")
        return insights
    
    # Основной инсайт по перцентилю
    if best_pct >= 90:
        insights.append(f"🏆 Ты в <b>топ-{100 - best_pct}%</b> среди {comparison_group}!")
    elif best_pct >= 75:
        insights.append(f"💪 Ты опережаешь <b>{best_pct}%</b> {comparison_group}")
    elif best_pct >= 50:
        insights.append(f"📊 Ты в <b>верхней половине</b> среди {comparison_group}")
    elif best_pct >= 25:
        insights.append(f"📈 Ты опережаешь <b>{best_pct}%</b> {comparison_group} — есть потенциал!")
    else:
        insights.append(f"🌱 Ты в начале пути — впереди большой рост!")
    
    # Сравнение со средним
    if result.combined_total_sessions >= MIN_SESSIONS_FOR_STATS:
        avg = result.avg_score_combined
        diff = user_score - avg
        if diff > 10:
            insights.append(f"⭐ Твой балл на <b>{diff:.0f} выше</b> среднего ({avg:.0f})")
        elif diff > 0:
            insights.append(f"✅ Твой балл выше среднего ({avg:.0f}) на {diff:.0f}")
        elif diff > -10:
            insights.append(f"📈 До среднего ({avg:.0f}) осталось {-diff:.0f} баллов")
        else:
            insights.append(f"🎯 Средний балл в группе: {avg:.0f} — есть к чему стремиться!")
    
    # Инсайт по динамике (если много данных)
    if result.overall_total_sessions >= 20:
        if result.role_percentile > result.overall_percentile + 10:
            insights.append(f"💡 Ты особенно силён среди {result.role_name}ов!")
        elif result.experience_percentile > result.overall_percentile + 10:
            insights.append(f"💡 Ты выделяешься среди специалистов с опытом {result.experience_name}")
    
    return insights


def format_benchmark_text(result: BenchmarkResult, user_score: int) -> str:
    """
    Форматировать бенчмарк для отправки в Telegram.
    
    Returns:
        HTML-форматированный текст
    """
    if not result.has_enough_data:
        return f"""📊 <b>БЕНЧМАРК</b>

<i>Пока собираем статистику...</i>
Всего диагностик: {result.overall_total_sessions}

Когда накопится больше данных, ты увидишь сравнение с другими специалистами!"""
    
    # Основные инсайты
    insights_text = "\n".join(f"• {i}" for i in result.insights)
    
    # Детальная статистика
    stats_lines = []
    
    if result.overall_total_sessions >= MIN_SESSIONS_FOR_STATS:
        stats_lines.append(
            f"📈 Среди всех ({result.overall_total_sessions}): "
            f"топ-{100 - result.overall_percentile}%"
        )
    
    if result.role_total_sessions >= MIN_SESSIONS_FOR_STATS:
        stats_lines.append(
            f"👤 Среди {result.role_name}ов ({result.role_total_sessions}): "
            f"топ-{100 - result.role_percentile}%"
        )
    
    if result.experience_total_sessions >= MIN_SESSIONS_FOR_STATS:
        stats_lines.append(
            f"📊 Среди {result.experience_name} ({result.experience_total_sessions}): "
            f"топ-{100 - result.experience_percentile}%"
        )
    
    if result.combined_total_sessions >= MIN_SESSIONS_FOR_STATS:
        stats_lines.append(
            f"🎯 Среди {result.role_name}ов {result.experience_name} ({result.combined_total_sessions}): "
            f"топ-{100 - result.combined_percentile}%"
        )
    
    stats_text = "\n".join(stats_lines) if stats_lines else "Статистика собирается..."
    
    return f"""📊 <b>БЕНЧМАРК</b>

{insights_text}

<b>Детализация:</b>
{stats_text}

<i>Твой балл: {user_score}/100</i>"""


def format_benchmark_short(result: BenchmarkResult) -> str:
    """Краткий формат для шапки отчёта."""
    if not result.has_enough_data:
        return ""
    
    best_pct, group = result.get_best_percentile()
    if not group:
        return ""
    
    return f"📊 Топ-{100 - best_pct}% среди {group}"

