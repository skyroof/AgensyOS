import asyncio
import logging
import os
import sys
import httpx
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_telegram_message(token: str, chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=30.0)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 1))
                logger.warning(f"Rate limited. Waiting {retry_after}s...")
                await asyncio.sleep(retry_after)
                return await send_telegram_message(token, chat_id, text)
            
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return False

async def recover_sessions():
    print("Inside recover_sessions...", flush=True)
    
    print("Importing modules...", flush=True)
    from dotenv import load_dotenv
    load_dotenv()
    
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    from src.db.session import get_session, init_db
    from src.db.models import DiagnosticSession
    from src.ai.answer_analyzer import calculate_category_scores, calibrate_scores
    from src.ai.report_gen import generate_detailed_report, generate_fallback_report, split_message
    from src.db.repositories.diagnostic_repo import complete_session
    
    print("Modules imported.", flush=True)

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN not found")
        return
    
    logger.info("🚀 Starting session recovery...")

    print("Initializing DB...", flush=True)
    await init_db()
    print("DB Initialized.", flush=True)
    
    async with get_session() as session:
        # Find stuck sessions (in_progress, has answers)
        stmt = select(DiagnosticSession).options(
            selectinload(DiagnosticSession.answers)
        ).where(
            DiagnosticSession.status == "in_progress"
        )
        
        result = await session.execute(stmt)
        sessions = result.scalars().all()
        
        logger.info(f"Found {len(sessions)} in_progress sessions.")
        
        for s in sessions:
            if not s.answers:
                logger.info(f"Session {s.id} has no answers. Skipping.")
                continue
                
            # Check if it has enough answers (e.g. > 0)
            if len(s.answers) < 3: # Skip very short sessions
                 logger.info(f"Session {s.id} has only {len(s.answers)} answers. Skipping.")
                 continue

            logger.info(f"Recovering session {s.id} for user {s.user_id}...")
            
            try:
                # 1. Reconstruct history
                history = []
                analysis_history = []
                
                # Sort answers by created_at or id
                sorted_answers = sorted(s.answers, key=lambda a: a.id)
                
                for a in sorted_answers:
                    history.append({"role": "user", "content": a.answer_text})
                    if a.analysis:
                        try:
                            # a.analysis is typically a dict if using JSON field
                            analysis = a.analysis if isinstance(a.analysis, dict) else {}
                            analysis_history.append(analysis)
                        except:
                            pass
                
                # 2. Calculate scores
                scores = calculate_category_scores(analysis_history)
                # Calibrate if possible (needs experience from session)
                if s.experience:
                     scores = calibrate_scores(scores, s.experience)
                
                # 3. Generate report
                logger.info(f"Generating report for session {s.id}...")
                
                try:
                    report_text = await generate_detailed_report(
                        role=s.role or "Specialist",
                        role_name=s.role_name or "Specialist",
                        experience=s.experience or "Middle",
                        conversation_history=history,
                        analysis_history=analysis_history
                    )
                except Exception as e:
                    logger.error(f"Report gen failed: {e}")
                    # Fallback
                    report_text = generate_fallback_report(
                         role_name=s.role_name or "Specialist",
                         experience=s.experience or "Middle",
                         scores=scores,
                         insights=[],
                         gaps=[]
                    )
                
                # 4. Save to DB
                await complete_session(
                    session,
                    s.id,
                    scores,
                    report_text,
                    history,
                    analysis_history
                )
                logger.info(f"Session {s.id} marked as completed.")
                
                # 5. Send to user
                summary = (
                    f"✅ <b>Твой результат готов!</b>\n\n"
                    f"Role: <b>{s.role_name}</b>\n"
                    f"Level: <b>{s.experience_name}</b>\n"
                    f"Total Score: <b>{scores.get('total', 0)}/100</b>\n\n"
                    f"👇 Твой подробный отчет ниже"
                )
                
                await send_telegram_message(bot_token, s.user_id, summary)
                
                parts = split_message(report_text)
                for part in parts:
                    await send_telegram_message(bot_token, s.user_id, part)
                    await asyncio.sleep(0.5)
                
                logger.info(f"Report sent to user {s.user_id}.")
                
            except Exception as e:
                logger.error(f"Error recovering session {s.id}: {e}", exc_info=True)

if __name__ == "__main__":
    print("Running main...", flush=True)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(recover_sessions())
