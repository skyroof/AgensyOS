import asyncio
from pyrogram import Client
from typing import Optional, List
from pyrogram.types import Message
import logging

logger = logging.getLogger(__name__)

class BaseScenario:
    def __init__(self, client: Client, bot_username: str):
        self.app = client
        self.bot = bot_username
        self.chat_id = None  # Will be resolved

    async def run(self):
        """Execute the test scenario."""
        raise NotImplementedError

    async def clear_chat_history(self):
        """Clear chat history with the bot."""
        logger.info("🧹 Clearing chat history...")
        try:
             # resolve peer
             peer = await self.app.resolve_peer(self.bot)
             # delete history
             from pyrogram.raw.functions.messages import DeleteHistory
             await self.app.invoke(
                 DeleteHistory(
                     peer=peer,
                     max_id=0,
                     just_clear=False,
                     revoke=True
                 )
             )
             await asyncio.sleep(1) # Wait for sync
        except Exception as e:
            logger.warning(f"⚠️ Failed to clear history: {e}")

    async def send_message(self, text: str) -> Message:
        """Send a message to the bot."""
        logger.info(f"📤 Sending: {text}")
        return await self.app.send_message(self.bot, text)

    async def get_response(self, limit: int = 1, timeout: int = 30) -> List[Message]:
        """
        Wait for a response from the bot.
        Polls until a message from the bot (not self) appears or timeout occurs.
        """
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            messages = []
            async for message in self.app.get_chat_history(self.bot, limit=limit):
                messages.append(message)
            
            if not messages:
                await asyncio.sleep(1)
                continue
            
            # If the latest message is from us, the bot hasn't replied yet
            if messages[0].from_user.is_self:
                await asyncio.sleep(1)
                continue
                
            logger.info(f"📥 Received: {messages[0].text[:50]}...")
            return messages
            
        raise TimeoutError("Bot did not respond in time.")

    async def click_button(self, message: Message, button_text: str, exact: bool = True):
        """Click a button (Inline or Reply) by text."""
        if not message.reply_markup:
            raise ValueError("Message has no buttons.")

        # 1. Check Inline Keyboard
        if hasattr(message.reply_markup, "inline_keyboard"):
            for row in message.reply_markup.inline_keyboard:
                for btn in row:
                    if (exact and btn.text == button_text) or (not exact and button_text in btn.text):
                        logger.info(f"point_up Clicked Inline button: {btn.text} (match: {button_text})")
                        try:
                            # Wrap in asyncio.wait_for to ensure timeout is respected
                            await asyncio.wait_for(
                                self.app.request_callback_answer(
                                    chat_id=message.chat.id,
                                    message_id=message.id,
                                    callback_data=btn.callback_data,
                                    timeout=20
                                ),
                                timeout=25 # Slightly larger than internal timeout
                            )
                        except Exception as e:
                            logger.warning(f"⚠️ Callback answer failed (ignored): {e}")
                        return

        # 2. Check Reply Keyboard
        if hasattr(message.reply_markup, "keyboard"):
            for row in message.reply_markup.keyboard:
                for btn in row:
                    # btn can be KeyboardButton (obj) or str (in older pyrogram? No, usually KeyboardButton)
                    # Pyrogram KeyboardButton has .text
                    text = btn.text if hasattr(btn, "text") else str(btn)
                    
                    if (exact and text == button_text) or (not exact and button_text in text):
                        logger.info(f"point_up Clicked Reply button: {text} (match: {button_text})")
                        await self.send_message(text)
                        return
        
        raise ValueError(f"Button '{button_text}' not found.")
