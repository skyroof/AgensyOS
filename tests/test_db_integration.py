import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.repositories.user_repo import get_or_create_user, get_user_by_telegram_id
from src.db.repositories.diagnostic_repo import (
    create_session,
    get_session_by_id,
    update_session_progress,
    save_answer,
    complete_session,
    get_session_with_answers,
    get_active_session
)

@pytest.mark.asyncio
async def test_user_lifecycle(db_session, db_engine):
    # 1. Create User
    telegram_id = 12345
    username = "test_user"
    
    user = await get_or_create_user(
        db_session, 
        telegram_id=telegram_id, 
        username=username, 
        first_name="Test", 
        last_name="User"
    )
    
    assert user.id is not None
    assert user.telegram_id == telegram_id
    assert user.username == username
    
    # 2. Update User (same ID)
    updated_user = await get_or_create_user(
        db_session,
        telegram_id=telegram_id,
        username="new_username"
    )
    
    assert updated_user.id == user.id
    assert updated_user.username == "new_username"
    
    # 3. Verify persistence in a fresh session
    async with AsyncSession(db_engine) as session2:
        fetched_user = await get_user_by_telegram_id(session2, telegram_id)
        assert fetched_user is not None
        assert fetched_user.username == "new_username"

@pytest.mark.asyncio
async def test_diagnostic_flow(db_session, db_engine):
    # Setup User
    user = await get_or_create_user(db_session, 555, "diag_user")
    
    # 1. Start Session
    diag_session = await create_session(
        db_session,
        user_id=user.id,
        role="pm",
        role_name="Product Manager",
        experience="senior",
        experience_name="Senior",
        mode="demo"
    )
    
    assert diag_session.id is not None
    assert diag_session.status == "in_progress"
    
    # Verify active session retrieval
    active = await get_active_session(db_session, user.id)
    assert active is not None
    assert active.id == diag_session.id
    
    # 2. Save Answer
    answer_text = "My answer"
    analysis_data = {"scores": {"depth": 8}}
    
    answer = await save_answer(
        db_session,
        diagnostic_session_id=diag_session.id,
        question_number=1,
        question_text="Q1",
        answer_text=answer_text,
        analysis=analysis_data
    )
    
    assert answer.id is not None
    
    # 3. Update Progress
    await update_session_progress(
        db_session,
        session_id=diag_session.id,
        current_question=2,
        conversation_history=[{"role": "user", "content": "hi"}],
        analysis_history=[analysis_data]
    )
    
    # Check updates in fresh session
    async with AsyncSession(db_engine) as session2:
        s = await get_session_by_id(session2, diag_session.id)
        assert s.current_question == 2
        assert len(s.conversation_history) == 1
        
    # 4. Complete Session
    final_scores = {
        "total": 85,
        "hard_skills": 80,
        "soft_skills": 90,
        "thinking": 85,
        "mindset": 85
    }
    await complete_session(
        db_session,
        session_id=diag_session.id,
        scores=final_scores,
        report="Great job!",
        conversation_history=[],
        analysis_history=[]
    )
    
    # Verify completion
    async with AsyncSession(db_engine) as session3:
        s = await get_session_with_answers(session3, diag_session.id)
        assert s.status == "completed"
        assert s.total_score == 85
        assert len(s.answers) == 1
        assert s.answers[0].answer_text == answer_text
