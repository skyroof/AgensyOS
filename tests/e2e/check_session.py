import asyncio
import time
from pyrogram import Client
from config import API_ID, API_HASH

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

async def main():
    print("Attempting connection...")
    app = Client("my_userbot", api_id=API_ID, api_hash=API_HASH, workdir="tests/e2e")
    try:
        await app.start()
        print("✅ Started successfully!")
        me = await app.get_me()
        print(f"✅ Logged in as {me.first_name}")
        await app.stop()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    for i in range(3):
        print(f"\n--- Attempt {i+1} ---")
        try:
            asyncio.run(main())
        except Exception as e:
            print(f"Loop Error: {e}")
        time.sleep(2)
