"""Аналитический модуль для профилей компетенций, бенчмаркинга, трекинга прогресса и PDP."""
from src.analytics.competency_profile import (
    CompetencyProfile,
    build_profile,
    format_profile_text,
    format_profile_short,
)
from src.analytics.benchmark import (
    BenchmarkResult,
    get_benchmark,
    calculate_percentile,
    format_benchmark_text,
    format_benchmark_short,
)
from src.analytics.progress import (
    ProgressReport,
    get_user_progress,
    format_progress_text,
    format_progress_short,
)
from src.analytics.pdp import (
    PersonalDevelopmentPlan,
    build_pdp,
    format_pdp_text,
    format_pdp_short,
)

__all__ = [
    # Профиль компетенций
    "CompetencyProfile",
    "build_profile",
    "format_profile_text",
    "format_profile_short",
    # Бенчмаркинг
    "BenchmarkResult",
    "get_benchmark",
    "calculate_percentile",
    "format_benchmark_text",
    "format_benchmark_short",
    # Трекинг прогресса
    "ProgressReport",
    "get_user_progress",
    "format_progress_text",
    "format_progress_short",
    # Personal Development Plan
    "PersonalDevelopmentPlan",
    "build_pdp",
    "format_pdp_text",
    "format_pdp_short",
]



