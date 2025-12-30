import pytest
import json
from unittest.mock import AsyncMock, patch
from src.db.repositories.user_repo import get_or_create_user
from src.db.repositories.diagnostic_repo import (
    create_session,
    save_answer,
    update_session_progress,
    complete_session,
    get_session_with_answers
)
from src.ai.answer_analyzer import calculate_category_scores, calibrate_scores

# Mock Data
MOCK_ANALYSIS = {
    "scores": {
        "expertise": 8, "methodology": 7, "tools_proficiency": 9,
        "articulation": 8, "self_awareness": 7, "conflict_handling": 6,
        "depth": 8, "structure": 9, "systems_thinking": 7, "creativity": 6,
        "honesty": 9, "growth_orientation": 8
    },
    "key_insights": ["Insight 1"],
    "patterns": {"authentic": True}
}

@pytest.mark.asyncio
async def test_full_diagnostic_cycle(db_session):
    """
    Test a full diagnostic cycle from start to finish with mocked AI.
    Simulates: Start -> 3 Answers -> Completion -> Report Generation.
    """
    
    # 1. Setup User
    user = await get_or_create_user(db_session, 999, "flow_user")
    
    # 2. Start Session (Demo Mode = 3 questions)
    session = await create_session(
        db_session,
        user_id=user.id,
        role="product",
        role_name="Product Manager",
        experience="senior",
        experience_name="Senior",
        mode="demo"
    )
    assert session.status == "in_progress"
    
    # 3. Simulate answering 3 questions
    conversation_history = []
    analysis_history = []
    
    for q_num in range(1, 4):
        # User answers
        question_text = f"Question {q_num}"
        answer_text = f"Answer {q_num}"
        
        # Mock AI Analysis
        analysis = MOCK_ANALYSIS.copy()
        analysis["scores"]["expertise"] = 5 + q_num # Vary scores slightly
        
        # Save Answer
        await save_answer(
            db_session,
            diagnostic_session_id=session.id,
            question_number=q_num,
            question_text=question_text,
            answer_text=answer_text,
            analysis=analysis
        )
        
        # Update Histories
        conversation_history.append({"role": "assistant", "content": question_text})
        conversation_history.append({"role": "user", "content": answer_text})
        analysis_history.append(analysis)
        
        # Update Progress
        await update_session_progress(
            db_session,
            session_id=session.id,
            current_question=q_num + 1,
            conversation_history=conversation_history,
            analysis_history=analysis_history
        )
        
        # Verify progress update
        # Note: In a real app, we'd query the DB to check, but session object might be detached
        # Let's rely on final verification
        
    # 4. Calculate Scores
    scores = calculate_category_scores(analysis_history)
    calibrated_scores = calibrate_scores(scores, "senior")
    
    # 5. Complete Session
    report_text = "Full Report Content"
    await complete_session(
        db_session,
        session_id=session.id,
        scores=calibrated_scores,
        report=report_text,
        conversation_history=conversation_history,
        analysis_history=analysis_history
    )
    
    # 6. Verify Final State
    final_session = await get_session_with_answers(db_session, session.id)
    
    assert final_session.status == "completed"
    assert final_session.current_question == 4 # Next question would be 4
    assert len(final_session.answers) == 3
    assert final_session.total_score is not None
    assert final_session.report == report_text
    
    # Verify scores stored correctly
    assert final_session.hard_skills_score == calibrated_scores["hard_skills"]
    
    # Verify answers content
    assert final_session.answers[0].answer_text == "Answer 1"
    assert final_session.answers[2].answer_text == "Answer 3"
