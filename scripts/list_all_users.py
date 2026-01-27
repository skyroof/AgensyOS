
import asyncio
import sys
import os
from sqlalchemy import select

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def list_all_users():
    from src.db.session import get_session, init_db
    from src.db.models import User
    
    await init_db()
    
    async with get_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        print(f"Total users: {len(users)}")
        for user in users:
            print(f"ID: {user.id}, TG: {user.telegram_id}, Username: @{user.username}, Name: {user.first_name}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(list_all_users())
