"""AI модуль для диагностики."""
from src.ai.client import chat_completion, get_ai_client, AIServiceError
from src.ai.question_gen import generate_question
from src.ai.answer_analyzer import analyze_answer, calculate_category_scores
from src.ai.report_gen import generate_detailed_report, split_message

__all__ = [
    "chat_completion",
    "get_ai_client",
    "AIServiceError",
    "generate_question",
    "analyze_answer",
    "calculate_category_scores",
    "generate_detailed_report",
    "split_message",
]

