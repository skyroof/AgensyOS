import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from dotenv import load_dotenv

load_dotenv()

async def on_update(update: Update):
    print(f"📥 Received update: {update}")

async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN not found")
        return
    
    bot = Bot(token=token)
    dp = Dispatcher()
    
    @dp.update()
    async def handle_any(update: Update):
        print(f"📥 Update: {update.update_id}")
        if update.message:
            print(f"   Message: {update.message.text} from {update.message.from_user.id}")
        return True

    print("🚀 Starting local poll...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
