import asyncio
import logging
from src.db.session import init_db
from src.db.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Forcing database schema creation...")
    try:
        # This will create all tables defined in Base.metadata if they don't exist
        await init_db()
        logger.info("Database schema check/creation completed.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
