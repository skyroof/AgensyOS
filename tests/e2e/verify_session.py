import asyncio
from pyrogram import Client
from config import API_ID, API_HASH

async def main():
    print("Checking session...")
    app = Client("my_userbot", api_id=API_ID, api_hash=API_HASH, workdir="tests/e2e")
    async with app:
        me = await app.get_me()
        print(f"✅ VERIFIED: Logged in as {me.first_name} (@{me.username})")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ VERIFICATION FAILED: {e}")
