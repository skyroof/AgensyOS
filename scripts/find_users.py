import asyncio
import sys
import os
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def find_users(usernames: list[str]):
    print("Importing...", flush=True)
    from dotenv import load_dotenv
    load_dotenv()
    
    from src.db.session import get_session, init_db
    from src.db.models import User, DiagnosticSession
    
    await init_db()
    
    async with get_session() as session:
        # Normalize usernames (remove @)
        target_usernames = [u.lstrip('@') for u in usernames]
        print(f"Searching for users: {target_usernames}")
        
        stmt = select(User).options(
            selectinload(User.sessions).selectinload(DiagnosticSession.answers)
        ).where(
            User.username.in_(target_usernames)
        )
        
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        found_usernames = set()
        
        for user in users:
            found_usernames.add(user.username)
            print(f"\nUser: @{user.username} (ID: {user.id}, TG: {user.telegram_id})")
            if not user.sessions:
                print("  No sessions found.")
            
            for s in user.sessions:
                ans_count = len(s.answers) if s.answers else 0
                print(f"  Session {s.id}: status={s.status}, answers={ans_count}, report={'YES' if s.report else 'NO'}")
                if s.report:
                     print(f"    Report length: {len(s.report)}")

        # Check who was not found
        for u in target_usernames:
            if u not in found_usernames:
                print(f"\nUser @{u} NOT FOUND in database.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python find_users.py username1 username2 ...")
        sys.exit(1)
    
    usernames = sys.argv[1:]
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(find_users(usernames))
