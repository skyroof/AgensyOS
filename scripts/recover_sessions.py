import asyncio
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def recover_sessions():
    print("Inside recover_sessions...", flush=True)
    
    print("Importing modules...", flush=True)
    from dotenv import load_dotenv
    load_dotenv()
    
    from aiogram import Bot
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    from src.db.session import get_session, init_db
    from src.db.models import DiagnosticSession
    from src.ai.answer_analyzer import calculate_category_scores, calibrate_scores
    from src.ai.report_gen import generate_detailed_report, generate_fallback_report
    from src.bot.keyboards.inline import get_post_diagnostic_keyboard
    from src.db.repositories.diagnostic_repo import complete_session
    from src.bot.handlers.diagnostic import achievements
    from src.ai.report_gen import split_message
    
    print("Modules imported.", flush=True)

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN not found")
        return

    bot = Bot(token=bot_token)
    
    logger.info("🚀 Starting session recovery...")

    print("Initializing DB...", flush=True)
    await init_db()
    print("DB Initialized.", flush=True)
    
    async with get_session() as session:
        # Find stuck sessions
        stmt = (
            select(DiagnosticSession)
            .options(
                selectinload(DiagnosticSession.user),
                selectinload(DiagnosticSession.answers)
            )
            .where(DiagnosticSession.status == "in_progress")
            .where(DiagnosticSession.completed_at.is_(None))
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
                
                # Calculate scores
                scores = calculate_category_scores(analysis_history)
                scores = calibrate_scores(scores, ds.experience)
                
                # Generate report
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
    print("Running main...", flush=True)
    asyncio.run(recover_sessions())
