import json
import logging
import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

from src.db.models import (
    User,
    UserSubscription,
    UserContentHistory,
    PdpPlan,
    DiagnosticSession,
)
from src.ai.client import chat_completion
from src.core.prompts.digest import DIGEST_SYSTEM_PROMPT, DIGEST_USER_PROMPT

logger = logging.getLogger(__name__)


async def send_weekly_digests(session: AsyncSession, bot: Bot) -> None:
    """
    Рассылка еженедельного дайджеста пользователям с подпиской.
    """
    logger.info("Starting weekly digest job")

    # 1. Получаем пользователей с активной подпиской
    # Которым не отправляли контент в последние 7 дней
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    # Subquery for recent content history
    recent_history_subquery = select(UserContentHistory.user_id).where(
        UserContentHistory.sent_at > seven_days_ago
    )

    stmt = (
        select(UserSubscription)
        .where(UserSubscription.is_active.is_(True))
        .where(UserSubscription.end_date > datetime.utcnow())
        .where(UserSubscription.user_id.not_in(recent_history_subquery))
    )

    result = await session.execute(stmt)
    subscriptions = result.scalars().all()

    logger.info(f"Found {len(subscriptions)} users for digest")

    for sub in subscriptions:
        try:
            await process_user_digest(session, bot, sub.user_id)
        except Exception as e:
            logger.error(f"Error processing digest for user {sub.user_id}: {e}")


async def process_user_digest(session: AsyncSession, bot: Bot, user_id: int) -> None:
    """Обработать дайджест для одного пользователя."""
    # Get user details
    user = await session.get(User, user_id)
    if not user:
        return

    # Get context (PDP or Diagnostic)
    # Try PDP first
    pdp_stmt = (
        select(PdpPlan)
        .where(PdpPlan.user_id == user_id)
        .where(PdpPlan.status == "active")
        .order_by(PdpPlan.id.desc())
        .limit(1)
    )
    pdp = (await session.execute(pdp_stmt)).scalar_one_or_none()

    skill = "General Growth"
    role = "Specialist"
    experience = "Unknown"

    if pdp and pdp.focus_skills:
        # Pick a random skill from focus_skills
        # focus_skills is a dict {"skills": ["A", "B"]}
        skills = pdp.focus_skills.get("skills", [])
        if skills:
            skill = random.choice(skills)

    # Get role/exp from diagnostic session
    diag_stmt = (
        select(DiagnosticSession)
        .where(DiagnosticSession.user_id == user_id)
        .where(DiagnosticSession.status == "completed")
        .order_by(DiagnosticSession.id.desc())
        .limit(1)
    )
    diag = (await session.execute(diag_stmt)).scalar_one_or_none()

    if diag:
        role = diag.role_name
        experience = diag.experience_name

    # Generate content
    prompt = DIGEST_USER_PROMPT.format(
        role=role, experience=experience, skill=skill, score="?"
    )

    response = await chat_completion(
        messages=[
            {"role": "system", "content": DIGEST_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    if not response:
        logger.warning(f"Empty AI response for user {user_id}")
        return

    try:
        # Try to clean markdown code blocks
        clean_resp = response.replace("```json", "").replace("```", "").strip()
        content_data = json.loads(clean_resp)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON for user {user_id}: {response}")
        return

    # Send message
    message_text = (
        f"📚 <b>Еженедельный дайджест</b>\n\n"
        f"Для навыка: <b>{skill}</b>\n\n"
        f"📌 <b>{content_data.get('title')}</b>\n"
        f"<i>{content_data.get('reason')}</i>\n\n"
    )

    url = content_data.get("url")
    if url and url.lower() != "null" and url.lower() != "none":
        message_text += f"🔗 <a href='{url}'>Читать/Смотреть</a>"

    try:
        await bot.send_message(user.telegram_id, message_text, parse_mode="HTML")

        # Save history
        history = UserContentHistory(
            user_id=user_id,
            content_type=content_data.get("type", "article"),
            title=content_data.get("title", "Unknown"),
            url=url,
            metric=skill,
            reason=content_data.get("reason"),
            sent_at=datetime.utcnow(),
        )
        session.add(history)
        await session.commit()

    except Exception as e:
        logger.error(f"Failed to send digest to telegram_id {user.telegram_id}: {e}")
