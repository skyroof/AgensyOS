import asyncio
import logging
import os
import sys
print("Script started", flush=True)
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.session import get_session, init_db
from src.db.models import DiagnosticSession, User, Answer
from src.ai.answer_analyzer import calculate_category_scores, calibrate_scores
from src.ai.report_gen import generate_detailed_report, generate_fallback_report
from src.bot.handlers.diagnostic import generate_final_achievements
from src.utils.message_splitter import send_long_message
from src.bot.keyboards.inline import get_post_diagnostic_keyboard
from src.db.repositories.diagnostic_repo import complete_session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

async def recover_sessions():
    """Восстановить прерванные сессии и отправить отчеты."""
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN not found")
        return

    bot = Bot(token=bot_token)
    
    print("🚀 Starting session recovery...", flush=True)
    logger.info("🚀 Starting session recovery...")

    print("Initializing DB...", flush=True)
    await init_db()
    print("DB Initialized.", flush=True)
    
    async with get_session() as session:
        # Find stuck sessions
        # Logic: in_progress, created recently (e.g., last 24h), and has answers
        stmt = (
            select(DiagnosticSession)
            .options(
                selectinload(DiagnosticSession.user),
                selectinload(DiagnosticSession.answers)
            )
            .where(DiagnosticSession.status == "in_progress")
            .where(DiagnosticSession.completed_at.is_(None))
            # We assume if they have >= 10 answers (or near that), they finished but crashed
        )
        
        result = await session.execute(stmt)
        stuck_sessions = result.scalars().all()
        
        logger.info(f"Found {len(stuck_sessions)} in_progress sessions.")
        
        recovered_count = 0
        
        for ds in stuck_sessions:
            try:
                # Check if they really finished
                answers_count = len(ds.answers)
                if answers_count < 10:
                    logger.info(f"Session {ds.id} (User {ds.user_id}) has only {answers_count} answers. Skipping.")
                    continue
                
                logger.info(f"🔄 Recovering session {ds.id} for User {ds.user.telegram_id} ({answers_count} answers)...")
                
                # Reconstruct history and analysis
                history = []
                analysis_history = []
                
                # Sort answers by question number
                sorted_answers = sorted(ds.answers, key=lambda a: a.question_number)
                
                for ans in sorted_answers:
                    history.append({
                        "question": ans.question_text,
                        "answer": ans.answer_text
                    })
                    if ans.analysis:
                        analysis_history.append(ans.analysis)
                
                # If analysis is missing in answers (shouldn't happen if they passed), try session
                if not analysis_history and ds.analysis_history:
                    if isinstance(ds.analysis_history, list):
                        analysis_history = ds.analysis_history
                
                if not analysis_history:
                    logger.warning(f"No analysis history for session {ds.id}. Skipping.")
                    continue

                # Calculate scores
                scores = calculate_category_scores(analysis_history)
                scores = calibrate_scores(scores, ds.experience)
                
                # Generate report
                logger.info(f"Generating report for session {ds.id}...")
                
                try:
                    report_text = await generate_detailed_report(
                        role=ds.role,
                        role_name=ds.role_name,
                        experience=ds.experience,
                        conversation_history=history,
                        analysis_history=analysis_history
                    )
                except Exception as e:
                    logger.error(f"Failed to generate detailed report: {e}")
                    # Fallback
                    all_insights = []
                    all_gaps = []
                    for analysis in analysis_history:
                        all_insights.extend(analysis.get("key_insights", []))
                        all_gaps.extend(analysis.get("gaps", []))
                        
                    report_text = generate_fallback_report(
                        role_name=ds.role_name,
                        experience=ds.experience,
                        scores=scores,
                        insights=all_insights,
                        gaps=all_gaps
                    )

                # Save to DB
                await complete_session(
                    session,
                    ds.id,
                    scores,
                    report_text,
                    history,
                    analysis_history
                )
                await session.commit()
                
                # Send to user
                user_id = ds.user.telegram_id
                
                # Achievements
                # Need dummy answer_stats or reconstruct from DB?
                # DB doesn't store duration per answer easily unless we diff created_at
                # Let's mock it or skip achievements logic reliant on time
                answer_stats = [] # Passed as empty, achievements will be minimal
                
                achievements = generate_final_achievements(answer_stats)
                
                summary = (
                    f"✅ <b>Твой результат готов!</b>\n"
                    f"(Восстановлен после сбоя)\n\n"
                    f"Role: <b>{ds.role_name}</b>\n"
                    f"Level: <b>{ds.experience_name}</b>\n"
                    f"Total Score: <b>{scores['total']}/100</b>\n"
                    f"{achievements}\n\n"
                    f"👇 Твой подробный отчет ниже"
                )
                
                try:
                    await bot.send_message(user_id, summary)
                    
                    # Split and send report
                    # We can use send_long_message but it requires 'message' object usually?
                    # No, send_long_message takes 'message' object to call .answer()
                    # We need to manually split and send via bot.send_message
                    
                    from src.ai.report_gen import split_message
                    parts = split_message(report_text)
                    
                    for part in parts:
                        await bot.send_message(user_id, part)
                        
                    # Post diagnostic keyboard
                    await bot.send_message(
                        user_id,
                        "Что делать дальше?",
                        reply_markup=get_post_diagnostic_keyboard()
                    )
                    
                    logger.info(f"✅ Successfully recovered session {ds.id}")
                    recovered_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}: {e}")
            
            except Exception as e:
                logger.error(f"Error processing session {ds.id}: {e}", exc_info=True)
                
        logger.info(f"Recovery finished. Recovered {recovered_count} sessions.")
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(recover_sessions())
