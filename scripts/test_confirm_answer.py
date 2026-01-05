import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import CallbackQuery, Message, User, Chat
from aiogram.fsm.context import FSMContext
from aiogram import Bot

# Mock dependencies
import sys
import os
sys.path.append(os.getcwd())

# Mock logging to see errors
logging.basicConfig(level=logging.ERROR)

async def test_confirm_answer_crash():
    print("🚀 Starting reproduction test...")
    
    # 1. Mock objects
    bot = AsyncMock(spec=Bot)
    
    # Mock message
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 12345
    message.edit_text = AsyncMock()
    message.answer = AsyncMock()
    
    # Mock user
    user = MagicMock(spec=User)
    user.id = 12345
    
    # Mock callback
    callback = AsyncMock(spec=CallbackQuery)
    callback.message = message
    callback.from_user = user
    callback.answer = AsyncMock()
    
    # Mock state
    state = AsyncMock(spec=FSMContext)
    
    # Scenario 1: Normal data
    print("\n🧪 Test Case 1: Normal data")
    state.get_data.return_value = {
        "current_question": 1,
        "draft_answer": "Test answer",
        "question_start_time": 1000.0,
        "role": "founder",
        "total_questions": 10
    }
    
    # Mock external functions
    import src.bot.handlers.diagnostic as diagnostic_module
    diagnostic_module.analyze_answer = AsyncMock(return_value={"scores": {}, "key_insights": []})
    diagnostic_module.generate_question = AsyncMock(return_value="Next question?")
    diagnostic_module.get_session = MagicMock()
    diagnostic_module.save_answer = AsyncMock()
    diagnostic_module.update_session_progress = AsyncMock()
    diagnostic_module.start_reminder = AsyncMock()
    diagnostic_module.cancel_reminder = AsyncMock()
    
    # Mock asyncio.sleep to avoid waiting
    # We patch the module's sleep function directly, but we must be careful not to break other asyncio functions
    # Since asyncio is imported as 'import asyncio', we can patch it on the module
    # But patching 'asyncio.sleep' globally is safer if we just want to skip sleep
    # However, we need to ensure we don't break 'asyncio.create_task' etc.
    
    # Better approach: Patch asyncio.sleep in the module dict if possible, or just accept the wait.
    # But since the previous run timed out (maybe), let's try to patch ONLY sleep.
    # diagnostic_module.asyncio.sleep = AsyncMock() # This patches the real asyncio.sleep!
    
    # Instead of patching, let's just mock the sleep call inside the handler if we can.
    # But we can't easily access the imported name if it's 'import asyncio'.
    # Let's try to patch it via sys.modules or just set it on the module object IF it's bound there.
    
    # Actually, the error in previous run "catching classes..." was because I replaced the whole asyncio module.
    # If I just do:
    # diagnostic_module.asyncio.sleep = AsyncMock()
    # It might work, but it affects the test runner itself (asyncio.run uses sleep?).
    # NO, asyncio.run doesn't use sleep usually.
    
    # Let's try patching diagnostic_module.asyncio.sleep
    # We must capture the original sleep function, not just the module, 
    # because we are modifying the module's attribute.
    original_sleep = diagnostic_module.asyncio.sleep
    
    async def fast_sleep(delay):
        # Allow other tasks to run, avoiding infinite loop starvation
        # Use a very small delay to simulate yielding
        if delay > 0:
            await original_sleep(0.001)
        else:
            await original_sleep(0)
        
    diagnostic_module.asyncio.sleep = AsyncMock(side_effect=fast_sleep)
    
    # Import handler (must be done after path setup)
    try:
        from src.bot.handlers.diagnostic import confirm_answer
        from src.bot.states import DiagnosticStates
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return

    # Run handler
    try:
        await confirm_answer(callback, state, bot)
        print("✅ Test Case 1 passed (no crash)")
    except Exception as e:
        print(f"❌ Test Case 1 failed: {e}")

    # Scenario 2: Missing draft_answer (should return empty string)
    print("\n🧪 Test Case 2: Missing draft_answer")
    state.get_data.return_value = {
        "current_question": 1,
        # No draft_answer
        "question_start_time": 1000.0,
        "role": "founder"
    }
    
    # Reset mocks
    callback.answer.reset_mock()
    state.set_state.reset_mock()
    
    try:
        await confirm_answer(callback, state, bot)
        # Should trigger "Сессия истекла" because key is missing
        args = str(callback.answer.call_args)
        if callback.answer.call_args and "Сессия истекла" in args:
            print("✅ Test Case 2 passed (handled missing session key)")
        else:
             print(f"⚠️ Test Case 2 warning: unexpected response: {args}")
    except Exception as e:
        print(f"❌ Test Case 2 failed: {e}")

    # Scenario 3: Final Question (Finish)
    print("\n🧪 Test Case 3: Final Question (Finish)")
    state.get_data.return_value = {
        "current_question": 10,
        "total_questions": 10,
        "draft_answer": "Final answer",
        "question_start_time": 1000.0,
        "role": "founder",
        "role_name": "Founder", # Added missing field
        "experience_name": "Senior (5+ years)", # Added missing field
        "answers": {},
        "scores": {},
        "diagnostic_mode": "full",
        "db_session_id": 123,
        "user_name": "TestUser"
    }
    
    # Mock result generation functions
    diagnostic_module.generate_summary_card = MagicMock(return_value="Summary Card")
    diagnostic_module.generate_pdp_plan = MagicMock()
    diagnostic_module.save_diagnostic_result = AsyncMock()
    diagnostic_module.get_result_summary_keyboard = MagicMock()
    diagnostic_module.generate_detailed_report = AsyncMock(return_value="Detailed Report")
    # Mock generate_basic_report if it exists, otherwise just ignore (it might be local function)
    if hasattr(diagnostic_module, 'generate_basic_report'):
        diagnostic_module.generate_basic_report = AsyncMock(return_value="Basic Report")
    
    diagnostic_module.calculate_category_scores = MagicMock(return_value={"total": 100, "raw_averages": {}})
    diagnostic_module.calibrate_scores = MagicMock(return_value={"total": 100, "raw_averages": {}})
    diagnostic_module.build_profile = MagicMock()
    diagnostic_module.build_profile.return_value.strengths = []
    diagnostic_module.build_pdp = MagicMock()
    diagnostic_module.format_profile_text = MagicMock(return_value="Profile Text")
    diagnostic_module.format_pdp_text = MagicMock(return_value="PDP Text")
    diagnostic_module.complete_session = AsyncMock()
    
    # Mock database session context manager
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_db
    mock_session_ctx.__aexit__.return_value = None
    diagnostic_module.get_session = MagicMock(return_value=mock_session_ctx)
    
    # Mock dynamic imports
    sys.modules['src.db.repositories.reminder_repo'] = MagicMock()
    
    # Reset mocks
    message.answer.reset_mock()
    message.edit_text.reset_mock()
    
    try:
        await confirm_answer(callback, state, bot)
        with open("test_output.txt", "w", encoding="utf-8") as f:
            f.write("✅ Test Case 3 passed (no crash on finish)\n")
            f.write(f"   Messages sent (answer): {message.answer.call_count}\n")
            f.write(f"   Messages edited: {message.edit_text.call_count}\n")
        print("✅ Test Case 3 passed (no crash on finish)")
    except Exception as e:
        with open("test_output.txt", "w", encoding="utf-8") as f:
            f.write(f"❌ Test Case 3 failed: {e}\n")
        print(f"❌ Test Case 3 failed: {e}")
        import traceback
        traceback.print_exc()

    # Scenario 4: None draft_answer (Explicit None)
    print("\n🧪 Test Case 4: Explicit None draft_answer")
    state.get_data.return_value = {
        "current_question": 1,
        "draft_answer": None,
        "question_start_time": 1000.0,
        "role": "founder"
    }
    
    try:
        await confirm_answer(callback, state, bot)
        print("✅ Test Case 4 passed")
    except Exception as e:
        print(f"❌ Test Case 4 failed: {e}")

    # Scenario 5: answer_stats is not a list
    print("\n🧪 Test Case 5: answer_stats is broken")
    state.get_data.return_value = {
        "current_question": 1,
        "draft_answer": "Answer",
        "answer_stats": "BROKEN_STRING", # Not a list
        "role": "founder"
    }
    
    try:
        await confirm_answer(callback, state, bot)
        print("✅ Test Case 5 passed")
    except Exception as e:
        print(f"❌ Test Case 5 failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_confirm_answer_crash())
