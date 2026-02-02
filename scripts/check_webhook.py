import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

async def check_webhook():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN not found")
        return
    
    bot = Bot(token=token)
    try:
        webhook_info = await bot.get_webhook_info()
        print(f"🌐 Webhook Info: {webhook_info}")
        
        if webhook_info.url:
            print(f"⚠️ Webhook is active: {webhook_info.url}")
            print("🔄 Deleting webhook...")
            await bot.delete_webhook()
            print("✅ Webhook deleted!")
        else:
            print("✅ Webhook is not set (Polling mode)")
            
        me = await bot.get_me()
        print(f"🤖 Bot: @{me.username} ({me.id})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    print("🚀 Starting check_webhook script...")
    asyncio.run(check_webhook())
    print("🏁 Script finished.")
