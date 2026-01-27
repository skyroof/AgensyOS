import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram API Credentials (Get from https://my.telegram.org/apps)
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

# The bot username we are testing
BOT_USERNAME = os.getenv("BOT_USERNAME", "VISUALMAXAGENCY_BOT")

# Session string (will be generated on first login)
SESSION_STRING = os.getenv("USERBOT_SESSION_STRING")

# Test configuration
TIMEOUT = 15  # Seconds to wait for bot response
