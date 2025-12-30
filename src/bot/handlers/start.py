"""
Обработчик команды /start и выбора параметров.
"""
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from src.bot.states import DiagnosticStates
from src.bot.keyboards.inline import (
    get_role_keyboard,
    get_experience_keyboard,
    get_start_diagnostic_keyboard,
    get_onboarding_keyboard,
    get_onboarding_step2_keyboard,
    get_returning_user_keyboard,
    get_session_recovery_keyboard,
    get_back_to_menu_keyboard,
    get_start_with_history_keyboard,
)
from src.db import get_session
from src.db.repositories import (
    get_or_create_user,
    create_session as create_db_session,
    get_active_session,
    get_user_sessions,
    get_completed_sessions,
    get_user_stats,
)

router = Router(name="start")
logger = logging.getLogger(__name__)

# TTL для незавершённых сессий (24 часа)
SESSION_TTL_HOURS = 24

# Базовый текст приветствия (без персонализации)
WELCOME_TEXT = """
🎯 <b>Deep Diagnostic Bot</b>

Я помогу оценить твой уровень как специалиста за <b>10 глубоких вопросов</b>.

<b>Что я оценю:</b>
• Hard Skills — технические навыки
• Soft Skills — коммуникация и лидерство  
• Thinking — системное мышление
• Mindset — ценности и зрелость

<b>Выбери свою роль:</b>
"""


def get_welcome_text(first_name: str) -> str:
    """Персонализированное приветствие."""
    return f"""
🎯 <b>Deep Diagnostic Bot</b>

Привет, <b>{first_name}</b>! 👋

Я помогу оценить твой уровень как специалиста за <b>10 глубоких вопросов</b>.

<b>Что я оценю:</b>
• Hard Skills — технические навыки
• Soft Skills — коммуникация и лидерство  
• Thinking — системное мышление
• Mindset — ценности и зрелость

<b>Важно:</b> Отвечай развёрнуто и честно. Чем подробнее ответы — тем точнее диагностика.

⏱️ Время: ~15-20 минут
"""


# Контекстные подсказки по уровню опыта
EXPERIENCE_TIPS = {
    "junior": "💡 <i>Не переживай, если опыта мало — важна честность и рефлексия!</i>",
    "middle": "💡 <i>Расскажи о реальных кейсах и что ты из них вынес.</i>",
    "senior": "💡 <i>Ожидаем глубоких кейсов с метриками и системным подходом.</i>",
    "lead": "💡 <i>Интересны стратегические решения и влияние на команду/продукт.</i>",
}

# Темы вопросов для preview
QUESTION_TOPICS = {
    "designer": "проекты, процессы, пользователи, метрики, рост",
    "product": "стратегия, приоритизация, метрики, команда, рост",
}


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start."""
    # Сбрасываем состояние
    await state.clear()
    
    db_user_id = None
    active_session = None
    user_first_name = message.from_user.first_name or "друг"
    
    # Сохраняем/обновляем пользователя в БД
    try:
        async with get_session() as db:
            user = await get_or_create_user(
                session=db,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
            db_user_id = user.id
            await state.update_data(db_user_id=user.id)
            logger.info(f"User {user.telegram_id} (@{user.username}) started bot")
            
            # Проверяем незавершённые сессии
            active_session = await get_active_session(db, user.id)
            
    except Exception as e:
        logger.error(f"Failed to save user: {e}")
        # Продолжаем работу даже без БД
    
    # Если есть незавершённая сессия — предлагаем продолжить
    if active_session:
        # Проверяем TTL сессии
        session_age = datetime.utcnow() - active_session.started_at
        if session_age < timedelta(hours=SESSION_TTL_HOURS):
            current_q = active_session.current_question
            role_name = active_session.role_name
            
            await message.answer(
                f"👋 <b>Привет, {user_first_name}!</b>\n\n"
                f"У тебя есть незавершённая диагностика:\n"
                f"• Роль: {role_name}\n"
                f"• Прогресс: <b>{current_q - 1}/10</b> вопросов\n\n"
                f"Хочешь продолжить с того места?",
                reply_markup=get_session_recovery_keyboard(active_session.id, current_q),
            )
            await state.set_state(DiagnosticStates.session_recovery)
            return
    
    # Проверяем, есть ли у пользователя завершённые диагностики
    has_completed = False
    best_score = None
    
    if db_user_id:
        try:
            async with get_session() as db:
                stats = await get_user_stats(db, db_user_id)
                has_completed = stats["total_diagnostics"] > 0
                best_score = stats["best_score"]
        except Exception as e:
            logger.warning(f"Failed to get user stats: {e}")
    
    # Выбираем клавиатуру
    if has_completed:
        keyboard = get_start_with_history_keyboard(True, best_score)
    else:
        keyboard = get_role_keyboard()
    
    # Стандартный flow — персонализированное приветствие
    await message.answer(
        get_welcome_text(user_first_name),
        reply_markup=keyboard,
    )
    await state.set_state(DiagnosticStates.choosing_role)


@router.callback_query(F.data.startswith("role:"), DiagnosticStates.choosing_role)
async def process_role(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора роли."""
    role = callback.data.split(":")[1]
    role_name = "Дизайнер" if role == "designer" else "Продакт-менеджер"
    
    await state.update_data(role=role, role_name=role_name)
    
    await callback.message.edit_text(
        f"✅ Роль: <b>{role_name}</b>\n\nТеперь выбери свой опыт:",
        reply_markup=get_experience_keyboard(),
    )
    await state.set_state(DiagnosticStates.choosing_experience)
    await callback.answer()


# === PROGRESSIVE ONBOARDING ===
# Экран 1: Краткие правила + контекстная подсказка
ONBOARDING_STEP1 = """
📋 <b>Как проходит диагностика</b>

✅ Роль: <b>{role_name}</b>
✅ Опыт: <b>{exp_value}</b>

━━━━━━━━━━━━━━━━━━━━

<b>📝 3 простых правила:</b>

1️⃣ <b>Честность важнее "правильности"</b>
   Нет плохих ответов — есть неточная диагностика.

2️⃣ <b>Текст или голос</b>
   Пиши текстом или отправляй голосовые.

3️⃣ <b>Развёрнуто = точнее</b>
   Чем больше деталей — тем точнее результат.

━━━━━━━━━━━━━━━━━━━━

{experience_tip}

🎯 <b>Темы вопросов:</b> {question_topics}

⏱️ <b>10 вопросов • ~15 минут</b>
"""

# Экран 2: Пример ответа
ONBOARDING_STEP2 = """
💡 <b>Пример хорошего ответа</b>

<i>Вопрос: "Расскажи о сложном проекте"</i>

━━━━━━━━━━━━━━━━━━━━

❌ <b>Плохо:</b>
<i>"Делал редизайн, было сложно, справился."</i>

━━━━━━━━━━━━━━━━━━━━

✅ <b>Хорошо:</b>
<i>"Редизайн B2B-портала для финтеха. 50k пользователей. 

Главная сложность — 4 разных UI за 5 лет. 
Провёл 12 интервью, нашёл топ-5 проблем. 
Создал дизайн-систему. 

Результат: время разработки -30%, NPS +15. 

Ошибка — недооценил сопротивление команды."</i>

━━━━━━━━━━━━━━━━━━━━

<b>🎯 Формула:</b> Контекст → Действия → Результат → Выводы
"""

# Сокращённый онбординг для возвращающихся
RETURNING_USER_TEXT = """
👋 <b>Привет снова, {first_name}!</b>

Рад видеть тебя! {stats_line}

Готов к новой диагностике?
"""


@router.callback_query(F.data.startswith("exp:"), DiagnosticStates.choosing_experience)
async def process_experience(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора опыта."""
    exp_map = {
        "junior": "до 1 года",
        "middle": "1-3 года",
        "senior": "3-5 лет",
        "lead": "5+ лет",
    }
    
    exp_key = callback.data.split(":")[1]
    exp_value = exp_map[exp_key]
    
    await state.update_data(experience=exp_key, experience_name=exp_value)
    
    data = await state.get_data()
    db_user_id = data.get("db_user_id")
    is_returning_user = False
    last_score = None
    
    # Проверяем, есть ли у пользователя завершённые сессии (returning user)
    if db_user_id:
        try:
            async with get_session() as db:
                # Создаём сессию диагностики
                db_session = await create_db_session(
                    session=db,
                    user_id=db_user_id,
                    role=data["role"],
                    role_name=data["role_name"],
                    experience=exp_key,
                    experience_name=exp_value,
                )
                await state.update_data(db_session_id=db_session.id)
                logger.info(f"Created diagnostic session {db_session.id}")
                
                # Проверяем историю
                past_sessions = await get_user_sessions(db, db_user_id, limit=5)
                completed = [s for s in past_sessions if s.status == "completed"]
                if completed:
                    is_returning_user = True
                    last_score = completed[0].total_score
                    
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
    
    # Для возвращающихся — сокращённый онбординг
    if is_returning_user:
        first_name = callback.from_user.first_name or "друг"
        stats_line = ""
        if last_score:
            stats_line = f"В прошлый раз ты набрал <b>{last_score}/100</b>."
        
        await callback.message.edit_text(
            RETURNING_USER_TEXT.format(
                first_name=first_name,
                stats_line=stats_line,
            ),
            reply_markup=get_returning_user_keyboard(),
        )
        await state.set_state(DiagnosticStates.onboarding)
        await callback.answer()
        return
    
    # Для новых — Progressive Onboarding (Step 1) с контекстом
    role = data.get("role", "designer")
    experience_tip = EXPERIENCE_TIPS.get(exp_key, "")
    question_topics = QUESTION_TOPICS.get(role, "проекты, решения, рост")
    
    onboarding = ONBOARDING_STEP1.format(
        role_name=data['role_name'],
        exp_value=exp_value,
        experience_tip=experience_tip,
        question_topics=question_topics,
    )
    
    await callback.message.edit_text(
        onboarding,
        reply_markup=get_onboarding_keyboard(),
    )
    await state.set_state(DiagnosticStates.onboarding)
    await callback.answer()


@router.callback_query(F.data == "onboarding_step2", DiagnosticStates.onboarding)
async def process_onboarding_step2(callback: CallbackQuery, state: FSMContext):
    """Переход к шагу 2 онбординга (пример ответа)."""
    await callback.message.edit_text(
        ONBOARDING_STEP2,
        reply_markup=get_onboarding_step2_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "onboarding_back", DiagnosticStates.onboarding)
async def process_onboarding_back(callback: CallbackQuery, state: FSMContext):
    """Возврат к шагу 1 онбординга."""
    data = await state.get_data()
    
    role = data.get("role", "designer")
    exp_key = data.get("experience", "middle")
    experience_tip = EXPERIENCE_TIPS.get(exp_key, "")
    question_topics = QUESTION_TOPICS.get(role, "проекты, решения, рост")
    
    onboarding = ONBOARDING_STEP1.format(
        role_name=data.get('role_name', 'Специалист'),
        exp_value=data.get('experience_name', ''),
        experience_tip=experience_tip,
        question_topics=question_topics,
    )
    
    await callback.message.edit_text(
        onboarding,
        reply_markup=get_onboarding_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "onboarding_done", DiagnosticStates.onboarding)
async def process_onboarding_done(callback: CallbackQuery, state: FSMContext):
    """Пользователь прочитал онбординг — готов начать."""
    data = await state.get_data()
    
    await callback.message.edit_text(
        f"🚀 <b>Отлично!</b>\n\n"
        f"Роль: {data['role_name']}\n"
        f"Опыт: {data['experience_name']}\n\n"
        f"Впереди 10 вопросов. Погнали!",
        reply_markup=get_start_diagnostic_keyboard(),
    )
    await state.set_state(DiagnosticStates.ready_to_start)
    await callback.answer()


@router.callback_query(F.data == "skip_onboarding", DiagnosticStates.onboarding)
async def process_skip_onboarding(callback: CallbackQuery, state: FSMContext):
    """Пропуск онбординга для возвращающихся пользователей."""
    data = await state.get_data()
    
    await callback.message.edit_text(
        f"🚀 <b>Погнали!</b>\n\n"
        f"Роль: {data['role_name']}\n"
        f"Опыт: {data['experience_name']}\n\n"
        f"10 вопросов ждут!",
        reply_markup=get_start_diagnostic_keyboard(),
    )
    await state.set_state(DiagnosticStates.ready_to_start)
    await callback.answer()


@router.callback_query(F.data == "show_onboarding", DiagnosticStates.onboarding)
async def process_show_onboarding(callback: CallbackQuery, state: FSMContext):
    """Показать онбординг по запросу (для возвращающихся)."""
    data = await state.get_data()
    
    role = data.get("role", "designer")
    exp_key = data.get("experience", "middle")
    experience_tip = EXPERIENCE_TIPS.get(exp_key, "")
    question_topics = QUESTION_TOPICS.get(role, "проекты, решения, рост")
    
    onboarding = ONBOARDING_STEP1.format(
        role_name=data.get('role_name', 'Специалист'),
        exp_value=data.get('experience_name', ''),
        experience_tip=experience_tip,
        question_topics=question_topics,
    )
    
    await callback.message.edit_text(
        onboarding,
        reply_markup=get_onboarding_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "restart")
async def process_restart(callback: CallbackQuery, state: FSMContext):
    """Перезапуск диагностики."""
    # Сохраняем db_user_id перед очисткой
    data = await state.get_data()
    db_user_id = data.get("db_user_id")
    
    await state.clear()
    
    # Восстанавливаем db_user_id
    if db_user_id:
        await state.update_data(db_user_id=db_user_id)
    
    await callback.message.edit_text(
        WELCOME_TEXT,
        reply_markup=get_role_keyboard(),
    )
    await state.set_state(DiagnosticStates.choosing_role)
    await callback.answer()


@router.callback_query(F.data.startswith("continue_session:"), DiagnosticStates.session_recovery)
async def continue_session(callback: CallbackQuery, state: FSMContext):
    """Продолжение незавершённой сессии."""
    from src.db.repositories import get_session_by_id
    import time
    
    session_id = int(callback.data.split(":")[1])
    
    try:
        async with get_session() as db:
            db_session = await get_session_by_id(db, session_id)
            
            if not db_session:
                await callback.answer("❌ Сессия не найдена", show_alert=True)
                return
            
            # Восстанавливаем FSM state из БД
            conversation_history = db_session.conversation_history or []
            analysis_history = db_session.analysis_history or []
            current_question = db_session.current_question
            
            await state.update_data(
                db_session_id=db_session.id,
                db_user_id=db_session.user_id,
                role=db_session.role,
                role_name=db_session.role_name,
                experience=db_session.experience,
                experience_name=db_session.experience_name,
                current_question=current_question,
                conversation_history=conversation_history,
                analysis_history=analysis_history,
                answer_stats=[],  # Начинаем статистику заново
                question_start_time=time.time(),
            )
            
            # Получаем последний вопрос из истории или генерируем новый
            if conversation_history and len(conversation_history) >= current_question - 1:
                # Если есть история — генерируем следующий вопрос
                from src.ai.client import generate_question
                
                await callback.message.edit_text("🔄 Восстанавливаю сессию...")
                
                question = await generate_question(
                    role=db_session.role,
                    role_name=db_session.role_name,
                    experience=db_session.experience_name,
                    question_number=current_question,
                    conversation_history=conversation_history,
                    analysis_history=analysis_history,
                )
                
                await state.update_data(current_question_text=question)
                
                await callback.message.edit_text(
                    f"✅ <b>Сессия восстановлена!</b>\n\n"
                    f"Продолжаем с вопроса {current_question}/10:\n\n"
                    f"<b>Вопрос {current_question}/10</b>\n\n{question}",
                )
            else:
                # Нет истории — генерируем первый вопрос
                from src.ai.client import generate_question
                
                await callback.message.edit_text("🔄 Восстанавливаю сессию...")
                
                question = await generate_question(
                    role=db_session.role,
                    role_name=db_session.role_name,
                    experience=db_session.experience_name,
                    question_number=1,
                    conversation_history=[],
                    analysis_history=[],
                )
                
                await state.update_data(
                    current_question=1,
                    current_question_text=question,
                )
                
                await callback.message.edit_text(
                    f"✅ <b>Сессия восстановлена!</b>\n\n"
                    f"<b>Вопрос 1/10</b>\n\n{question}",
                )
            
            await state.set_state(DiagnosticStates.answering)
            logger.info(f"Session {session_id} recovered, question {current_question}")
            
    except Exception as e:
        logger.error(f"Failed to recover session: {e}")
        await callback.answer("❌ Ошибка восстановления", show_alert=True)
        # Fallback — начинаем заново
        await callback.message.edit_text(
            WELCOME_TEXT,
            reply_markup=get_role_keyboard(),
        )
        await state.set_state(DiagnosticStates.choosing_role)
    
    await callback.answer()


@router.callback_query(F.data == "restart_fresh", DiagnosticStates.session_recovery)
async def restart_fresh(callback: CallbackQuery, state: FSMContext):
    """Начать заново, игнорируя незавершённую сессию."""
    from src.db.repositories import get_active_session
    from sqlalchemy import update
    from src.db.models import DiagnosticSession
    
    data = await state.get_data()
    db_user_id = data.get("db_user_id")
    
    # Помечаем старую сессию как abandoned
    if db_user_id:
        try:
            async with get_session() as db:
                active = await get_active_session(db, db_user_id)
                if active:
                    stmt = (
                        update(DiagnosticSession)
                        .where(DiagnosticSession.id == active.id)
                        .values(status="abandoned")
                    )
                    await db.execute(stmt)
                    await db.commit()
                    logger.info(f"Session {active.id} marked as abandoned")
        except Exception as e:
            logger.error(f"Failed to abandon session: {e}")
    
    await state.clear()
    
    if db_user_id:
        await state.update_data(db_user_id=db_user_id)
    
    await callback.message.edit_text(
        WELCOME_TEXT,
        reply_markup=get_role_keyboard(),
    )
    await state.set_state(DiagnosticStates.choosing_role)
    await callback.answer()


# ==================== MAIN MENU HANDLER ====================

MAIN_MENU_TEXT = """
🎯 <b>Deep Diagnostic Bot</b>

Выбери действие:
"""


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню."""
    await state.clear()
    
    # Восстанавливаем db_user_id если есть
    try:
        async with get_session() as db:
            user = await get_or_create_user(
                session=db,
                telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
            )
            await state.update_data(db_user_id=user.id)
    except Exception:
        pass
    
    await callback.message.edit_text(
        MAIN_MENU_TEXT,
        reply_markup=get_role_keyboard(),
    )
    await state.set_state(DiagnosticStates.choosing_role)
    await callback.answer()


# ==================== CANCEL COMMAND ====================

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущей диагностики."""
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer(
            "🤷 Нечего отменять — ты не в процессе диагностики.",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return
    
    # Получаем данные для сохранения статуса
    data = await state.get_data()
    db_session_id = data.get("db_session_id")
    current_question = data.get("current_question", 0)
    
    # Помечаем сессию как abandoned
    if db_session_id:
        try:
            from sqlalchemy import update
            from src.db.models import DiagnosticSession
            
            async with get_session() as db:
                stmt = (
                    update(DiagnosticSession)
                    .where(DiagnosticSession.id == db_session_id)
                    .values(status="cancelled")
                )
                await db.execute(stmt)
                await db.commit()
                logger.info(f"Session {db_session_id} cancelled at question {current_question}")
        except Exception as e:
            logger.error(f"Failed to mark session as cancelled: {e}")
    
    # Очищаем state
    await state.clear()
    
    await message.answer(
        f"❌ <b>Диагностика отменена</b>\n\n"
        f"Прогресс: {current_question}/10 вопросов\n"
        f"<i>Можешь начать заново в любое время.</i>",
        reply_markup=get_back_to_menu_keyboard(),
    )
