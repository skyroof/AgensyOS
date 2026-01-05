import asyncio
import logging
import os
import sys
from sqlalchemy import update

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reset_session(session_id: int):
    print("Importing modules...", flush=True)
    from dotenv import load_dotenv
    load_dotenv()
    
    from src.db.session import get_session, init_db
    from src.db.models import DiagnosticSession
    
    print("Initializing DB...", flush=True)
    await init_db()
    
    async with get_session() as session:
        logger.info(f"Resetting session {session_id} to in_progress...")
        
        stmt = update(DiagnosticSession).where(
            DiagnosticSession.id == session_id
        ).values(
            status="in_progress",
            report=None,
            total_score=None,
            hard_skills_score=None,
            soft_skills_score=None,
            thinking_score=None,
            mindset_score=None
        )
        
        result = await session.execute(stmt)
        await session.commit()
        
        if result.rowcount > 0:
            logger.info(f"Session {session_id} successfully reset.")
        else:
            logger.warning(f"Session {session_id} not found.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reset_session.py <session_id>")
        sys.exit(1)
        
    session_id = int(sys.argv[1])
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(reset_session(session_id))
