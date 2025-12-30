"""Репозитории для работы с БД."""
from src.db.repositories.user_repo import get_or_create_user, get_user_by_telegram_id
from src.db.repositories.diagnostic_repo import (
    create_session,
    get_session_by_id,
    get_active_session,
    update_session_progress,
    complete_session,
    save_answer,
    get_user_sessions,
    get_session_with_answers,
    save_feedback,
    get_average_rating,
    get_completed_sessions,
    get_user_stats,
)
from src.db.repositories import balance_repo

__all__ = [
    "get_or_create_user",
    "get_user_by_telegram_id",
    "create_session",
    "get_session_by_id",
    "get_active_session",
    "update_session_progress",
    "complete_session",
    "save_answer",
    "get_user_sessions",
    "get_session_with_answers",
    "save_feedback",
    "get_average_rating",
    "get_completed_sessions",
    "get_user_stats",
    # Монетизация
    "balance_repo",
]

