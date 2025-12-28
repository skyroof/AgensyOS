"""
Репозиторий для работы с диагностическими сессиями.
"""
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import DiagnosticSession, Answer, User


async def create_session(
    session: AsyncSession,
    user_id: int,
    role: str,
    role_name: str,
    experience: str,
    experience_name: str,
) -> DiagnosticSession:
    """Создать новую сессию диагностики."""
    diagnostic_session = DiagnosticSession(
        user_id=user_id,
        role=role,
        role_name=role_name,
        experience=experience,
        experience_name=experience_name,
        status="in_progress",
        current_question=1,
    )
    session.add(diagnostic_session)
    await session.commit()
    await session.refresh(diagnostic_session)
    
    return diagnostic_session


async def get_session_by_id(
    session: AsyncSession,
    session_id: int,
) -> DiagnosticSession | None:
    """Получить сессию по ID."""
    stmt = select(DiagnosticSession).where(DiagnosticSession.id == session_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_session(
    session: AsyncSession,
    user_id: int,
) -> DiagnosticSession | None:
    """Получить активную (незавершённую) сессию пользователя."""
    stmt = (
        select(DiagnosticSession)
        .where(DiagnosticSession.user_id == user_id)
        .where(DiagnosticSession.status == "in_progress")
        .order_by(DiagnosticSession.started_at.desc())
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_session_progress(
    session: AsyncSession,
    session_id: int,
    current_question: int,
    conversation_history: list[dict],
    analysis_history: list[dict],
) -> None:
    """Обновить прогресс сессии."""
    stmt = (
        update(DiagnosticSession)
        .where(DiagnosticSession.id == session_id)
        .values(
            current_question=current_question,
            conversation_history=conversation_history,
            analysis_history=analysis_history,
        )
    )
    await session.execute(stmt)
    await session.commit()


async def complete_session(
    session: AsyncSession,
    session_id: int,
    scores: dict,
    report: str,
    conversation_history: list[dict],
    analysis_history: list[dict],
) -> None:
    """Завершить сессию и сохранить результаты."""
    stmt = (
        update(DiagnosticSession)
        .where(DiagnosticSession.id == session_id)
        .values(
            status="completed",
            completed_at=datetime.utcnow(),
            total_score=scores.get("total"),
            hard_skills_score=scores.get("hard_skills"),
            soft_skills_score=scores.get("soft_skills"),
            thinking_score=scores.get("thinking"),
            mindset_score=scores.get("mindset"),
            report=report,
            conversation_history=conversation_history,
            analysis_history=analysis_history,
        )
    )
    await session.execute(stmt)
    await session.commit()


async def save_answer(
    session: AsyncSession,
    diagnostic_session_id: int,
    question_number: int,
    question_text: str,
    answer_text: str,
    analysis: dict | None = None,
) -> Answer:
    """Сохранить ответ на вопрос."""
    scores = analysis.get("scores", {}) if analysis else {}
    
    answer = Answer(
        session_id=diagnostic_session_id,
        question_number=question_number,
        question_text=question_text,
        answer_text=answer_text,
        depth_score=scores.get("depth"),
        self_awareness_score=scores.get("self_awareness"),
        structure_score=scores.get("structure"),
        honesty_score=scores.get("honesty"),
        expertise_score=scores.get("expertise"),
        analysis=analysis,
    )
    session.add(answer)
    await session.commit()
    await session.refresh(answer)
    
    return answer


async def get_user_sessions(
    session: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> list[DiagnosticSession]:
    """Получить историю сессий пользователя."""
    stmt = (
        select(DiagnosticSession)
        .where(DiagnosticSession.user_id == user_id)
        .order_by(DiagnosticSession.started_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_session_with_answers(
    session: AsyncSession,
    session_id: int,
) -> DiagnosticSession | None:
    """Получить сессию со всеми ответами."""
    stmt = (
        select(DiagnosticSession)
        .where(DiagnosticSession.id == session_id)
        .options(selectinload(DiagnosticSession.answers))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

