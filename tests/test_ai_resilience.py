import pytest
import json
from unittest.mock import AsyncMock, patch
from src.ai.answer_analyzer import analyze_answer, DEFAULT_ANALYSIS
from src.ai.question_gen import generate_question
from src.ai.client import AIServiceError

# Mock response for analyze_answer
VALID_ANALYSIS_JSON = json.dumps({
    "scores": {
        "expertise": 8, "methodology": 7, "tools_proficiency": 9,
        "articulation": 8, "self_awareness": 7, "conflict_handling": 6,
        "depth": 8, "structure": 9, "systems_thinking": 7, "creativity": 6,
        "honesty": 9, "growth_orientation": 8
    },
    "key_insights": ["Good job"],
    "gaps": [],
    "red_flags": [],
    "hypothesis": "Strong candidate",
    "patterns": {"authentic": True}
})

@pytest.mark.asyncio
async def test_analyze_answer_success():
    """Test successful analysis with valid JSON."""
    with patch("src.ai.answer_analyzer.chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = VALID_ANALYSIS_JSON
        
        result = await analyze_answer("Q", "A", "role")
        
        assert result["scores"]["expertise"] == 8
        assert "authentic" in result["detected_patterns"]
        assert result["key_insights"] == ["Good job"]

@pytest.mark.asyncio
async def test_analyze_answer_bad_json():
    """Test graceful degradation on bad JSON."""
    with patch("src.ai.answer_analyzer.chat_completion", new_callable=AsyncMock) as mock_chat:
        # Return invalid JSON
        mock_chat.return_value = "Not a JSON string"
        
        result = await analyze_answer("Q", "A", "role")
        
        # Should return default analysis
        assert result == DEFAULT_ANALYSIS
        assert result["scores"]["expertise"] == 5

@pytest.mark.asyncio
async def test_analyze_answer_ai_error():
    """Test graceful degradation on AI service error (e.g. timeout)."""
    with patch("src.ai.answer_analyzer.chat_completion", new_callable=AsyncMock) as mock_chat:
        # Simulate exception raised by client
        mock_chat.side_effect = Exception("AI Timeout")
        
        result = await analyze_answer("Q", "A", "role")
        
        # Should return default analysis
        assert result == DEFAULT_ANALYSIS

@pytest.mark.asyncio
async def test_generate_question_success():
    """Test successful question generation."""
    with patch("src.ai.question_gen.chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = "Generated Question?"
        
        question = await generate_question(
            role="product", role_name="PM", experience="senior",
            question_number=2, conversation_history=[], analysis_history=[]
        )
        
        assert question == "Generated Question?"

@pytest.mark.asyncio
async def test_generate_question_failure():
    """Test fallback to hardcoded questions on AI failure."""
    with patch("src.ai.question_gen.chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.side_effect = Exception("Service Down")
        
        # Request question #2
        question = await generate_question(
            role="product", role_name="PM", experience="senior",
            question_number=2, conversation_history=[], analysis_history=[]
        )
        
        # Should return a fallback question (not empty)
        assert len(question) > 0
        assert "?" in question
