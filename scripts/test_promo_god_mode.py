
import asyncio
import logging
from src.db.session import init_db, get_session, close_db
from src.db.repositories import balance_repo
from src.db.repositories.subscription_repo import activate_subscription
from src.db.models import User

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()
    
    async with get_session() as session:
        # Create a dummy user if not exists
        user_id = 123456789
        # Ensure user exists in DB
        # We need to create a User object
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=user_id, username="test_user", first_name="Test")
            session.add(user)
            await session.commit()
            await session.refresh(user)
            print(f"Created user {user.id}")
        else:
            print(f"Found user {user.id}")
            
        db_user_id = user.id

        print("Testing GOD MODE...")
        
        # Simulating the code in payments.py
        try:
            # 1. Add diagnostics
            await balance_repo.add_diagnostics(
                session, db_user_id, 999, payment_id=None, commit=False
            )
            print("Added diagnostics")
            
            # 2. Activate subscription
            await activate_subscription(session, db_user_id, days=3650)
            print("Activated subscription")
            
            # 3. Commit
            await session.commit()
            print("Committed successfully")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

    await close_db()

if __name__ == "__main__":
    asyncio.run(main())
