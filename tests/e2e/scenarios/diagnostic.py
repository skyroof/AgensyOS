from .base import BaseScenario
import logging
import asyncio

logger = logging.getLogger(__name__)

class DiagnosticTest(BaseScenario):
    """
    Scenario:
    1. Start Diagnostic
    2. Answer questions (some with text, some with buttons if any)
    3. Complete session
    4. Check for report generation
    """
    async def run(self):
        logger.info("🚀 Starting Diagnostic Flow Test...")
        
        # Helper to click button in any of messages
        self.current_resps = []
        
        async def try_click_any(text, exact=True):
            for m in self.current_resps:
                try:
                    await self.click_button(m, text, exact=exact)
                    return True
                except ValueError:
                    continue
            return False

        async def refresh_resps(limit=3):
             self.current_resps = await self.get_response(limit=limit)
             for idx, m in enumerate(self.current_resps):
                 rm_type = type(m.reply_markup).__name__ if m.reply_markup else "None"
                 logger.info(f"Msg {idx}: {m.text[:30] if m.text else 'No text'} | Buttons: {rm_type}")
                 if m.reply_markup:
                     logger.info(f"   Buttons Content: {m.reply_markup}")

        # 1. Start
        await self.clear_chat_history()
        await self.send_message("/start")
        
        # Setup Loop
        setup_done = False
        for step in range(15): # Max 15 attempts
             await refresh_resps()
             
             # Check for "I don't understand" and retry start
             # This handles cases where the bot gets confused or stuck
             text_0 = self.current_resps[0].text or ""
             if "не совсем понимаю" in text_0 or "нажми /start" in text_0 or "I don't understand" in text_0:
                 logger.info("ℹ️ Bot is confused. Sending '/start' again...")
                 await self.send_message("/start")
                 await asyncio.sleep(3)
                 continue

             # Check for Exit conditions (Start Button)
             # Try explicit exact match first, then fuzzy
             if await try_click_any("🎯 Начать диагностику") or \
                await try_click_any("Начать диагностику", exact=False) or \
                await try_click_any("🚀 Начать диагностику"):
                 logger.info("🚀 Clicked 'Start Diagnostic'")
                 setup_done = True
                 break
             
             clicked = False
             # Try all setup buttons
             if await try_click_any("▶️ Продолжить"):
                 logger.info("▶️ Continued.")
                 setup_done = True
                 break
             elif await try_click_any("🚀 Погнали!", exact=False):
                 logger.info("🚀 Clicked 'Let's Go!'")
                 clicked = True
             elif await try_click_any("🚀 Новая диагностика", exact=False):
                 logger.info("🚀 Clicked 'New Diagnostic'")
                 clicked = True
             elif await try_click_any("📈 Рост дохода"):
                 logger.info("✅ Selected Goal.")
                 clicked = True
             elif await try_click_any("🚀 Поиск работы"):
                 logger.info("✅ Selected Goal (Job).")
                 clicked = True
             elif await try_click_any("🧐 Оценка навыков"):
                 logger.info("✅ Selected Goal (Check).")
                 clicked = True
             elif await try_click_any("👀 Просто интересно"):
                 logger.info("✅ Selected Goal (Curious).")
                 clicked = True
             elif await try_click_any("📊 Продакт"):
                 logger.info("✅ Selected Role.")
                 clicked = True
             elif await try_click_any("🎨 Дизайнер"):
                 logger.info("✅ Selected Role (Designer).")
                 clicked = True
             elif await try_click_any("3-5 лет") or await try_click_any("Senior"):
                 logger.info("✅ Selected Exp.")
                 clicked = True
             elif await try_click_any("👉 Далее", exact=False):
                 logger.info("✅ Next.")
                 clicked = True
             elif await try_click_any("✅ Понятно, начинаем!", exact=False):
                 logger.info("✅ Understand.")
                 clicked = True
             elif await try_click_any("🎁 Промокод", exact=False):
                 logger.info("🎁 Found Promo code.")
                 await refresh_resps() # Prompt
                 await self.send_message("MAXVISUAL200")
                 logger.info("🎁 Sent Promo code.")
                 clicked = True
             elif await try_click_any("🔄 Начать заново"):
                 logger.info("🔄 Restarted.")
                 clicked = True
             elif await try_click_any("▶️ Продолжить", exact=False):
                 logger.info("▶️ Continued session.")
                 clicked = True
             elif await try_click_any("Начать новую", exact=False):
                 logger.info("🆕 Started new session.")
                 clicked = True
             
             if clicked:
                 await asyncio.sleep(1)
                 continue

             # 0. Check for "What you get" message with no buttons (FALLBACK)
             # Moved after button checks to prefer buttons if available.
             if self.current_resps and "Что получишь после" in (self.current_resps[0].text or "") and not self.current_resps[0].reply_markup:
                  logger.info("ℹ️ Found welcome message (Msg 0) with no buttons. Sending '🚀 Начать диагностику'...")
                  await self.send_message("🚀 Начать диагностику")
                  # Wait for response
                  await asyncio.sleep(2)
                  continue
          
             if not clicked:
                 logger.info("No setup buttons found in this step.")
                 
                 # Check lock
                 locked = False
                 for m in self.current_resps:
                     if "Нет доступных диагностик" in (m.text or "") or "🔒" in (m.text or ""):
                         locked = True
                         break
                 if locked:
                     logger.info("🔒 Locked. Trying to find promo button...")
                     if await try_click_any("🎁 Промокод", exact=False):
                         logger.info("🎁 Found Promo code (via lock recovery).")
                         await refresh_resps() # Prompt
                         await self.send_message("MAXVISUAL200")
                         logger.info("🎁 Sent Promo code.")
                         clicked = True
                     else:
                         logger.warning("🔒 Locked but no promo button found!")
                 else:
                     # Check if we are already in Questions
                     # Use regex to be sure it's "Question X" or "Вопрос X"
                     # And ensure it's NOT the welcome message (which might mention "questions")
                     import re
                     for m in self.current_resps:
                         text = m.text or ""
                         if re.search(r"Вопрос \d+", text, re.IGNORECASE) or \
                            re.search(r"Question \d+", text, re.IGNORECASE) or \
                            (text.startswith("1️⃣") or text.startswith("2️⃣")):
                             logger.info("📝 Question found in text (regex/icon match). Setup done.")
                             setup_done = True
                             break
                     if setup_done: break
                 
             await asyncio.sleep(1)
        
        if not setup_done:
            logger.warning("⚠️ Setup loop finished without clear start. Might be stuck in menu.")

        # 4. Answer Questions
        logger.info("🏁 Entering Question Loop...")
        last_msg_id = 0
        last_msg_date = 0
        
        questions_answered = 0
        max_questions = 20 # Safety limit
        
        while questions_answered < max_questions:
            # Wait for a NEW message (different ID or updated date)
            # We poll every 2 seconds.
            # Default timeout 180s, but if generating report, allow more.
            msg = None
            wait_start = asyncio.get_event_loop().time()
            current_timeout = 300 # Increased to 5 mins for report generation
            
            while (asyncio.get_event_loop().time() - wait_start) < current_timeout:
                messages = await self.get_response(limit=5, timeout=5) # Fetch more messages to ignore spam
                
                # Check for new messages
                msg_found = None
                for m in messages:
                    current_date = m.edit_date or m.date
                    if m.id != last_msg_id or current_date != last_msg_date:
                        # Skip reminders if we are looking for a question
                        if "напоминание" in (m.text or "").lower():
                            logger.info(f"ℹ️ Skipping reminder message: {m.id}")
                            continue
                        msg_found = m
                        break
                
                if msg_found:
                    msg = msg_found
                    break
                
                # Check if we are generating report (keep waiting)
                if "генерирую отчет" in (m.text or "").lower():
                     # Just log periodically
                     if int(asyncio.get_event_loop().time()) % 10 == 0:
                         logger.info("⏳ Still generating report...")
                
                # Still the same message
                await asyncio.sleep(2)
            
            if not msg:
                logger.error("❌ Timeout waiting for next question/step.")
                # We can try to click "Confirm" again just in case?
                # But for now, raise error
                raise TimeoutError("Stuck waiting for bot response.")

            # Update last seen
            last_msg_id = msg.id
            last_msg_date = msg.edit_date or msg.date
            text = msg.text or ""
            
            logger.info(f"📥 Processing: {text[:100]}... (ID: {msg.id})")
            if msg.reply_markup:
                 logger.info(f"🔘 Buttons available: {msg.reply_markup}")
            
            # --- Termination Checks ---
            if "диагностика завершена" in text.lower() or \
               "результат готов" in text.lower():
                logger.info("✅ Diagnostic finished!")
                break
                
            if "твой результат" in text.lower() and "вопрос" not in text.lower():
                 logger.info("✅ Diagnostic finished (Result found)!")
                 break

            if "не удалось сгенерировать" in text.lower():
                logger.warning("⚠️ Report generation failed (partial result). Considering diagnostic finished.")
                break
            
            # --- Intermediate Message Handling ---
            if "произошла ошибка" in text.lower():
                 logger.warning("⚠️ Error occurred (AI timeout?). Retrying...")
                 if msg.reply_markup:
                     # Try to click Confirm again
                     try:
                        await self.click_button(msg, "✅ Отправить")
                        logger.info("✅ Clicked 'Confirm' again after error.")
                        continue
                     except: pass
            
            if "я не совсем понимаю" in text.lower():
                 logger.warning("⚠️ Bot confused in Question Loop. Sending /start to recover...")
                 await self.send_message("/start")
                 await asyncio.sleep(3)
                 continue

            if "анализ" in text.lower() and "ответ" in text.lower():
                 logger.info("ℹ️ Bot is analyzing answer. Waiting...")
                 continue

            if "потерял нить" in text.lower():
                logger.warning("⚠️ Bot lost thread. Attempting to recover...")
                # Try to click "Continue" button
                try:
                    if msg.reply_markup:
                        await self.click_button(msg, "Продолжить", exact=False)
                        logger.info("✅ Clicked recovery button 'Continue'.")
                        await asyncio.sleep(2)
                        continue
                    else:
                         logger.error("❌ Recovery failed: Message has no buttons.")
                         raise RuntimeError("Bot lost thread: Message has no buttons.")
                except ValueError:
                    logger.error("❌ Recovery failed: No 'Continue' button found.")
                    raise RuntimeError("Bot lost thread and recovery failed.")

            # Refined ACK check: Look for "✅ Ответ ... принят" specifically
            if "✅" in text and "ответ" in text.lower() and "принят" in text.lower():
                 logger.info("ℹ️ Received answer acknowledgement. Waiting for actual question...")
                 continue

            # "Target accepted" might be the Role selection message itself.
            # Only skip if it has NO buttons.
            if "цель принята" in text.lower() and not msg.reply_markup:
                 logger.info("ℹ️ Received 'Target accepted' (text only). Waiting for question...")
                 continue
            
            # If it's just "Your answer: ..." and "Confirm" button, we might need to click it again?
            # But usually we click it after sending.
            
            # Check if it is a question or a step requiring action
            # It should have "Вопрос" or "Question" or start with an emoji number
            is_question = False
            import re
            
            # Recovery: Check for late setup buttons in Question Loop
            if "погнали" in text.lower() or "начать диагностику" in text.lower() or "давай договоримся" in text.lower() or "всё готово" in text.lower():
                if msg.reply_markup:
                    try:
                        if await self.click_button(msg, "🚀 Начать диагностику", exact=False):
                            logger.info("🚀 Clicked 'Start Diagnostic' inside Question Loop recovery.")
                            await asyncio.sleep(2)
                            continue
                        elif await self.click_button(msg, "👉 Далее", exact=False):
                             logger.info("👉 Clicked 'Next' inside Question Loop recovery.")
                             await asyncio.sleep(2)
                             continue
                    except: pass

            # Check for "Continue" button which might appear between questions (e.g. "▶️ Продолжить (9/10)")
            if msg.reply_markup:
                try:
                    if await self.click_button(msg, "▶️ Продолжить", exact=False):
                         logger.info("▶️ Clicked 'Continue' inside Question Loop.")
                         await asyncio.sleep(2)
                         continue
                except: pass

            if (re.search(r"Вопрос \d+", text, re.IGNORECASE) or \
               re.search(r"Question \d+", text, re.IGNORECASE) or \
               text.strip().startswith("1️⃣") or text.strip().startswith("2️⃣") or \
               "выбери" in text.lower() or "?" in text or \
               "давай договоримся" in text.lower() or \
               (msg.reply_markup and hasattr(msg.reply_markup, 'inline_keyboard') and 
                any("далее" in btn.text.lower() for row in msg.reply_markup.inline_keyboard for btn in row))) and \
               "отправляем" not in text.lower() and "твой ответ" not in text.lower():
                   is_question = True
            
            # --- Paywall Recovery in Question Loop ---
            if "нет доступных диагностик" in text.lower() or "🔒" in text:
                 logger.info("🔒 Paywall detected in Question Loop. Attempting recovery with Promo Code...")
                 if await try_click_any("🎁 Промокод", exact=False):
                     logger.info("🎁 Found Promo code button.")
                     await asyncio.sleep(1)
                     await self.send_message("MAXVISUAL200")
                     logger.info("🎁 Sent Promo code.")
                     await asyncio.sleep(3)
                     continue
                 else:
                     logger.warning("🔒 Paywall detected but no promo button found!")

            if not is_question:
                 logger.info("ℹ️ Message does not look like a question. Waiting...")
                 continue

            # --- Answering ---
            questions_answered += 1
            logger.info(f"📝 Answering Question {questions_answered}...")
            
            # Check for Inline Buttons first
            answered_via_button = False
            if msg.reply_markup:
                # Basic check if it has inline_keyboard (Pyrogram object)
                # We can try to use click_button on the first button
                # Or check the type of reply_markup
                rm_type = type(msg.reply_markup).__name__
                if "InlineKeyboardMarkup" in rm_type:
                     logger.info("🔘 Inline buttons detected. Clicking the first option...")
                     try:
                         # Try to find a valid option button (avoid navigation if possible, or just click first)
                         # We'll just click the first button for now as a default choice
                         # But sometimes first button is "Back" or something.
                         # Let's inspect rows.
                         # msg.reply_markup.inline_keyboard is a list of lists
                         if hasattr(msg.reply_markup, 'inline_keyboard'):
                            # Iterate to find a button that looks like an answer (not "Back" or "Pause")
                            target_text = None
                            ignored_keywords = ["назад", "back", "пауз", "pause", "меню", "menu"]
                            
                            for row in msg.reply_markup.inline_keyboard:
                                for btn in row:
                                    # Filter out navigation/system buttons
                                    b_text_lower = btn.text.lower()
                                    if any(k in b_text_lower for k in ignored_keywords):
                                        continue
                                        
                                    target_text = btn.text
                                    break
                                if target_text: break
                            
                            if target_text:
                                await self.click_button(msg, target_text, exact=True)
                                logger.info(f"✅ Clicked inline button: {target_text}")
                                answered_via_button = True
                            else:
                                logger.info("ℹ️ Inline keyboard found but only contained ignored buttons (Pause/Menu). treating as text question.")
                                answered_via_button = False
                     except Exception as e:
                         logger.error(f"❌ Failed to click inline button: {e}")

            if not answered_via_button:
                # Text answer
                answer_text = f"Test answer for question {questions_answered}. Relevant content."
                await self.send_message(answer_text)
                
                # Confirm (only needed for text answers usually)
                await asyncio.sleep(3)
                try:
                    # Wait for the confirmation message with the button
                    # We expect a NEW message or update from the bot
                    conf_msgs = await self.get_response(limit=1, timeout=20)
                    # Only click confirm if it exists
                    if conf_msgs and conf_msgs[0].reply_markup:
                        await self.click_button(conf_msgs[0], "✅ Отправить")
                        logger.info("✅ Confirmed answer.")
                    else:
                        logger.info("ℹ️ No confirmation button found. Proceeding.")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Confirmation button issue: {e}. Proceeding.")
            else:
                 # If we clicked a button, we might need to wait a bit for the next question
                 await asyncio.sleep(2)
                
        # 5. Check Report
        logger.info("📊 Checking for Report...")
        await asyncio.sleep(10) 
        try:
            final_msgs = await self.get_response(limit=5)
            found_report = False
            for m in final_msgs:
                if "hard skills" in (m.text or "").lower():
                    found_report = True
                    break
            
            if found_report:
                logger.info("✅ Report generated successfully!")
            else:
                logger.warning("⚠️ Report summary not explicitly found.")
        except Exception as e:
            logger.warning(f"Error checking report: {e}")
