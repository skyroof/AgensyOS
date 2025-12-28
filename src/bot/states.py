"""
FSM состояния для диагностики.
"""
from aiogram.fsm.state import State, StatesGroup


class DiagnosticStates(StatesGroup):
    """Состояния процесса диагностики."""
    
    # Выбор параметров
    choosing_role = State()
    choosing_experience = State()
    
    # Подтверждение старта
    ready_to_start = State()
    
    # Процесс диагностики (10 вопросов)
    answering = State()
    
    # Подтверждение ответа перед отправкой
    confirming_answer = State()
    
    # Завершение
    finished = State()

