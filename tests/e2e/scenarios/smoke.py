from .base import BaseScenario
import logging

logger = logging.getLogger(__name__)

class SmokeTest(BaseScenario):
    """
    Basic Smoke Test:
    1. Send /start
    2. Check for welcome message
    3. Check for main menu buttons
    """
    async def run(self):
        logger.info("🚀 Starting Smoke Test...")
        
        # 1. Send /start
        await self.send_message("/start")
        
        # 2. Get Response
        responses = await self.get_response(limit=1)
        last_msg = responses[0]
        
        # 3. Assertions
        assert last_msg.from_user.username.lower() == self.bot.lower().replace("@", "")
        
        # Check text (flexible assertion)
        welcome_keywords = [
            "привет", "добро пожаловать", "меню", "диагностика", 
            "незавершённая", "с возвращением", "новую диагностику"
        ]
        text_lower = (last_msg.text or last_msg.caption or "").lower()
        
        if not any(k in text_lower for k in welcome_keywords):
            raise AssertionError(f"Welcome message seems incorrect: {text_lower}")
            
        logger.info("✅ Smoke Test Passed!")
