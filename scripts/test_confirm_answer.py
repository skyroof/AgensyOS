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

    # Scenario 3: None draft_answer (Explicit None)
    print("\n🧪 Test Case 3: Explicit None draft_answer")
    state.get_data.return_value = {
        "current_question": 1,
        "draft_answer": None,
        "question_start_time": 1000.0,
        "role": "founder"
    }
    
    try:
        await confirm_answer(callback, state, bot)
        print("✅ Test Case 3 passed")
    except Exception as e:
        print(f"❌ Test Case 3 failed: {e}")

    # Scenario 4: answer_stats is not a list
    print("\n🧪 Test Case 4: answer_stats is broken")
    state.get_data.return_value = {
        "current_question": 1,
        "draft_answer": "Answer",
        "answer_stats": "BROKEN_STRING", # Not a list
        "role": "founder"
    }
    
    try:
        await confirm_answer(callback, state, bot)
        print("✅ Test Case 4 passed")
    except Exception as e:
        print(f"❌ Test Case 4 failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_confirm_answer_crash())
