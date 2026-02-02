import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

async def test_send():
    token = os.getenv("BOT_TOKEN")
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    if not token or not admin_id:
        print("❌ BOT_TOKEN or ADMIN_TELEGRAM_ID not found")
        return
    
    bot = Bot(token=token)
    try:
        print(f"📤 Sending test message to {admin_id}...")
        await bot.send_message(admin_id, "🤖 **Test message from deployment script**\nIf you see this, the bot can send messages.")
        print("✅ Message sent!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_send())
