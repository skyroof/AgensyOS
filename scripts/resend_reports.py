import asyncio
import sys
import os
import aiohttp

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def send_telegram_message(bot_token: str, chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Split long messages
    max_length = 4096
    parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
    async with aiohttp.ClientSession() as session:
        for part in parts:
            payload = {
                "chat_id": chat_id,
                "text": part,
                "parse_mode": "Markdown"
            }
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    print(f"Failed to send message to {chat_id}: {await response.text()}")
                else:
                    print(f"Message part sent to {chat_id}")

async def resend_reports(session_ids: list[int]):
    print("Importing...", flush=True)
    from dotenv import load_dotenv
    load_dotenv()
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("BOT_TOKEN not found")
        return

    from src.db.session import get_session, init_db
    from src.db.models import DiagnosticSession
    
    await init_db()
    
    async with get_session() as session:
        for session_id in session_ids:
            # Fetch session with user
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            
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
                
            print(f"Resending report for session {session_id} to user {s.user.telegram_id} (@{s.user.username})")
            
            await send_telegram_message(bot_token, s.user.telegram_id, s.report)
            print(f"Done for session {session_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python resend_reports.py session_id1 session_id2 ...")
        sys.exit(1)
    
    session_ids = [int(x) for x in sys.argv[1:]]
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(resend_reports(session_ids))
