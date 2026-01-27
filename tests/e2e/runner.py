import asyncio
import os
import logging
from pyrogram import Client
from config import API_ID, API_HASH, BOT_USERNAME, SESSION_STRING
from scenarios.smoke import SmokeTest
from scenarios.diagnostic import DiagnosticTest
from scenarios.payment import PaymentTest
from scenarios.error import ErrorHandlingTest

import sys
import time

# --- TIME PATCH ---
import pyrogram.session.auth
import pyrogram.session.internals.msg_id

original_time = time.time

def patched_time():
    # Subtract 60 seconds to fix clock skew (32s ahead)
    return original_time() - 60

# Apply patch
time.time = patched_time
# ------------------

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("tests/e2e/runner.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

async def main():
    if not API_ID or not API_HASH:
        logger.error("❌ API_ID and API_HASH are missing in .env")
        return

    logger.info("🔌 Connecting to Telegram Userbot...")
    
    # Initialize Client
    app = Client(
        "my_userbot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True if SESSION_STRING else False,
        workdir="tests/e2e"
    )

    async with app:
        me = await app.get_me()
        logger.info(f"✅ Logged in as: {me.first_name} (@{me.username})")
        logger.info(f"🎯 Target Bot: {BOT_USERNAME}")

        # --- RUN SCENARIOS ---
        
        tests = [
            ("Smoke Test", SmokeTest(app, BOT_USERNAME)),
            ("Payment Test", PaymentTest(app, BOT_USERNAME)),
            ("Error Handling Test", ErrorHandlingTest(app, BOT_USERNAME)),
            ("Diagnostic Test", DiagnosticTest(app, BOT_USERNAME)),
        ]

        results = []

        for name, test in tests:
            logger.info(f"--- Running {name} ---")
            print(f"--- Running {name} ---")
            try:
                await test.run()
                logger.info(f"✅ {name} PASSED")
                print(f"✅ {name} PASSED")
                results.append((name, "PASSED"))
            except BaseException as e:
                logger.error(f"❌ {name} FAILED: {e}")
                print(f"❌ {name} FAILED: {e}")
                results.append((name, "FAILED"))
        
        logger.info("\n" + "="*30)
        logger.info("📊 TEST REPORT SUMMARY")
        logger.info("="*30)
        for name, status in results:
            icon = "✅" if status == "PASSED" else "❌"
            logger.info(f"{icon} {name}: {status}")
        logger.info("="*30)
        logger.info("🎉 Test Suite Completed!")

if __name__ == "__main__":
    asyncio.run(main())
