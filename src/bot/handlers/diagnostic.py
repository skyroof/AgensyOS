"""
Обработчик диагностики — flow 10 вопросов с AI.
"""
import logging
import asyncio
import time
import random
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest

from src.bot.states import DiagnosticStates
from src.bot.keyboards.inline import (
    get_restart_keyboard, 
    get_report_keyboard, 
    get_confirm_answer_keyboard,
    get_pause_keyboard,
    get_feedback_rating_keyboard,
    get_skip_comment_keyboard,
    get_result_summary_keyboard,
    get_back_to_summary_keyboard,
    get_delayed_feedback_keyboard,
    get_demo_result_keyboard,
    get_paywall_keyboard,
    get_question_keyboard,
    get_oto_keyboard,
    get_after_share_keyboard,
    get_report_sections_keyboard,
    get_back_to_report_menu_keyboard,
    get_post_diagnostic_keyboard,
    get_session_recovery_keyboard,
)
from src.bot.keyboards.reply import get_main_menu_reply_keyboard
from src.core.prices import SHARE_PROMO_CODE
from src.db.repositories import balance_repo
from src.ai.question_gen import generate_question
from src.ai.cached_questions import get_cached_first_question
from src.ai.answer_analyzer import (
    analyze_answer, 
    calculate_category_scores,
    calibrate_scores,
    METRIC_NAMES_RU,
    METRIC_CATEGORIES,
)
from src.ai.report_gen import generate_detailed_report, stream_detailed_report, split_message, split_report_into_blocks, sanitize_html, generate_fallback_report
from src.ai.client import AIServiceError
from src.analytics import build_profile, format_profile_text, get_benchmark, format_benchmark_text, build_pdp, format_pdp_text
from src.db import get_session
from src.db.repositories import (
    save_answer, 
    update_session_progress, 
    complete_session, 
    save_feedback, 
    create_session,
    get_or_create_user,
    get_active_session,
)
from src.db.repositories.reminder_repo import schedule_stuck_reminder, cancel_stuck_reminders, schedule_smart_reminder, cancel_all_user_reminders
from src.utils.message_splitter import send_long_message, send_with_continuation

router = Router(name="diagnostic")
logger = logging.getLogger(__name__)

# Количество вопросов в зависимости от режима
FULL_QUESTIONS = 10
DEMO_QUESTIONS = 10
# REMINDER_TIMEOUT удален, так как теперь через БД (5 минут по дефолту)

def get_total_questions(mode: str) -> int:
    """Получить количество вопросов для режима."""
    return DEMO_QUESTIONS if mode == "demo" else FULL_QUESTIONS

# _reminder_tasks удален

async def safe_send_chat_action(bot: Bot, chat_id: int, action: ChatAction) -> None:
    """Безопасная отправка chat action (игнорирует ошибки топиков/форумов)."""
    try:
        await bot.send_chat_action(chat_id, action)
    except Exception:
        pass  # Игнорируем ошибки (топики, форумы, etc)


def generate_progress_message(
    current_question: int,
    total_questions: int,
    answer_stats: list[dict],
    answer_text: str,
) -> str:
    """
    Генерация сообщения с прогрессом и gamification.
    
    Включает:
    - Визуальный прогресс-бар
    - Milestone messages на 5, 8, 10 вопросе
    - Micro-feedback по длине/скорости ответа
    """
    # Прогресс-бар
    completed = current_question
    remaining = total_questions - completed
    filled = "█" * completed
    empty = "░" * remaining
    pct = int(completed / total_questions * 100)
    
    # Базовое сообщение
    progress_bar = f"<code>{filled}{empty}</code> {pct}%"
    
    # Milestone messages (приоритетные)
    milestone = ""
    if current_question == 5:
        milestone = "\n\n🎯 <b>Половина пути!</b>\nОтличный темп — продолжай в том же духе! 💪"
    elif current_question == 8:
        milestone = "\n\n🏁 <b>Финишная прямая!</b>\nОсталось всего 2 вопроса!"
    elif current_question == 10:
        milestone = "\n\n🎉 <b>Последний ответ принят!</b>\nСейчас подготовлю твой результат..."
    
    answer_len = len(answer_text)
    
    # Streak detection (быстрые/глубокие ответы подряд)
    streak = ""
    if len(answer_stats) >= 3:
        recent = answer_stats[-3:]
        avg_duration = sum(s["duration_sec"] for s in recent) / 3
        if avg_duration < 120:  # Менее 2 минут в среднем
            streak = "\n\n⚡ <i>Держишь отличный темп!</i>"
        
        # Считаем сколько глубоких ответов подряд (с конца)
        deep_streak = 0
        for stat in reversed(answer_stats):
            if stat["length"] > 300:
                deep_streak += 1
            else:
                break
        
        if deep_streak >= 3:
            streak = f"\n\n🔥 <i>{deep_streak} глубоких ответов подряд — молодец!</i>"
    
    # Achievement для первого длинного ответа (ранний показатель)
    if current_question <= 3 and answer_len > 400 and not any(s["length"] > 400 for s in answer_stats[:-1] if answer_stats):
        streak = "\n\n🌟 <i>Сразу видно — ты подходишь серьёзно!</i>"
    
    # Рандомная позитивная реакция (если нет milestone или streak)
    reaction = ""
    if not milestone and not streak:
        reaction = f"\n\n<i>{get_random_reaction(answer_len)}</i>"
    
    # Собираем финальное сообщение
    header = f"✅ <b>Ответ {current_question}/{total_questions} принят!</b>"
    
    return f"{header}\n\n{progress_bar}{milestone}{streak}{reaction}"


def generate_final_achievements(answer_stats: list[dict]) -> str:
    """
    Генерация итоговых достижений по результатам диагностики.
    
    Анализирует:
    - Общее время прохождения
    - Глубину ответов
    - Стабильность (streak)
    - Особые паттерны
    """
    if not answer_stats:
        return "\n\n<i>Отлично справился! Готовлю твой результат...</i>"
    
    achievements: list[str] = []
    
    # Общее время
    total_time = sum(s["duration_sec"] for s in answer_stats)
    avg_time = total_time / len(answer_stats) if answer_stats else 0
    
    # Общая длина
    total_length = sum(s["length"] for s in answer_stats)
    avg_length = total_length / len(answer_stats) if answer_stats else 0
    
    # === TIME ACHIEVEMENTS ===
    if total_time < 900:  # < 15 минут
        achievements.append("⚡ <b>Скоростной режим</b> — менее 15 минут!")
    elif total_time < 1800:  # < 30 минут
        achievements.append("🚀 <b>Отличный темп</b> — уложился в 30 минут")
    elif total_time > 3600:  # > 60 минут
        achievements.append("🧘 <b>Глубокий мыслитель</b> — вдумчивый подход")
    
    # === LENGTH ACHIEVEMENTS ===
    if avg_length > 400:
        achievements.append("📚 <b>Эксперт</b> — очень детальные ответы")
    elif avg_length > 250:
        achievements.append("📝 <b>Аналитик</b> — хорошая глубина ответов")
    elif avg_length < 100:
        achievements.append("💨 <b>Лаконичность</b> — краткость — сестра таланта")
    
    # === STREAK ACHIEVEMENTS ===
    long_answers = [s for s in answer_stats if s["length"] > 300]
    if len(long_answers) >= 8:
        achievements.append("🔥 <b>Серия эксперта</b> — 8+ глубоких ответов")
    elif len(long_answers) >= 5:
        achievements.append("✨ <b>Глубокий анализ</b> — 5+ развёрнутых ответов")
    
    # === CONSISTENCY ===
    lengths = [s["length"] for s in answer_stats]
    if lengths:
        variance = sum((l - avg_length) ** 2 for l in lengths) / len(lengths)
        std_dev = variance ** 0.5
        if std_dev < 50:  # Очень стабильные ответы
            achievements.append("🎯 <b>Стабильность</b> — ровное качество ответов")
    
    # === SPECIAL PATTERNS ===
    # Разгон — последние ответы длиннее первых
    if len(answer_stats) >= 5:
        first_half = sum(s["length"] for s in answer_stats[:5]) / 5
        second_half = sum(s["length"] for s in answer_stats[5:]) / max(1, len(answer_stats[5:]))
        if second_half > first_half * 1.5:
            achievements.append("📈 <b>Разгон</b> — раскрылся к концу!")
    
    if not achievements:
        achievements.append("✅ <b>Диагностика пройдена</b>")
    
    # Лимитируем до 3 достижений
    displayed = achievements[:3]
    
    return "\n\n" + "\n".join(displayed)


def get_typing_hint(answer_length: int) -> str:
    """
    Генерация подсказки по длине ответа (показывается в preview).
    
    Помогает пользователю понять, достаточно ли развёрнутый ответ.
    """
    if answer_length < 50:
        return "💡 <i>Совет: добавь деталей для более точного анализа</i>"
    elif answer_length < 100:
        return "📝 <i>Неплохо! Но чем больше деталей — тем точнее результат</i>"
    elif answer_length < 200:
        return "👍 <i>Хороший ответ!</i>"
    elif answer_length < 400:
        return "✨ <i>Отличный развёрнутый ответ!</i>"
    elif answer_length < 700:
        return "🔥 <i>Впечатляющая детализация!</i>"
    else:
        return "📚 <i>Вау, очень подробно! Это точно поможет анализу</i>"


# Пул позитивных реакций (не оценочных!)
POSITIVE_REACTIONS = [
    "✨ Интересно!",
    "💡 Записал!",
    "📝 Принято!",
    "🎯 Понял тебя!",
    "👀 Любопытно!",
    "💭 Интересный взгляд!",
    "🧠 Зафиксировал!",
    "📌 Отмечено!",
    "🔍 Анализирую...",
    "💫 Хорошо!",
]

# Реакции для длинных ответов
DEEP_REACTIONS = [
    "🔥 Глубоко!",
    "📚 Очень детально!",
    "💎 Богатый ответ!",
    "🌟 Впечатляет!",
    "🧩 Много инсайтов!",
]


def get_random_reaction(answer_length: int) -> str:
    """
    Генерация рандомной позитивной реакции.
    
    Не оценка! Просто acknowledgment что ответ получен.
    """
    if answer_length > 400:
        # Для длинных ответов — специальные реакции
        return random.choice(DEEP_REACTIONS)
    else:
        return random.choice(POSITIVE_REACTIONS)


async def start_reminder(user_id: int, session_id: int):
    """Запускает таймер напоминания (через БД)."""
    if not session_id:
        return
    try:
        async with get_session() as db:
            # Сначала отменяем старые, чтобы не дублировать
            await cancel_stuck_reminders(db, session_id)
            # Планируем новое (5 минут)
            await schedule_stuck_reminder(db, user_id, session_id, minutes_delay=5)
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to start reminder: {e}")


async def cancel_reminder(session_id: int):
    """Отменяет таймер напоминания (через БД)."""
    if not session_id:
        return
    try:
        async with get_session() as db:
            await cancel_stuck_reminders(db, session_id)
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to cancel reminder: {e}")


@router.callback_query(F.data == "start_diagnostic")
async def start_diagnostic(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Начало диагностики — первый вопрос."""
    logger.info(f"START_DIAGNOSTIC triggered by {callback.from_user.id}")
    # Сразу отвечаем, чтобы убрать часики (и избежать timeout)
    try:
        await callback.answer()
        logger.info("Callback answered successfully")
    except Exception as e:
        logger.warning(f"Failed to answer callback in start_diagnostic: {e}")

    # Prevent double clicks
    current_state = await state.get_state()
    if current_state == DiagnosticStates.starting:
        return

    # Сразу меняем состояние, чтобы избежать двойного клика
    # Но сначала проверим данные!
    data = await state.get_data()
    
    # Проверяем наличие роли/опыта (если стейт пустой после рестарта)
    if "role" not in data or "experience" not in data:
        # Попытка восстановления сессии из БД
        try:
            async with get_session() as db:
                user = await get_or_create_user(
                    session=db,
                    telegram_id=callback.from_user.id,
                    username=callback.from_user.username,
                    first_name=callback.from_user.first_name,
                    last_name=callback.from_user.last_name,
                )
                active_session = await get_active_session(db, user.id)
                
                if active_session:
                    logger.info(f"Restoring session {active_session.id} for user {user.id}")
                    # Восстанавливаем данные в стейт
                    await state.update_data(
                        role=active_session.role,
                        role_name=active_session.role_name,
                        experience=active_session.experience,
                        experience_name=active_session.experience_name,
                        db_user_id=user.id,
                        db_session_id=active_session.id,
                        current_question=active_session.current_question,
                        diagnostic_mode=active_session.mode,
                        conversation_history=active_session.conversation_history or [],
                        analysis_history=active_session.analysis_history or [],
                        answer_stats=[], # Статистика может быть потеряна, но это не критично
                    )
                    # Обновляем data, чтобы пройти проверки ниже
                    data = await state.get_data()
                    
                    # Если сессия уже была в процессе, перенаправляем на восстановление
                    if active_session.current_question > 1:
                        await callback.message.edit_text(
                            "🔄 <b>Восстанавливаю контекст...</b>\n\n"
                            f"Нашел твою активную сессию (Вопрос {active_session.current_question}). Продолжаем!",
                        )
                        
                        try:
                            # Генерация текущего вопроса
                            question = await generate_question(
                                role=active_session.role,
                                role_name=active_session.role_name,
                                experience=active_session.experience,
                                question_number=active_session.current_question,
                                conversation_history=active_session.conversation_history,
                                analysis_history=active_session.analysis_history
                            )
                            
                            await state.update_data(current_question_text=question)
                            
                            await callback.message.answer(
                                f"{active_session.current_question}️⃣ <b>Вопрос {active_session.current_question}/{get_total_questions(active_session.mode)}</b>\n\n{question}",
                                reply_markup=get_question_keyboard(show_skip=False)
                            )
                            await state.set_state(DiagnosticStates.answering)
                            
                            # Ставим таймер напоминания
                            await start_reminder(user.id, active_session.id)
                            return
                        except Exception as e:
                            logger.error(f"Failed to restore question: {e}")
                            # Fallthrough to normal start if failed
                            pass 
        except Exception as e:
            logger.error(f"Failed to restore session: {e}")

    # Повторная проверка
    if "role" not in data or "experience" not in data:
        logger.warning(f"Missing state data for user {callback.from_user.id}")
        await callback.answer("Сессия истекла. Начни заново.", show_alert=True)
        await state.clear()
        return

    await state.set_state(DiagnosticStates.starting)

    # UX: Сразу показываем лоадер, чтобы юзер видел реакцию
    try:
        loading_msg = await callback.message.edit_text(
            "🚀 <b>Запускаю диагностику...</b>"
        )
    except TelegramBadRequest:
        # Если сообщение не изменилось или удалено
        loading_msg = callback.message

    try:
        user_id = callback.from_user.id
        db_user_id = data.get("db_user_id")
        db_session_id = data.get("db_session_id")
        
        if not db_session_id:
            # ==================== ПРОВЕРКА ДОСТУПА ====================
            async with get_session() as db:
                # Если db_user_id нет в стейте — восстанавливаем
                if not db_user_id:
                    user = await get_or_create_user(
                        session=db,
                        telegram_id=user_id,
                        username=callback.from_user.username,
                        first_name=callback.from_user.first_name,
                        last_name=callback.from_user.last_name,
                    )
                    db_user_id = user.id
                    await state.update_data(db_user_id=db_user_id)
                
                # Проверяем доступ используя PK пользователя!
                access = await balance_repo.check_diagnostic_access(db, db_user_id)
            
            if not access.allowed:
                # Возвращаем состояние назад, если отказ
                await state.set_state(DiagnosticStates.ready_to_start)
                
                # Нет доступа — показываем paywall
                await callback.message.edit_text(
                    "🔒 <b>Нет доступных диагностик</b>\n\n"
                    f"Баланс: {access.balance} диагностик\n"
                    f"Демо: {'✅ использовано' if access.demo_used else '🆓 доступно'}\n\n"
                    "Купи диагностику, чтобы продолжить!",
                    reply_markup=get_paywall_keyboard(),
                )
                await callback.answer("Нужна подписка", show_alert=True)
                return
            
            # Определяем режим (demo или full)
            diagnostic_mode = access.mode  # "demo" или "full"
            total_questions = get_total_questions(diagnostic_mode)
            
            logger.info(f"[ACCESS] User {user_id}: mode={diagnostic_mode}, balance={access.balance}")
            
            # ==================== ТРАНЗАКЦИЯ: СПИСАНИЕ + СОЗДАНИЕ ====================
            try:
                async with get_session() as db:
                    # 1. Списываем диагностику с баланса (без коммита)
                    success = await balance_repo.use_diagnostic(db, db_user_id, diagnostic_mode, commit=False)
                    if not success:
                        # Если вдруг баланс изменился между проверкой и списанием
                        await state.set_state(DiagnosticStates.ready_to_start)
                        await callback.answer("Ошибка доступа: баланс исчерпан", show_alert=True)
                        return

                    # 2. Очищаем все старые напоминания
                    await cancel_all_user_reminders(db, db_user_id)

                    # 3. Создаем сессию (без коммита)
                    diagnostic_session = await create_session(
                        session=db,
                        user_id=db_user_id,
                        role=data["role"],
                        role_name=data["role_name"],
                        experience=data["experience"],
                        experience_name=data["experience_name"],
                        mode=diagnostic_mode,
                        commit=False,
                    )
                    
                    # 3. Фиксируем изменения
                    await db.commit()
                    await db.refresh(diagnostic_session)
                    db_session_id = diagnostic_session.id
                    
                    logger.info(f"Created {diagnostic_mode} session {db_session_id} for user {user_id}")
                    
            except Exception as e:
                logger.error(f"Failed to create session in DB: {e}")
                await state.set_state(DiagnosticStates.ready_to_start)
                await callback.answer("Ошибка базы данных. Попробуй позже.", show_alert=True)
                return
        else:
            # Сессия уже есть (восстановлена)
            diagnostic_mode = data.get("diagnostic_mode", "full")
            total_questions = get_total_questions(diagnostic_mode)
        
        await state.update_data(
            current_question=1,
            conversation_history=[],
            analysis_history=[],
            answer_stats=[],  # Статистика ответов для gamification
            question_start_time=time.time(),  # Трекаем время на ответ
            db_session_id=db_session_id,  # Сохраняем ID сессии
            diagnostic_mode=diagnostic_mode,  # "demo" или "full"
            total_questions=total_questions,  # 3 или 10
        )
        
        # Пробуем взять первый вопрос из кэша (мгновенно!)
        cached_question = get_cached_first_question(data["role"], data["experience"])
        
        if cached_question:
            # Кэш найден — показываем быструю анимацию
            try:
                loading_msg = await callback.message.edit_text(
                    "🚀 <b>Запускаю диагностику...</b>"
                )
            except TelegramBadRequest:
                return
            await asyncio.sleep(0.5)  # Минимальная задержка для UX
            question = cached_question
            logger.info(f"Using cached first question for {data['role']}/{data['experience']}")
        else:
            # Кэш не найден — генерируем через AI с анимацией
            try:
                loading_msg = await callback.message.edit_text(
                    "🧠 <b>Подготавливаю диагностику...</b>\n\n<code>░░░░░░░░░░</code> 0%"
                )
            except TelegramBadRequest:
                return
            
            async def animate_first_question():
                states = [
                    ("▓▓░░░░░░░░", "20%", "Анализирую профиль..."),
                    ("▓▓▓▓░░░░░░", "40%", "Формирую стратегию..."),
                    ("▓▓▓▓▓▓░░░░", "60%", "Подбираю вопросы..."),
                    ("▓▓▓▓▓▓▓▓░░", "80%", "Почти готово..."),
                    ("▓▓▓▓▓▓▓▓▓▓", "100%", "Поехали!"),
                ]
                for bar, pct, text in states:
                    await loading_msg.edit_text(
                        f"🧠 <b>{text}</b>\n\n<code>{bar}</code> {pct}"
                    )
                    await asyncio.sleep(0.5)
            
            # Запускаем анимацию и генерацию параллельно
            # Но реально анимация здесь блокирующая, так что просто перед генерацией
            await animate_first_question()
            
            question = await generate_question(
                role=data["role"],
                role_name=data.get("role_name", "Специалист"),
                experience=data["experience"],
                question_number=1,
                conversation_history=[],
                analysis_history=[]
            )
        
        # Сохраняем вопрос
        await state.update_data(current_question_text=question)
        
        # Устанавливаем состояние ДО отправки вопроса, чтобы избежать race condition
        await state.set_state(DiagnosticStates.answering)
        
        # Ставим таймер напоминания (5 минут)
        db_user_id = data.get("db_user_id")
        await start_reminder(db_user_id, db_session_id)
        
        # Обновляем сообщение на вопрос
        await loading_msg.edit_text(
            f"1️⃣ <b>Вопрос 1/{total_questions}</b>\n\n{question}",
            reply_markup=get_question_keyboard(show_skip=False)
        )

    except Exception as e:
        logger.error(f"Error starting diagnostic: {e}", exc_info=True)
        await callback.message.edit_text(
            "😔 Произошла ошибка при запуске.\nПопробуй нажать /start и начать заново."
        )


@router.message(DiagnosticStates.answering)
async def handle_answer(message: Message, state: FSMContext, bot: Bot):
    """Обработка ответа пользователя."""
    logger.info(f"handle_answer triggered for {message.from_user.id}")
    data = await state.get_data()
    
    # Валидация
    if not message.text and not message.voice:
        await message.answer("Пожалуйста, напиши ответ текстом или запиши голосовое.")
        return
        
    answer_text = message.text if message.text else "[Голосовое сообщение]"
    
    # Проверяем длину ответа (если текст)
    if message.text and len(message.text) < 10:
        await message.answer("Слишком короткий ответ. Расскажи чуть подробнее, пожалуйста.")
        return

    # Сохраняем черновик ответа и показываем меню подтверждения
    await state.update_data(draft_answer=answer_text)
    
    # Удаляем таймер, пока юзер думает
    db_session_id = data.get("db_session_id")
    user_id = message.from_user.id
    if db_session_id:
        await cancel_reminder(db_session_id)

    await message.answer(
        f"<b>Твой ответ:</b>\n\n{answer_text}\n\nОтправляем или хочешь дополнить?",
        reply_markup=get_confirm_answer_keyboard()
    )
    await state.set_state(DiagnosticStates.confirming_answer)


@router.callback_query(DiagnosticStates.confirming_answer, F.data == "confirm_answer")
async def confirm_answer(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение ответа — переход к следующему вопросу."""
    logger.info(f"DEBUG: Entering confirm_answer for {callback.from_user.id}")
    try:
        await callback.answer()
        logger.info("DEBUG: Callback answered (confirm)")
    except Exception as e:
        logger.error(f"DEBUG: Callback answer failed (confirm): {e}")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        logger.warning(f"Double click on confirm_answer by {callback.from_user.id}")
        return
    
    # Показываем "Анализирую..."
    processing_msg = await callback.message.answer("🤔 Анализирую ответ...")
    
    data = await state.get_data()
    answer_text = data.get("draft_answer")
    current_q = data.get("current_question", 1)
    history = data.get("conversation_history", [])
    analysis_history = data.get("analysis_history", [])
    question_text = data.get("current_question_text")
    answer_stats = data.get("answer_stats", [])
    start_time = data.get("question_start_time", time.time())
    db_session_id = data.get("db_session_id")
    diagnostic_mode = data.get("diagnostic_mode", "full")
    total_questions = data.get("total_questions", FULL_QUESTIONS)
    
    duration = time.time() - start_time
    
    try:
        # 1. Анализируем ответ
        analysis = await analyze_answer(question_text, answer_text, data["role"])
        
        # Обновляем статистику
        stats_entry = {
            "question": current_q,
            "length": len(answer_text),
            "duration_sec": int(duration),
            "scores": analysis.get("scores", {}),
        }
        answer_stats.append(stats_entry)
        
        # Сохраняем в историю
        history.append({
            "question": question_text,
            "answer": answer_text
        })
        
        # Сохраняем анализ (только важные поля)
        analysis_history.append({
            "question": current_q,
            "scores": analysis.get("scores", {}),
            "feedback": analysis.get("feedback", ""),
            "topics": analysis.get("topics", [])
        })
        
        # Сохраняем в БД
        if db_session_id:
            async with get_session() as db:
                # Сохраняем ответ
                await save_answer(
                    db, 
                    db_session_id, 
                    current_q, 
                    question_text, 
                    answer_text, 
                    analysis
                )
                
                # Обновляем прогресс сессии
                await update_session_progress(
                    db,
                    db_session_id,
                    current_q,
                    history,
                    analysis_history
                )
        
        # Показываем прогресс и feedback
        progress_msg = generate_progress_message(
            current_q, 
            total_questions, 
            answer_stats, 
            answer_text
        )
        
        # Редактируем сообщение с анализом на сообщение с прогрессом
        await processing_msg.edit_text(progress_msg)
        
        # Если это был последний вопрос
        if current_q >= total_questions:
            await finish_diagnostic(callback.message, state, data, history, analysis_history, answer_stats)
            return
            
        # 2. Генерируем следующий вопрос
        await safe_send_chat_action(bot, callback.message.chat.id, ChatAction.TYPING)
        
        next_q_num = current_q + 1
        next_question = await generate_question(
            role=data["role"],
            role_name=data.get("role_name", "Специалист"), # Fallback если нет имени роли
            experience=data["experience"],
            question_number=next_q_num,
            conversation_history=history,
            analysis_history=analysis_history
        )
        
        # Обновляем стейт
        await state.update_data(
            current_question=next_q_num,
            current_question_text=next_question,
            conversation_history=history,
            analysis_history=analysis_history,
            answer_stats=answer_stats,
            question_start_time=time.time(),
        )
        
        # Отправляем вопрос
        await callback.message.answer(
            f"{next_q_num}️⃣ <b>Вопрос {next_q_num}/{total_questions}</b>\n\n{next_question}",
            reply_markup=get_question_keyboard(show_skip=False)
        )
        
        # Снова ставим таймер
        db_user_id = data.get("db_user_id")
        await start_reminder(db_user_id, db_session_id)
        
        await state.set_state(DiagnosticStates.answering)
        
    except Exception as e:
        logger.error(f"Error processing answer: {e}", exc_info=True)
        # Возвращаем клавиатуру подтверждения, чтобы юзер мог повторить
        data = await state.get_data()
        draft = data.get("draft_answer", "")
        await callback.message.answer(
            f"<b>Твой ответ:</b>\n\n{draft}\n\n❌ Произошла ошибка при анализе. Попробуем еще раз?",
            reply_markup=get_confirm_answer_keyboard()
        )
        # State остается confirming_answer


@router.message(DiagnosticStates.confirming_answer)
async def handle_text_during_confirmation(message: Message, state: FSMContext):
    """Если юзер пишет текст во время подтверждения — считаем это редактированием."""
    await state.update_data(draft_answer=message.text)
    await message.answer(
        f"<b>Твой новый ответ:</b>\n\n{message.text}\n\nОтправляем?",
        reply_markup=get_confirm_answer_keyboard()
    )


@router.callback_query(F.data == "pause_session")
async def pause_session(callback: CallbackQuery, state: FSMContext):
    """Приостановка диагностики."""
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.message.answer(
        "⏸️ <b>Диагностика приостановлена.</b>\n\n"
        "Мы сохранили твой прогресс. Когда будешь готов продолжить — просто нажми /start или выбери «Продолжить» в меню."
    )
    
    # Сбрасываем стейт, но данные в БД остаются
    await state.clear()


@router.callback_query(DiagnosticStates.confirming_answer, F.data == "edit_answer")
async def edit_answer(callback: CallbackQuery, state: FSMContext):
    """Редактирование ответа (просто просим ввести заново)."""
    await callback.message.edit_text("Хорошо, напиши новый ответ:")
    await state.set_state(DiagnosticStates.answering)


async def finish_diagnostic(message: Message, state: FSMContext, data: dict, history: list, analysis_history: list, answer_stats: list):
    """Завершение диагностики и генерация отчета."""
    # Удаляем таймеры
    db_session_id = data.get("db_session_id")
    user_id = message.from_user.id
    if db_session_id:
        await cancel_reminder(db_session_id)
        
    await message.answer(
        "🎉 <b>Поздравляю! Диагностика завершена.</b>\n\n"
        "Мне нужно немного времени, чтобы проанализировать все ответы и составить твой профиль.\n"
        "Обычно это занимает около 30-60 секунд."
    )
    
    # Анимация генерации
    report_msg = await message.answer("⏳ <b>Генерирую отчет...</b>\n\n<code>░░░░░░░░░░</code> 0%")
    
    try:
        # Расчет баллов
        scores = calculate_category_scores(analysis_history)
        
        # Калибровка (чтобы не было завышенных/заниженных)
        scores = calibrate_scores(scores, data["experience"])
        
        # Обновляем прогресс
        await report_msg.edit_text("⏳ <b>Генерирую отчет...</b>\n\n<code>▓▓▓▓░░░░░░</code> 40%\n<i>Считаю метрики...</i>")
        
        # Генерация текста отчета (Streaming)
        report_text = ""
        chunk_count = 0
        last_update_time = time.time()
        
        try:
            async for chunk in stream_detailed_report(
                role=data["role"],
                role_name=data["role_name"],
                experience=data["experience"],
                conversation_history=history,
                analysis_history=analysis_history
            ):
                report_text += chunk
                chunk_count += 1
                
                # Обновляем статус раз в 2 секунды, чтобы не словить FloodWait
                current_time = time.time()
                if current_time - last_update_time > 2.0:
                    # Эмулируем прогресс от 40% до 90%
                    # Предполагаем средний отчет 3000 символов
                    estimated_pct = min(40 + int((len(report_text) / 3000) * 50), 90)
                    filled = int(estimated_pct / 10)
                    bar = "▓" * filled + "░" * (10 - filled)
                    
                    status_variations = [
                        "<i>Пишу введение...</i>",
                        "<i>Анализирую сильные стороны...</i>",
                        "<i>Формулирую рекомендации...</i>",
                        "<i>Подбираю слова...</i>",
                        "<i>Оформляю выводы...</i>"
                    ]
                    status_text = status_variations[chunk_count % len(status_variations)]
                    
                    try:
                        await report_msg.edit_text(
                            f"⏳ <b>Генерирую отчет...</b>\n\n<code>{bar}</code> {estimated_pct}%\n{status_text}"
                        )
                        last_update_time = current_time
                    except Exception:
                        pass # Игнорируем ошибки редактирования (например, если текст не изменился)
                        
        except Exception as e:
            logger.error(f"Streaming failed, falling back: {e}")
            if not report_text:
                # Если стриминг упал сразу, пробуем обычный метод или fallback
                report_text = await generate_detailed_report(
                    role=data["role"],
                    role_name=data["role_name"],
                    experience=data["experience"],
                    conversation_history=history,
                    analysis_history=analysis_history
                )

        logger.info(f"Report generated. Length: {len(report_text)}")
        
        await report_msg.edit_text("⏳ <b>Генерирую отчет...</b>\n\n<code>▓▓▓▓▓▓▓▓░░</code> 95%\n<i>Финальные штрихи...</i>")
        
        # Сохраняем результаты в БД
        benchmark_summary = ""
        if db_session_id:
            async with get_session() as db:
                await complete_session(
                    db,
                    db_session_id,
                    scores,
                    report_text,
                    history,
                    analysis_history
                )
                
                # Q1 1.4: Real-time Benchmarking
                try:
                    # Получаем бенчмарк
                    benchmark_res = await get_benchmark(
                        session=db,
                        user_score=scores['total'],
                        role=data["role"],
                        role_name=data["role_name"],
                        experience=data["experience"],
                        experience_name=data.get("experience_name", data["experience"]),
                    )
                    
                    if benchmark_res.has_enough_data:
                        best_pct, group = benchmark_res.get_best_percentile()
                        # Формируем краткую строку для саммари
                        benchmark_summary = f"\n📊 <b>Топ-{100 - best_pct}%</b> среди {group}"
                        
                        # Также можно добавить инсайт, если он есть
                        if benchmark_res.insights:
                            benchmark_summary += f"\n<i>{benchmark_res.insights[0]}</i>"
                            
                except Exception as e:
                    logger.error(f"Failed to get benchmark: {e}")
        
        # Добавляем ачивки
        achievements = generate_final_achievements(answer_stats)
        
        # Отправляем отчет (разбиваем, если длинный)
        await report_msg.delete()
        
        # Красивое саммари перед отчетом
        summary = (
            f"✅ <b>Твой результат готов!</b>\n\n"
            f"Role: <b>{data['role_name']}</b>\n"
            f"Level: <b>{data.get('experience_name', data['experience'])}</b>\n"
            f"Total Score: <b>{scores['total']}/100</b>"
            f"{benchmark_summary}\n"
            f"{achievements}\n\n"
            f"👇 Твой подробный отчет ниже"
        )
        
        await message.answer(summary)
        
        # Отправляем сам отчет
        # Используем message_splitter для надежности
        await send_long_message(message.bot, message.chat.id, report_text)
        
        # Предлагаем следующие шаги
        await message.answer(
            "Что делать дальше?",
            reply_markup=get_post_diagnostic_keyboard()
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        # Fallback отчет
        if 'scores' not in locals():
            try:
                scores = calculate_category_scores(analysis_history)
            except:
                scores = {'total': 0, 'hard_skills': 0, 'soft_skills': 0, 'thinking': 0, 'mindset': 0}
        
        all_insights = []
        all_gaps = []
        if analysis_history:
            for analysis in analysis_history:
                all_insights.extend(analysis.get("key_insights", []))
                all_gaps.extend(analysis.get("gaps", []))

        fallback_report = generate_fallback_report(
            role_name=data.get("role_name", "Specialist"),
            experience=data.get("experience", "Middle"),
            scores=scores,
            insights=all_insights,
            gaps=all_gaps
        )
        await message.answer(
            f"Не удалось сгенерировать полный отчет, но вот твои баллы:\n\n{fallback_report}",
            reply_markup=get_post_diagnostic_keyboard()
        )
        await state.clear()


@router.message()
async def handle_unknown_message(message: Message, state: FSMContext):
    """
    Catch-all обработчик для сообщений, которые не попали в другие хендлеры.
    Особенно полезен при потере контекста (перезапуск бота).
    """
    # Игнорируем команды (они должны обрабатываться своими хендлерами)
    # Или если сообщение пустое (например, стикер без текста)
    if not message.text or message.text.startswith("/"):
        return

    user_id = message.from_user.id
    current_state = await state.get_state()
    logger.info(f"handle_unknown_message triggered for {user_id}. State: {current_state}")
    
    try:
        async with get_session() as db:
            # Получаем пользователя из БД (или создаем, чтобы получить ID)
            # Это безопасно, так как user_id уникален
            user = await get_or_create_user(
                session=db,
                telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
            
            # Проверяем активную сессию
            active_session = await get_active_session(db, user.id)
            
            if active_session:
                # Восстанавливаем контекст, чтобы кнопка сработала
                await state.set_state(DiagnosticStates.session_recovery)
                
                await message.answer(
                    "⚠️ <b>Я потерял нить разговора (возможно, меня перезапустили).</b>\n\n"
                    "Но я помню, что мы проходили диагностику!\n"
                    "Давай продолжим с последнего вопроса?",
                    reply_markup=get_session_recovery_keyboard(
                        active_session.id, active_session.current_question
                    )
                )
                return

    except Exception as e:
        logger.error(f"Error in catch-all handler: {e}")

    # Если сессии нет или ошибка — стандартный ответ
    await message.answer(
        "🤔 Я не совсем понимаю.\n\n"
        "Если ты хочешь начать диагностику — нажми /start\n"
        "Если возникла проблема — напиши в поддержку."
    )
