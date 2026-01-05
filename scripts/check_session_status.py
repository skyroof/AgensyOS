import asyncio
import sys
import os
from sqlalchemy import select

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def check_status(session_id: int):
    print("Importing...", flush=True)
    from dotenv import load_dotenv
    load_dotenv()
    
    from src.db.session import get_session, init_db
    from src.db.models import DiagnosticSession
    
    await init_db()
    
    async with get_session() as session:
        stmt = select(DiagnosticSession).where(DiagnosticSession.id == session_id)
        result = await session.execute(stmt)
        s = result.scalar_one_or_none()
        
        if s:
            print(f"Session {session_id}: status={s.status}, report_len={len(s.report) if s.report else 0}")
        else:
            print(f"Session {session_id} not found")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_session_status.py <session_id>")
        sys.exit(1)
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(check_status(int(sys.argv[1])))
