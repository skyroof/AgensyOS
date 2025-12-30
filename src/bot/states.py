"""
FSM состояния для диагностики.
"""
from aiogram.fsm.state import State, StatesGroup


class DiagnosticStates(StatesGroup):
    """Состояния процесса диагностики."""
    
    # Micro-commitment (Step 0)
    choosing_goal = State()
    
    # Выбор параметров
    choosing_role = State()
    choosing_experience = State()
    
    # Онбординг с правилами
    onboarding = State()
    
    # Подтверждение старта
    ready_to_start = State()
    
    # Запуск диагностики (анимация и генерация)
    starting = State()
    
    # Восстановление незавершённой сессии
    session_recovery = State()
    
    # Процесс диагностики (10 вопросов)
    answering = State()
    
    # Подтверждение ответа перед отправкой
    confirming_answer = State()
    
    # Обработка ответа (защита от double click)
    processing_answer = State()
    
    # Генерация отчёта (защита от race condition)
    generating_report = State()
    
    # Пауза сессии
    paused = State()
    
    # Сбор feedback
    feedback_rating = State()
    feedback_comment = State()
    
    # Завершение
    finished = State()

