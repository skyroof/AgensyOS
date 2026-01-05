import asyncio
import sys
import os
import aiohttp
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def send_telegram_document(bot_token: str, chat_id: int, document_bytes: bytes, filename: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    
    data = aiohttp.FormData()
    data.add_field('chat_id', str(chat_id))
    data.add_field('document', document_bytes, filename=filename)
    if caption:
        data.add_field('caption', caption)
        
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            if response.status != 200:
                print(f"Failed to send document to {chat_id}: {await response.text()}")
            else:
                print(f"Document sent to {chat_id}")

async def send_pdf_reports(session_ids: list[int]):
    print("Importing modules...", flush=True)
    from dotenv import load_dotenv
    load_dotenv()
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("BOT_TOKEN not found")
        return

    print("Importing DB...", flush=True)
    from src.db.session import get_session, init_db
    from src.db.models import DiagnosticSession
    
    print("Importing PDF generator...", flush=True)
    try:
        from src.utils.pdf_generator import generate_pdf_report
        print("PDF generator imported.", flush=True)
    except Exception as e:
        print(f"Failed to import PDF generator: {e}", flush=True)
        return
    
    print("Importing Analytics...", flush=True)
    try:
        from src.ai.answer_analyzer import calculate_category_scores, calibrate_scores, METRIC_NAMES_RU
        print("Answer analyzer imported.", flush=True)
        from src.analytics import build_profile
        print("Analytics imported.", flush=True)
    except Exception as e:
        print(f"Failed to import Analytics: {e}", flush=True)
        return

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    print("Initializing DB...", flush=True)
    await init_db()
    
    async with get_session() as session:
        for session_id in session_ids:
            print(f"Processing session {session_id}...", flush=True)
            stmt = select(DiagnosticSession).options(
                selectinload(DiagnosticSession.user)
            ).where(DiagnosticSession.id == session_id)
            
            result = await session.execute(stmt)
            s = result.scalar_one_or_none()
            
            if not s:
                print(f"Session {session_id} not found")
                continue
                
            if not s.report:
                print(f"Session {session_id} has no report")
                continue
                
            user_name = s.user.first_name or "Кандидат"
            if s.user.last_name:
                user_name += f" {s.user.last_name}"
            
            print(f"Generating PDF for {user_name} (ID: {s.user.telegram_id})...", flush=True)
            
            # Reconstruct data for PDF
            scores = {
                "total": s.total_score or 0,
                "hard_skills": s.hard_skills_score or 0,
                "soft_skills": s.soft_skills_score or 0,
                "thinking": s.thinking_score or 0,
                "mindset": s.mindset_score or 0,
            }
            
            conversation_history = s.conversation_history or []
            report_text = s.report
            analysis_history = s.analysis_history or []
            
            profile_data = None
            raw_averages = None
            
            if analysis_history:
                try:
                    raw_scores = calculate_category_scores(analysis_history)
                    calibrated = calibrate_scores(raw_scores, s.experience)
                    raw_averages = calibrated.get("raw_averages", {})
                    
                    profile = build_profile(
                        role=s.role,
                        role_name=s.role_name,
                        experience=s.experience,
                        experience_name=s.experience_name,
                        scores=calibrated,
                        analysis_history=analysis_history,
                    )
                    
                    profile_data = {
                        "strengths": [METRIC_NAMES_RU.get(st, st) for st in profile.strengths],
                        "growth_areas": [METRIC_NAMES_RU.get(ga, ga) for ga in profile.growth_areas],
                        "top_competencies": profile.top_competencies,
                    }
                except Exception as e:
                    print(f"Warning: Failed to build profile data: {e}")
            
            try:
                pdf_bytes = generate_pdf_report(
                    role_name=s.role_name,
                    experience=s.experience_name,
                    scores=scores,
                    report_text=report_text,
                    conversation_history=conversation_history,
                    user_name=user_name,
                    profile_data=profile_data,
                    pdp_data=None, # PDP generation might be complex to replicate here quickly, skipping for now as it's optional
                    benchmark_data=None, # Benchmark generation might be complex to replicate here quickly, skipping for now as it's optional
                    raw_averages=raw_averages,
                )
                
                date_str = s.completed_at.strftime("%Y%m%d") if s.completed_at else "report"
                filename = f"diagnostic_{s.role}_{date_str}.pdf"
                
                print(f"Sending PDF ({len(pdf_bytes)} bytes)...", flush=True)
                await send_telegram_document(bot_token, s.user.telegram_id, pdf_bytes, filename, caption="Ваш PDF отчет")
                print(f"Done for session {session_id}")
                
            except Exception as e:
                print(f"Error generating/sending PDF for session {session_id}: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Send PDF reports for specific sessions")
    parser.add_argument("session_ids", nargs="+", type=int, help="List of session IDs")
    parser.add_argument("--target-id", type=int, help="Optional Telegram ID to send reports to (instead of the user)", default=None)
    
    args = parser.parse_args()
    
    # Monkey patch send_telegram_document to redirect if target_id is set
    original_send = send_telegram_document
    
    if args.target_id:
        print(f"REDIRECTING ALL REPORTS TO: {args.target_id}")
        async def redirected_send(bot_token, chat_id, document_bytes, filename, caption=""):
            await original_send(bot_token, args.target_id, document_bytes, filename, caption)
        send_telegram_document = redirected_send
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(send_pdf_reports(args.session_ids))
