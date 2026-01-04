"""
Генератор адаптивных вопросов.
"""
import logging

from src.ai.client import chat_completion
from src.core.prompts.system import get_question_prompt
from src.core.prompts.questions import get_questions, get_random_icebreaker

logger = logging.getLogger(__name__)


async def generate_question(
    role: str,
    role_name: str,
    experience: str,
    question_number: int,
    conversation_history: list[dict],
    analysis_history: list[dict],
) -> str:
    """
    Сгенерировать адаптивный вопрос на основе контекста.
    
    Args:
        role: Роль (designer/product)
        role_name: Название роли
        experience: Уровень опыта
        question_number: Номер вопроса (1-10)
        conversation_history: История вопросов и ответов
        analysis_history: История анализов
        
    Returns:
        Текст вопроса
    """
    # Для первого вопроса используем случайный из разогревочных
    if question_number == 1:
        return get_random_icebreaker(role)
    
    try:
        messages = get_question_prompt(
            role=role,
            role_name=role_name,
            experience=experience,
            question_number=question_number,
            conversation_history=conversation_history,
            analysis_history=analysis_history,
        )
        
        question = await chat_completion(
            messages=messages,
            temperature=0.8,  # Немного креативности
            max_tokens=500,
        )
        
        # Очищаем от лишних пробелов (кавычки убираем промптом)
        question = question.strip()
        logger.info(f"Generated question {question_number} for {role}: {question[:50]}...")
        
        return question
        
    except Exception as e:
        logger.error(f"Failed to generate question: {e}")
        # Fallback на захардкоженные вопросы
        questions = get_questions(role)
        fallback_idx = min(question_number - 1, len(questions) - 1)
        fallback_q = questions[fallback_idx]
        logger.info(f"Using fallback question {question_number} for {role}: {fallback_q[:50]}...")
        return fallback_q

