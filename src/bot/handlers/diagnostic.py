"""
Обработчик диагностики — flow 10 вопросов с AI.
"""
import logging
import asyncio
import time
import random
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatAction

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
)
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
from src.ai.report_gen import generate_detailed_report, split_message, split_report_into_blocks, sanitize_html
from src.ai.client import AIServiceError
from src.analytics import build_profile, format_profile_text, get_benchmark, format_benchmark_text, build_pdp, format_pdp_text
from src.db import get_session
from src.db.repositories import save_answer, update_session_progress, complete_session, save_feedback, create_session
from src.utils.message_splitter import send_long_message, send_with_continuation

router = Router(name="diagnostic")
logger = logging.getLogger(__name__)

# Количество вопросов в зависимости от режима
FULL_QUESTIONS = 10
DEMO_QUESTIONS = 3
REMINDER_TIMEOUT = 5 * 60  # 5 минут

def get_total_questions(mode: str) -> int:
    """Получить количество вопросов для режима."""
    return DEMO_QUESTIONS if mode == "demo" else FULL_QUESTIONS

# Хранилище таймеров напоминаний {chat_id: asyncio.Task}
_reminder_tasks: dict[int, asyncio.Task] = {}


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


async def _send_reminder(bot: Bot, chat_id: int, question_num: int):
    """Отправляет напоминание через REMINDER_TIMEOUT секунд."""
    try:
        await asyncio.sleep(REMINDER_TIMEOUT)
        await bot.send_message(
            chat_id,
            f"⏰ <b>Напоминание</b>\n\n"
            f"Ты на вопросе {question_num}/{TOTAL_QUESTIONS}.\n"
            f"Можешь продолжить, когда будешь готов!\n\n"
            f"<i>Если нужно время подумать — это нормально 😊</i>",
        )
    except asyncio.CancelledError:
        pass  # Таймер отменён — пользователь ответил
    except Exception as e:
        logger.debug(f"Reminder failed: {e}")


def start_reminder(bot: Bot, chat_id: int, question_num: int):
    """Запускает таймер напоминания."""
    cancel_reminder(chat_id)
    task = asyncio.create_task(_send_reminder(bot, chat_id, question_num))
    _reminder_tasks[chat_id] = task


def cancel_reminder(chat_id: int):
    """Отменяет таймер напоминания."""
    if chat_id in _reminder_tasks:
        _reminder_tasks[chat_id].cancel()
        del _reminder_tasks[chat_id]


@router.callback_query(F.data == "start_diagnostic", DiagnosticStates.ready_to_start)
async def start_diagnostic(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Начало диагностики — первый вопрос."""
    data = await state.get_data()
    user_id = callback.from_user.id
    
    # ==================== ПРОВЕРКА ДОСТУПА ====================
    async with get_session() as db:
        access = await balance_repo.check_diagnostic_access(db, user_id)
    
    if not access.allowed:
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
    
    # Списываем диагностику с баланса
    async with get_session() as db:
        await balance_repo.use_diagnostic(db, user_id, diagnostic_mode)
    
    # ==================== СОЗДАНИЕ СЕССИИ ====================
    db_session_id = None
    try:
        async with get_session() as db:
            diagnostic_session = await create_session(
                session=db,
                user_id=user_id,
                role=data["role"],
                role_name=data["role_name"],
                experience=data["experience"],
                experience_name=data["experience_name"],
                mode=diagnostic_mode,  # Сохраняем режим
            )
            db_session_id = diagnostic_session.id
            logger.info(f"Created {diagnostic_mode} session {db_session_id} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to create session in DB: {e}")
    
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
        loading_msg = await callback.message.edit_text(
            "🚀 <b>Запускаю диагностику...</b>"
        )
        await asyncio.sleep(0.5)  # Минимальная задержка для UX
        question = cached_question
        logger.info(f"Using cached first question for {data['role']}/{data['experience']}")
    else:
        # Кэш не найден — генерируем через AI с анимацией
        loading_msg = await callback.message.edit_text(
            "🧠 <b>Подготавливаю диагностику...</b>\n\n<code>░░░░░░░░░░</code> 0%"
        )
        
        async def animate_first_question():
            states = [
                ("▓▓░░░░░░░░", "20%", "Анализирую профиль..."),
                ("▓▓▓▓░░░░░░", "40%", "Формирую стратегию..."),
                ("▓▓▓▓▓▓░░░░", "60%", "Генерирую вопрос..."),
                ("▓▓▓▓▓▓▓▓░░", "80%", "Оптимизирую..."),
            ]
            try:
                for bar, pct, status in states:
                    await asyncio.sleep(1.5)
                    await safe_send_chat_action(bot, callback.message.chat.id, ChatAction.TYPING)
                    try:
                        await loading_msg.edit_text(
                            f"🧠 <b>{status}</b>\n\n<code>{bar}</code> {pct}"
                        )
                    except Exception:
                        pass
            except asyncio.CancelledError:
                pass
        
        anim_task = asyncio.create_task(animate_first_question())
        
        question = await generate_question(
            role=data["role"],
            role_name=data["role_name"],
            experience=data["experience_name"],
            question_number=1,
            conversation_history=[],
            analysis_history=[],
        )
        
        anim_task.cancel()
        try:
            await anim_task
        except asyncio.CancelledError:
            pass
    
    await state.update_data(current_question_text=question)
    
    # Для демо показываем другой текст
    demo_note = "\n\n<i>🎁 Демо-версия: 3 вопроса</i>" if diagnostic_mode == "demo" else ""
    
    await callback.message.edit_text(
        f"<b>Вопрос 1/{total_questions}</b>\n\n{question}{demo_note}",
    )
    await state.set_state(DiagnosticStates.answering)
    await callback.answer()
    
    # Запускаем таймер напоминания
    start_reminder(bot, callback.message.chat.id, 1)


MIN_ANSWER_LENGTH = 50  # Минимальная длина ответа (для точной оценки)
MAX_ANSWER_LENGTH = 4000  # Максимальная длина (TG лимит 4096, с запасом)


@router.message(DiagnosticStates.answering)
async def capture_answer(message: Message, state: FSMContext):
    """Захват ответа и показ preview для подтверждения."""
    # Отменяем таймер напоминания
    cancel_reminder(message.chat.id)
    
    # Проверяем тип контента и даём подсказку
    if message.photo:
        await message.answer(
            "🖼️ Вижу картинку!\n\n"
            "Пока я не умею анализировать изображения.\n"
            "<b>Опиши словами то, что хотел показать</b> — "
            "например, расскажи о проекте с этого скриншота."
        )
        return
    
    if message.sticker:
        await message.answer(
            "😊 Классный стикер!\n\n"
            "Но для диагностики мне нужен текстовый ответ.\n"
            "<b>Расскажи развёрнуто</b> — это поможет точнее оценить твой уровень."
        )
        return
    
    if message.document:
        await message.answer(
            "📎 Вижу документ!\n\n"
            "Пока я не умею читать файлы.\n"
            "<b>Опиши ключевые моменты текстом</b> — "
            "что за проект, какие задачи решал, какой результат?"
        )
        return
    
    if message.video or message.video_note:
        await message.answer(
            "🎥 Вижу видео!\n\n"
            "Пока я не умею анализировать видео.\n"
            "<b>Расскажи текстом или голосом</b> — это тоже работает!"
        )
        return
    
    if message.animation:  # GIF
        await message.answer(
            "🎬 Крутая гифка!\n\n"
            "Но для диагностики нужен текстовый ответ.\n"
            "<b>Опиши свою мысль словами</b> 😊"
        )
        return
    
    if message.contact or message.location:
        await message.answer(
            "📍 Это интересно, но для диагностики нужен текстовый ответ.\n\n"
            "<b>Расскажи о своём опыте словами</b> — чем подробнее, тем лучше!"
        )
        return
    
    if not message.text:
        await message.answer(
            "📝 Для диагностики нужен текстовый ответ.\n\n"
            "<i>Голосовые сообщения тоже поддерживаются!</i>"
        )
        return
    
    # Проверяем, не отправлена ли только ссылка
    import re
    text_stripped = message.text.strip()
    url_pattern = r'^https?://\S+$'
    if re.match(url_pattern, text_stripped):
        await message.answer(
            "🔗 Вижу ссылку!\n\n"
            "Я пока не умею открывать страницы.\n"
            "<b>Расскажи о проекте своими словами:</b>\n"
            "• Что это за проект?\n"
            "• Какую задачу решал?\n"
            "• Какой был результат?"
        )
        return
    
    # Проверяем длину ответа
    if len(text_stripped) < MIN_ANSWER_LENGTH:
        await message.answer(
            f"💡 <b>Ответ слишком короткий</b> ({len(text_stripped)}/{MIN_ANSWER_LENGTH} символов)\n\n"
            "Для точной оценки нужны развёрнутые ответы.\n"
            "Расскажи подробнее — <b>минимум 2-3 предложения</b>.\n\n"
            "<i>Совет: опиши конкретную ситуацию, что делал, какой результат.</i>"
        )
        return
    
    # Проверяем максимальную длину (TG лимит)
    if len(text_stripped) > MAX_ANSWER_LENGTH:
        await message.answer(
            f"📏 <b>Ответ слишком длинный!</b>\n\n"
            f"Сейчас: {len(text_stripped)} символов\n"
            f"Максимум: {MAX_ANSWER_LENGTH} символов\n\n"
            "Попробуй сократить ответ — оставь самое важное.\n"
            "<i>Совет: лучше глубина, чем объём!</i>"
        )
        return
    
    # Сохраняем черновик ответа
    answer_text = message.text.strip()
    await state.update_data(draft_answer=answer_text)
    
    # Показываем preview с кнопками подтверждения
    preview_text = answer_text[:300] + "..." if len(answer_text) > 300 else answer_text
    
    # Typing hint по длине ответа
    typing_hint = get_typing_hint(len(answer_text))
    
    await message.answer(
        f"📝 <b>Твой ответ:</b>\n\n"
        f"<i>{preview_text}</i>\n\n"
        f"{typing_hint}\n"
        f"Отправить этот ответ?",
        reply_markup=get_pause_keyboard(),
    )
    await state.set_state(DiagnosticStates.confirming_answer)


@router.message(DiagnosticStates.confirming_answer)
async def handle_new_answer_while_confirming(message: Message, state: FSMContext):
    """Обработка нового текста во время подтверждения — обновляем черновик."""
    if not message.text:
        return
    
    answer_text = message.text.strip()
    
    # Проверяем максимальную длину
    if len(answer_text) > MAX_ANSWER_LENGTH:
        await message.answer(
            f"📏 <b>Ответ слишком длинный!</b>\n\n"
            f"Сейчас: {len(answer_text)} символов\n"
            f"Максимум: {MAX_ANSWER_LENGTH} символов\n\n"
            "Попробуй сократить ответ — оставь самое важное."
        )
        return
    
    # Обновляем черновик
    await state.update_data(draft_answer=answer_text)
    
    preview_text = answer_text[:300] + "..." if len(answer_text) > 300 else answer_text
    
    # Typing hint по длине ответа
    typing_hint = get_typing_hint(len(answer_text))
    
    await message.answer(
        f"📝 <b>Обновлённый ответ:</b>\n\n"
        f"<i>{preview_text}</i>\n\n"
        f"{typing_hint}\n"
        f"Отправить этот ответ?",
        reply_markup=get_pause_keyboard(),
    )


@router.callback_query(F.data == "edit_answer", DiagnosticStates.confirming_answer)
async def edit_answer(callback: CallbackQuery, state: FSMContext):
    """Возврат к редактированию ответа."""
    data = await state.get_data()
    current = data.get("current_question", 1)
    question = data.get("current_question_text", "")
    total = data.get("total_questions", FULL_QUESTIONS)
    
    await callback.message.edit_text(
        f"<b>Вопрос {current}/{total}</b>\n\n{question}\n\n"
        f"✏️ <i>Введи новый ответ:</i>"
    )
    await state.set_state(DiagnosticStates.answering)
    await callback.answer("Введи новый ответ")


@router.callback_query(F.data == "pause_session", DiagnosticStates.confirming_answer)
async def pause_session(callback: CallbackQuery, state: FSMContext):
    """Пауза диагностики — сохраняем и выходим."""
    from src.db import get_session
    from src.db.repositories import update_session_progress
    
    data = await state.get_data()
    current = data.get("current_question", 1)
    db_session_id = data.get("db_session_id")
    conversation_history = data.get("conversation_history", [])
    analysis_history = data.get("analysis_history", [])
    
    # Сохраняем прогресс в БД
    if db_session_id:
        try:
            async with get_session() as db:
                await update_session_progress(
                    session=db,
                    session_id=db_session_id,
                    current_question=current,
                    conversation_history=conversation_history,
                    analysis_history=analysis_history,
                )
                logger.info(f"Session {db_session_id} paused at question {current}")
        except Exception as e:
            logger.error(f"Failed to save pause state: {e}")
    
    # Отменяем таймер напоминания
    cancel_reminder(callback.message.chat.id)
    
    await callback.message.edit_text(
        f"⏸️ <b>Диагностика на паузе</b>\n\n"
        f"Прогресс: <b>{current - 1}/10</b> вопросов\n"
        f"Сессия сохранена!\n\n"
        f"Напиши /start когда будешь готов продолжить.\n"
        f"<i>Сессия активна 24 часа.</i>",
    )
    
    await state.set_state(DiagnosticStates.paused)
    await callback.answer("⏸️ Сохранено!")


@router.callback_query(F.data == "retry_analysis")
async def retry_analysis(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Повторная попытка анализа после ошибки."""
    data = await state.get_data()
    
    # Проверяем, есть ли сохранённый ответ
    draft_answer = data.get("draft_answer")
    if not draft_answer:
        await callback.answer("❌ Ответ не найден. Начни заново.", show_alert=True)
        return
    
    # Устанавливаем состояние и запускаем confirm_answer
    await state.set_state(DiagnosticStates.confirming_answer)
    
    # Меняем callback_data и вызываем confirm_answer
    callback.data = "confirm_answer"
    await confirm_answer(callback, state, bot)


@router.callback_query(F.data == "wait_more")
async def wait_more(callback: CallbackQuery):
    """Пользователь хочет подождать ещё."""
    await callback.answer(
        "⏳ Хорошо, подождём ещё немного...\n"
        "Если через минуту не появится результат — нажми 🔄 Повторить",
        show_alert=True,
    )


@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена текущего действия."""
    data = await state.get_data()
    current = data.get("current_question", 1)
    question = data.get("current_question_text", "")
    
    await callback.message.edit_text(
        f"❌ Действие отменено.\n\n"
        f"<b>Вопрос {current}/10:</b>\n{question}\n\n"
        f"Отправь свой ответ текстом или голосовым.",
    )
    
    await state.set_state(DiagnosticStates.answering)
    await callback.answer()


@router.callback_query(F.data == "confirm_answer", DiagnosticStates.confirming_answer)
async def confirm_answer(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение ответа — запускаем анализ."""
    from aiogram.enums import ChatAction
    
    data = await state.get_data()
    current = data["current_question"]
    answer_text = data.get("draft_answer", "")
    
    # Трекинг времени ответа
    question_start_time = data.get("question_start_time", time.time())
    answer_duration = time.time() - question_start_time
    
    # Сохраняем статистику ответов
    answer_stats = data.get("answer_stats", [])
    answer_stats.append({
        "question": current,
        "duration_sec": answer_duration,
        "length": len(answer_text),
    })
    await state.update_data(answer_stats=answer_stats)
    
    if not answer_text:
        await callback.answer("❌ Ответ не найден", show_alert=True)
        return
    
    await callback.answer("✅ Анализирую...")
    
    # Показываем typing indicator
    await safe_send_chat_action(bot, callback.message.chat.id, ChatAction.TYPING)
    
    total = data.get("total_questions", FULL_QUESTIONS)
    
    # Показываем, что анализируем с прогрессом
    thinking_msg = await callback.message.edit_text(
        f"🧠 Анализирую ответ {current}/{total}...\n\n<code>▓░░░░░░░░░</code> 10%"
    )
    
    # Сохраняем ответ
    conversation_history = data.get("conversation_history", [])
    analysis_history = data.get("analysis_history", [])
    
    current_question = data.get("current_question_text", f"Вопрос {current}")
    
    conversation_history.append({
        "question": current_question,
        "answer": answer_text,
    })
    
    # Подготавливаем данные
    db_session_id = data.get("db_session_id")
    next_question_num = current + 1
    start_time = time.perf_counter()
    
    # === УЛУЧШЕННЫЙ ПРОГРЕСС-БАР ===
    async def update_progress():
        """Обновляет прогресс-бар во время AI запросов с анимацией."""
        is_last_question = current >= total
        
        # Разные этапы для разных действий
        progress_states = [
            ("▓░░░░░░░░░", "10%", "Читаю ответ..."),
            ("▓▓░░░░░░░░", "20%", "Анализирую глубину..."),
            ("▓▓▓░░░░░░░", "30%", "Оцениваю структуру..."),
            ("▓▓▓▓░░░░░░", "40%", "Выявляю инсайты..."),
            ("▓▓▓▓▓░░░░░", "50%", "Формирую оценку..."),
            ("▓▓▓▓▓▓░░░░", "60%", "Сопоставляю с метриками..."),
        ]
        
        # Добавляем финальные шаги в зависимости от контекста
        if is_last_question:
            progress_states.extend([
                ("▓▓▓▓▓▓▓░░░", "70%", "Подготавливаю результаты..."),
                ("▓▓▓▓▓▓▓▓░░", "80%", "Финализирую анализ..."),
                ("▓▓▓▓▓▓▓▓▓░", "90%", "Почти готово..."),
            ])
        else:
            progress_states.extend([
                ("▓▓▓▓▓▓▓░░░", "70%", "Генерирую следующий вопрос..."),
                ("▓▓▓▓▓▓▓▓░░", "80%", "Оптимизирую формулировку..."),
                ("▓▓▓▓▓▓▓▓▓░", "90%", "Почти готово..."),
            ])
        
        chat_id = callback.message.chat.id
        try:
            for bar, pct, status in progress_states:
                await asyncio.sleep(1.5)  # Быстрее обновляем
                await safe_send_chat_action(bot, chat_id, ChatAction.TYPING)
                try:
                    await thinking_msg.edit_text(
                        f"🧠 <b>{status}</b>\n\n<code>{bar}</code> {pct}"
                    )
                except Exception:
                    pass
        except asyncio.CancelledError:
            pass
    
    # Запускаем прогресс-бар в фоне
    progress_task = asyncio.create_task(update_progress())
    
    # === ПАРАЛЛЕЛЬНЫЕ AI-ЗАПРОСЫ ===
    # Запускаем анализ ответа и генерацию следующего вопроса одновременно
    ai_had_issues = False  # Флаг для уведомления пользователя
    
    async def _analyze():
        """Анализ текущего ответа."""
        nonlocal ai_had_issues
        try:
            return await analyze_answer(
                question=current_question,
                answer=answer_text,
                role=data["role"],
            )
        except AIServiceError as e:
            logger.error(f"AI service error during analysis: {e}")
            ai_had_issues = True
            return {
                "scores": {"depth": 5, "self_awareness": 5, "structure": 5, "honesty": 5, "expertise": 5},
                "key_insights": ["⚠️ Анализ выполнен с ограничениями"],
                "gaps": [],
                "hypothesis": "AI временно недоступен",
                "_ai_error": True,
            }
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {
                "scores": {"depth": 5, "self_awareness": 5, "structure": 5, "honesty": 5, "expertise": 5},
                "key_insights": [],
                "gaps": [],
                "hypothesis": "Анализ недоступен",
            }
    
    async def _generate_next():
        """Генерация следующего вопроса (если нужен)."""
        nonlocal ai_had_issues
        if next_question_num > total:
            return None
        try:
            return await generate_question(
                role=data["role"],
                role_name=data["role_name"],
                experience=data["experience_name"],
                question_number=next_question_num,
                conversation_history=conversation_history,
                analysis_history=analysis_history,
            )
        except AIServiceError as e:
            logger.error(f"AI service error during question gen: {e}")
            ai_had_issues = True
            # Fallback вопросы
            fallback_questions = [
                "Расскажи о сложном проекте, где тебе пришлось принимать нестандартные решения.",
                "Как ты справляешься с дедлайнами и приоритизацией задач?",
                "Опиши ситуацию, когда тебе приходилось работать с неопределённостью.",
                "Что для тебя означает качественная работа?",
                "Расскажи о своём подходе к обучению новым навыкам.",
            ]
            idx = (next_question_num - 1) % len(fallback_questions)
            return fallback_questions[idx]
        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            return f"Вопрос {next_question_num}: Расскажи подробнее о своём опыте и подходе к работе."
    
    # === ПОСЛЕДОВАТЕЛЬНЫЙ ЗАПУСК (качество > скорость) ===
    # 1. Сначала анализируем текущий ответ
    # 2. Добавляем анализ в историю
    # 3. Генерируем следующий вопрос с ПОЛНЫМ контекстом
    # AI видит и ответ, и его анализ (скоры, инсайты, gaps) — максимальная адаптивность
    
    analyze_start = time.perf_counter()
    analysis = await _analyze()
    analyze_ms = (time.perf_counter() - analyze_start) * 1000
    logger.info(f"[PERF] Q{current}: analyze done in {analyze_ms:.0f}ms")
    
    # Добавляем анализ в историю ПЕРЕД генерацией следующего вопроса
    analysis_history.append(analysis)
    
    if next_question_num <= total:
        gen_start = time.perf_counter()
        next_question = await _generate_next()
        gen_ms = (time.perf_counter() - gen_start) * 1000
        logger.info(f"[PERF] Q{current}: generate done in {gen_ms:.0f}ms (total: {analyze_ms + gen_ms:.0f}ms)")
    else:
        next_question = None
    
    # Убираем из history (добавится в правильном месте ниже)
    analysis_history.pop()
    
    # Останавливаем прогресс-бар
    progress_task.cancel()
    try:
        await progress_task
    except asyncio.CancelledError:
        pass
    
    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"Answer {current} processed: {analysis.get('scores', {})} | {duration_ms:.0f}ms total")
    
    # Уведомляем пользователя о проблемах с AI (если были)
    if ai_had_issues:
        try:
            from src.utils.error_recovery import get_error_message, ErrorType
            from src.bot.keyboards.inline import get_error_retry_keyboard
            
            # Показываем информативное сообщение
            await callback.message.answer(
                "⚠️ <b>AI работает в упрощённом режиме</b>\n\n"
                "<i>Сервис временно перегружен, но диагностика продолжается.\n"
                "Результаты могут быть менее точными.</i>\n\n"
                "💡 Если хочешь получить полный анализ — попробуй позже.",
            )
        except Exception:
            pass
    
    analysis_history.append(analysis)
    
    # Сохраняем ответ в БД
    if db_session_id:
        try:
            async with get_session() as db:
                await save_answer(
                    session=db,
                    diagnostic_session_id=db_session_id,
                    question_number=current,
                    question_text=current_question,
                    answer_text=answer_text,
                    analysis=analysis,
                )
        except Exception as e:
            logger.error(f"Failed to save answer to DB: {e}")
    
    # Проверяем, есть ли ещё вопросы
    if next_question_num <= total:
        
        await state.update_data(
            current_question=next_question_num,
            current_question_text=next_question,
            conversation_history=conversation_history,
            analysis_history=analysis_history,
            question_start_time=time.time(),  # Трекаем время для следующего вопроса
        )
        
        # Сохраняем прогресс в БД
        if db_session_id:
            try:
                async with get_session() as db:
                    await update_session_progress(
                        session=db,
                        session_id=db_session_id,
                        current_question=next_question_num,
                        conversation_history=conversation_history,
                        analysis_history=analysis_history,
                    )
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")
        
        # === PROGRESS & GAMIFICATION ===
        progress_msg = generate_progress_message(
            current_question=current,
            total_questions=total,
            answer_stats=data.get("answer_stats", []),
            answer_text=answer_text,
        )
        
        # Показываем прогресс
        await thinking_msg.edit_text(progress_msg)
        await asyncio.sleep(1.5)  # Даём время прочитать
        
        # Показываем следующий вопрос
        await callback.message.answer(
            f"<b>Вопрос {next_question_num}/{total}</b>\n\n{next_question}",
        )
        await state.set_state(DiagnosticStates.answering)
        
        # Запускаем таймер напоминания для следующего вопроса
        start_reminder(bot, callback.message.chat.id, next_question_num)
    else:
        # Все вопросы заданы — генерируем детальный отчёт
        cancel_reminder(callback.message.chat.id)  # Отменяем таймер
        from aiogram.enums import ChatAction
        
        # Устанавливаем state generating_report для защиты от race condition
        await state.set_state(DiagnosticStates.generating_report)
        
        await state.update_data(
            conversation_history=conversation_history,
            analysis_history=analysis_history,
        )
        
        # === ФИНАЛЬНЫЕ ACHIEVEMENTS ===
        final_stats = data.get("answer_stats", [])
        achievements = generate_final_achievements(final_stats)
        
        # Показываем итоговый прогресс и достижения
        await thinking_msg.edit_text(
            "🎉 <b>Диагностика завершена!</b>\n\n"
            "<code>██████████</code> 100%\n"
            f"{achievements}"
        )
        await asyncio.sleep(2)  # Даём прочитать достижения
        
        # Теперь генерируем отчёт
        report_msg = await callback.message.answer(
            "📊 <b>Генерирую детальный AI-отчёт...</b>\n\n"
            "<code>▓░░░░░░░░░</code> 10%\n\n"
            "<i>Анализирую все 10 ответов...</i>"
        )
        
        # Улучшенный прогресс-бар для отчёта
        async def report_progress():
            progress_states = [
                ("▓░░░░░░░░░", "10%", "Собираю данные диагностики..."),
                ("▓▓░░░░░░░░", "20%", "Анализирую 10 ответов..."),
                ("▓▓▓░░░░░░░", "30%", "Выявляю паттерны..."),
                ("▓▓▓▓░░░░░░", "40%", "Вычисляю 12 метрик..."),
                ("▓▓▓▓▓░░░░░", "50%", "Формирую профиль..."),
                ("▓▓▓▓▓▓░░░░", "60%", "Генерирую рекомендации..."),
                ("▓▓▓▓▓▓▓░░░", "70%", "Составляю план развития..."),
                ("▓▓▓▓▓▓▓▓░░", "80%", "Сравниваю с рынком..."),
                ("▓▓▓▓▓▓▓▓▓░", "90%", "Финализирую отчёт..."),
            ]
            try:
                for bar, pct, status in progress_states:
                    await asyncio.sleep(2)  # Быстрее обновляем
                    await safe_send_chat_action(bot, callback.message.chat.id, ChatAction.TYPING)
                    try:
                        await report_msg.edit_text(
                            f"📊 <b>{status}</b>\n\n<code>{bar}</code> {pct}"
                        )
                    except Exception:
                        pass
            except asyncio.CancelledError:
                pass
        
        report_task = asyncio.create_task(report_progress())
        
        # Генерируем детальный отчёт через AI
        report = ""
        try:
            report = await generate_detailed_report(
                role=data["role"],
                role_name=data["role_name"],
                experience=data["experience_name"],
                conversation_history=conversation_history,
                analysis_history=analysis_history,
            )
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            # Fallback на базовый отчёт
            report = await generate_basic_report(data, conversation_history, analysis_history)
        
        # Останавливаем прогресс-бар отчёта
        report_task.cancel()
        try:
            await report_task
        except asyncio.CancelledError:
            pass
        
        # Удаляем сообщение с прогресс-баром отчёта
        try:
            await report_msg.delete()
        except Exception:
            pass  # Сообщение уже удалено или недоступно
        
        # Рассчитываем баллы и калибруем по опыту
        raw_scores = calculate_category_scores(analysis_history)
        scores = calibrate_scores(raw_scores, data.get("experience", "middle"))
        
        # Строим профиль компетенций
        profile = build_profile(
            role=data["role"],
            role_name=data["role_name"],
            experience=data.get("experience", "middle"),
            experience_name=data.get("experience_name", ""),
            scores=scores,
            analysis_history=analysis_history,
        )
        profile_text = format_profile_text(profile)
        
        # Строим PDP
        raw_averages = scores.get("raw_averages", {})
        pdp = build_pdp(
            role=data["role"],
            role_name=data["role_name"],
            experience=data.get("experience", "middle"),
            experience_name=data.get("experience_name", ""),
            total_score=scores["total"],
            raw_averages=raw_averages,
            strengths=profile.strengths,
        )
        pdp_text = format_pdp_text(pdp)
        
        # Сохраняем результат в БД
        header = generate_score_header(data, scores)
        full_report = header + "\n\n" + report
        if db_session_id:
            try:
                async with get_session() as db:
                    await complete_session(
                        session=db,
                        session_id=db_session_id,
                        scores=scores,
                        report=full_report,
                        conversation_history=conversation_history,
                        analysis_history=analysis_history,
                    )
                    logger.info(f"Session {db_session_id} completed with score {scores['total']}")
                    
                    # Планируем напоминание о повторной диагностике через 30 дней
                    try:
                        from src.db.repositories.reminder_repo import schedule_diagnostic_reminder, get_or_create_user_settings
                        
                        user_settings = await get_or_create_user_settings(db, db_user_id)
                        
                        if user_settings.diagnostic_reminders_enabled:
                            # Определяем главную зону роста
                            focus_skill = None
                            if raw_averages:
                                sorted_gaps = sorted(raw_averages.items(), key=lambda x: x[1])
                                if sorted_gaps:
                                    focus_skill = sorted_gaps[0][0]  # Метрика с самым низким баллом
                            
                            await schedule_diagnostic_reminder(
                                session=db,
                                user_id=db_user_id,
                                session_id=db_session_id,
                                last_score=scores['total'],
                                focus_skill=focus_skill,
                                days_delay=30,
                            )
                            logger.info(f"Scheduled reminder for user {db_user_id} in 30 days")
                    except Exception as re:
                        logger.warning(f"Failed to schedule reminder: {re}")
                    
            except Exception as e:
                logger.error(f"Failed to complete session: {e}")
        
        # === СОХРАНЯЕМ ВСЕ ДАННЫЕ В STATE ДЛЯ ЛЕНИВОЙ ЗАГРУЗКИ ===
        await state.update_data(
            result_report=report,
            result_profile=profile_text,
            result_pdp=pdp_text,
            result_scores=scores,
            result_header=header,
        )
        await state.set_state(DiagnosticStates.finished)
        
        # === ДИАГНОСТИКА: ЛОГИРУЕМ ДЛИНЫ ВСЕХ СЕКЦИЙ ===
        logger.info(
            f"[MSG_LEN] Generated results for user {callback.from_user.id}: "
            f"header={len(header)}, report={len(report)}, "
            f"profile={len(profile_text)}, pdp={len(pdp_text)}, "
            f"summary={len(generate_summary_card(data, scores, profile))}"
        )
        
        # === ДЕМО VS ПОЛНАЯ ВЕРСИЯ ===
        diagnostic_mode = data.get("diagnostic_mode", "full")
        
        if diagnostic_mode == "demo":
            # ДЕМО: Урезанный отчёт + paywall
            demo_summary = generate_demo_summary_card(data, scores, profile)
            await thinking_msg.edit_text(demo_summary, reply_markup=get_demo_result_keyboard())
            logger.info(f"Demo diagnostic completed for user {callback.from_user.id}")
        else:
            # ПОЛНАЯ ВЕРСИЯ: Summary Card
            summary_card = generate_summary_card(data, scores, profile)
            
            # Выбираем клавиатуру
            if db_session_id:
                keyboard = get_result_summary_keyboard(db_session_id)
            else:
                keyboard = get_restart_keyboard()
            
            await thinking_msg.edit_text(summary_card, reply_markup=keyboard)
            
            # === ОТЛОЖЕННЫЙ FEEDBACK (через 3 минуты) ===
            asyncio.create_task(_send_delayed_feedback(bot, callback.message.chat.id, db_session_id))


# === ХРАНИЛИЩЕ ТАЙМЕРОВ FEEDBACK ===
_feedback_tasks: dict[int, asyncio.Task] = {}


async def _send_delayed_feedback(bot: Bot, chat_id: int, session_id: int | None):
    """Отправляет запрос feedback через 3 минуты."""
    try:
        await asyncio.sleep(180)  # 3 минуты
        await bot.send_message(
            chat_id,
            "💭 <b>Как тебе диагностика?</b>\n\n"
            "Твой отзыв поможет сделать её лучше!",
            reply_markup=get_delayed_feedback_keyboard(),
        )
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Delayed feedback failed: {e}")


def generate_summary_card(data: dict, scores: dict, profile) -> str:
    """
    Генерация красивой Summary Card — один экран с ключевым результатом.
    
    Не спамим 6 сообщений, а показываем главное:
    - Общий балл и уровень
    - Топ-3 сильных стороны (кратко)
    - Топ-3 зоны роста (кратко)
    - Призыв к действию
    """
    total = scores["total"]
    
    # Уровень с эмодзи
    if total >= 80:
        level = "🏆 Senior / Lead"
        level_comment = "Впечатляющий результат!"
    elif total >= 60:
        level = "💪 Middle+"
        level_comment = "Отличный уровень!"
    elif total >= 40:
        level = "📈 Middle"
        level_comment = "Хорошая база для роста!"
    elif total >= 25:
        level = "🌱 Junior+"
        level_comment = "Есть потенциал!"
    else:
        level = "🌱 Junior"
        level_comment = "Начало пути!"
    
    # Прогресс-бар
    filled = int(total / 4)  # 25 символов для 100 баллов
    bar = "█" * filled + "░" * (25 - filled)
    
    # Сильные стороны (кратко)
    strengths = [METRIC_NAMES_RU.get(s, s) for s in profile.strengths[:3]]
    strengths_text = " • ".join(strengths) if strengths else "—"
    
    # Зоны роста (кратко)
    growth = [METRIC_NAMES_RU.get(g, g) for g in profile.growth_areas[:3]]
    growth_text = " • ".join(growth) if growth else "—"
    
    # Баллы по категориям
    hs = scores.get("hard_skills", 0)
    ss = scores.get("soft_skills", 0)
    th = scores.get("thinking", 0)
    ms = scores.get("mindset", 0)
    
    return f"""🎯 <b>ДИАГНОСТИКА ЗАВЕРШЕНА</b>

<b>{data['role_name']}</b> • {data['experience_name']}

━━━━━━━━━━━━━━━━━━━━

<b>📊 ОБЩИЙ БАЛЛ: {total}/100</b>
<code>{bar}</code>
{level} — {level_comment}

━━━━━━━━━━━━━━━━━━━━

<b>По категориям:</b>
🔧 Hard Skills: {hs}/30
🗣 Soft Skills: {ss}/25
🧠 Thinking: {th}/25
💡 Mindset: {ms}/20

━━━━━━━━━━━━━━━━━━━━

<b>💪 Сильные стороны:</b>
{strengths_text}

<b>📈 Фокус на развитие:</b>
{growth_text}

━━━━━━━━━━━━━━━━━━━━

<i>Выбери, что хочешь изучить подробнее:</i>"""


def generate_demo_summary_card(data: dict, scores: dict, profile) -> str:
    """
    Генерация урезанного Demo Summary — побуждает к покупке.
    
    Показываем только:
    - Общий балл
    - 2 метрики (лучшая и худшая)
    - Остальные 10 метрик скрыты
    - Агрессивный CTA
    """
    total = scores["total"]
    
    # Уровень
    if total >= 60:
        level = "💪 Выше среднего"
    elif total >= 40:
        level = "📈 Средний уровень"
    else:
        level = "🌱 Есть над чем работать"
    
    # Прогресс-бар
    filled = int(total / 4)
    bar = "█" * filled + "░" * (25 - filled)
    
    # Только 2 метрики для демо (лучшая и худшая)
    if profile.strengths:
        best_metric = METRIC_NAMES_RU.get(profile.strengths[0], profile.strengths[0])
        best_score = scores.get("raw_averages", {}).get(profile.strengths[0], 7.0)
    else:
        best_metric = "Коммуникация"
        best_score = 7.0
    
    if profile.growth_areas:
        worst_metric = METRIC_NAMES_RU.get(profile.growth_areas[0], profile.growth_areas[0])
        worst_score = scores.get("raw_averages", {}).get(profile.growth_areas[0], 4.5)
    else:
        worst_metric = "Системное мышление"
        worst_score = 4.5
    
    return f"""🎁 <b>ДЕМО-РЕЗУЛЬТАТ</b>

<b>{data['role_name']}</b> • {data['experience_name']}

━━━━━━━━━━━━━━━━━━━━

<b>📊 ОБЩИЙ БАЛЛ: {total}/100</b>
<code>{bar}</code>
{level}

━━━━━━━━━━━━━━━━━━━━

<b>✅ Открытые метрики (2/12):</b>

🟢 {best_metric}: <b>{best_score:.1f}/10</b>
🔴 {worst_metric}: <b>{worst_score:.1f}/10</b>

━━━━━━━━━━━━━━━━━━━━

<b>🔒 Скрытые метрики (10):</b>

├─ Системное мышление: ???
├─ Лидерство: ???
├─ Эмпатия: ???
├─ Критическое мышление: ???
├─ Адаптивность: ???
├─ Навыки презентации: ???
├─ Технические навыки: ???
├─ Управление проектами: ???
├─ Стратегическое видение: ???
└─ Инновационность: ???

━━━━━━━━━━━━━━━━━━━━

<b>🔒 Также недоступно в демо:</b>

├─ 📄 PDF-отчёт уровня McKinsey
├─ 📈 Детальный профиль компетенций
├─ 🎯 30-дневный план развития
└─ 📊 Сравнение с рынком

━━━━━━━━━━━━━━━━━━━━

🔥 <b>Открой полную версию и узнай все 12 метрик!</b>"""


def generate_score_header(data: dict, scores: dict) -> str:
    """Генерация шапки с баллами, калибровкой и детализацией по 12 метрикам."""
    total = scores["total"]
    raw_avg = scores.get("raw_averages", {})
    
    # Калибровка по опыту
    expectation_ru = scores.get("expectation_ru", "")
    expected_total = scores.get("expected_total", 50)
    delta_text = scores.get("delta_text", "0")
    percentile = scores.get("percentile_in_level", 50)
    experience_level = scores.get("experience_level", "Middle")
    
    # Определяем уровень и эмодзи
    if total >= 80:
        level = "🏆 Senior / Lead"
        bar = "█████████████████████████"
    elif total >= 60:
        level = "💪 Middle+"
        bar = "████████████████████░░░░░"
    elif total >= 40:
        level = "📈 Middle"
        bar = "███████████████░░░░░░░░░░"
    elif total >= 25:
        level = "🌱 Junior+"
        bar = "██████████░░░░░░░░░░░░░░░"
    else:
        level = "🌱 Junior"
        bar = "█████░░░░░░░░░░░░░░░░░░░░"
    
    # Генерируем детализацию по категориям
    details = []
    for cat_key, cat_info in METRIC_CATEGORIES.items():
        cat_score = scores.get(cat_key, 0)
        cat_max = cat_info["max_score"]
        details.append(f"\n<b>{cat_info['name']}</b>: {cat_score}/{cat_max}")
        
        # Детализация по метрикам внутри категории
        for metric in cat_info["metrics"]:
            metric_value = raw_avg.get(metric, 5)
            metric_name = METRIC_NAMES_RU.get(metric, metric)
            # Мини-бар для каждой метрики
            filled = int(metric_value)
            mini_bar = "▓" * filled + "░" * (10 - filled)
            details.append(f"  <code>{mini_bar}</code> {metric_name}: {metric_value:.1f}")
    
    details_text = "\n".join(details)
    
    return f"""🎯 <b>ДИАГНОСТИКА ЗАВЕРШЕНА</b>

<b>Профиль:</b> {data['role_name']}
<b>Заявленный опыт:</b> {data['experience_name']}
<b>Выявленный уровень:</b> {level}

<b>📊 ОБЩИЙ БАЛЛ: {total}/100</b>
<code>{bar}</code>

<b>📋 КАЛИБРОВКА ДЛЯ {experience_level.upper()}</b>
{expectation_ru}
• Ожидание для {experience_level}: {expected_total} баллов
• Ваш результат: {total} баллов ({delta_text})
• Перцентиль в группе: топ-{100 - percentile}%

━━━━━━━━━━━━━━━━━━━━

<b>📈 ДЕТАЛИЗАЦИЯ ПО КОМПЕТЕНЦИЯМ</b>
{details_text}

━━━━━━━━━━━━━━━━━━━━

<b>📝 ДЕТАЛЬНЫЙ АНАЛИЗ</b>"""


async def generate_basic_report(
    data: dict,
    conversation_history: list[dict],
    analysis_history: list[dict],
) -> str:
    """
    Fallback отчёт если AI недоступен.
    """
    # Собираем ключевые инсайты
    all_insights = []
    all_gaps = []
    hypotheses = []
    
    for analysis in analysis_history:
        all_insights.extend(analysis.get("key_insights", []))
        all_gaps.extend(analysis.get("gaps", []))
        if analysis.get("hypothesis"):
            hypotheses.append(analysis["hypothesis"])
    
    # Формируем топ инсайтов (убираем дубли)
    unique_insights = list(dict.fromkeys(all_insights))[:5]
    unique_gaps = list(dict.fromkeys(all_gaps))[:3]
    
    insights_text = "\n".join(f"• {i}" for i in unique_insights) if unique_insights else "• Недостаточно данных"
    gaps_text = "\n".join(f"• {g}" for g in unique_gaps) if unique_gaps else "• Не выявлено"
    final_hypothesis = hypotheses[-1] if hypotheses else "Требуется дополнительный анализ"
    
    return f"""<b>💡 Ключевые наблюдения:</b>
{insights_text}

<b>⚠️ Зоны для развития:</b>
{gaps_text}

<b>🔮 Общее впечатление:</b>
{final_hypothesis}

<i>Детальный AI-анализ временно недоступен.</i>"""


# ==================== GENERATING REPORT PROTECTION ====================

@router.message(DiagnosticStates.generating_report)
async def ignore_during_report_generation(message: Message, state: FSMContext):
    """Игнорируем сообщения во время генерации отчёта (защита от race condition)."""
    await message.answer(
        "⏳ <b>Подожди немного!</b>\n\n"
        "Сейчас генерируется твой персональный отчёт.\n"
        "<i>Это займёт ещё 30-60 секунд...</i>"
    )


@router.callback_query(DiagnosticStates.generating_report)
async def ignore_callbacks_during_report(callback: CallbackQuery):
    """Игнорируем callback'и во время генерации отчёта."""
    await callback.answer("⏳ Отчёт генерируется, подожди...", show_alert=False)


# ==================== FEEDBACK HANDLERS ====================

@router.callback_query(F.data.startswith("feedback:"), DiagnosticStates.feedback_rating)
async def process_feedback_rating(callback: CallbackQuery, state: FSMContext):
    """Обработка оценки от пользователя."""
    rating = int(callback.data.split(":")[1])
    
    await state.update_data(feedback_rating=rating)
    
    # Определяем эмодзи по оценке
    if rating >= 9:
        emoji = "🎉"
        reaction = "Супер!"
    elif rating >= 7:
        emoji = "😊"
        reaction = "Отлично!"
    elif rating >= 5:
        emoji = "👍"
        reaction = "Спасибо!"
    else:
        emoji = "🙏"
        reaction = "Спасибо за честность!"
    
    await callback.message.edit_text(
        f"{emoji} <b>{reaction}</b> Ты поставил <b>{rating}/10</b>\n\n"
        f"Хочешь оставить комментарий?\n"
        f"<i>Что понравилось или что улучшить?</i>",
        reply_markup=get_skip_comment_keyboard(),
    )
    await state.set_state(DiagnosticStates.feedback_comment)
    await callback.answer()


@router.message(DiagnosticStates.feedback_comment)
async def process_feedback_comment(message: Message, state: FSMContext):
    """Обработка текстового комментария к feedback."""
    data = await state.get_data()
    rating = data.get("feedback_rating", 5)
    comment = message.text.strip() if message.text else None
    db_session_id = data.get("db_session_id")
    
    # Сохраняем в БД
    if db_session_id:
        try:
            async with get_session() as db:
                await save_feedback(
                    session=db,
                    session_id=db_session_id,
                    rating=rating,
                    comment=comment,
                )
            logger.info(f"Feedback saved: session={db_session_id} rating={rating}")
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
    
    from src.bot.keyboards.inline import get_back_to_menu_keyboard
    await message.answer(
        "✅ <b>Спасибо за обратную связь!</b>\n\n"
        "Твой отзыв поможет улучшить диагностику 💪",
        reply_markup=get_back_to_menu_keyboard(),
    )
    await state.set_state(DiagnosticStates.finished)


@router.callback_query(F.data == "skip_feedback_comment", DiagnosticStates.feedback_comment)
async def skip_feedback_comment(callback: CallbackQuery, state: FSMContext):
    """Пропуск комментария к feedback."""
    data = await state.get_data()
    rating = data.get("feedback_rating", 5)
    db_session_id = data.get("db_session_id")
    
    # Сохраняем в БД (без комментария)
    if db_session_id:
        try:
            async with get_session() as db:
                await save_feedback(
                    session=db,
                    session_id=db_session_id,
                    rating=rating,
                    comment=None,
                )
            logger.info(f"Feedback saved: session={db_session_id} rating={rating}")
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
    
    from src.bot.keyboards.inline import get_back_to_menu_keyboard
    await callback.message.edit_text(
        "✅ <b>Спасибо за оценку!</b>\n\n"
        "Твой отзыв поможет улучшить диагностику 💪",
        reply_markup=get_back_to_menu_keyboard(),
    )
    await state.set_state(DiagnosticStates.finished)
    await callback.answer()


# ==================== STRUCTURED REPORT HANDLERS ====================

@router.callback_query(F.data.startswith("show:report:"))
async def show_detailed_report(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Показать детальный AI-анализ — автоматическое разбиение на части."""
    session_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    
    report = data.get("result_report")
    header = data.get("result_header", "")
    
    if not report:
        await callback.answer("⚠️ Отчёт недоступен", show_alert=True)
        return
    
    await callback.answer("📊 Загружаю...")
    
    # Объединяем header + report
    full_text = f"{header}\n\n{report}" if header else report
    full_text = sanitize_html(full_text)
    
    # === ДИАГНОСТИКА ДЛИНЫ СООБЩЕНИЙ ===
    logger.info(f"[MSG_LEN] show_detailed_report: header={len(header)}, report={len(report)}, total={len(full_text)}")
    
    # Используем умное разбиение вместо обрезки
    try:
        await send_with_continuation(
            bot=bot,
            chat_id=callback.message.chat.id,
            text=full_text,
            reply_markup=get_back_to_summary_keyboard(session_id),
            continuation_text="📊 <i>Продолжение отчёта...</i>",
        )
    except Exception as e:
        logger.error(f"[MSG_LEN] Failed to send report: {e}")
        # Fallback — отправляем обрезанную версию
        try:
            short_text = full_text[:3500]
            last_dot = max(short_text.rfind('.'), short_text.rfind('!'), short_text.rfind('\n\n'))
            if last_dot > 2000:
                short_text = short_text[:last_dot + 1]
            short_text += "\n\n<i>📄 Полный отчёт доступен в PDF</i>"
            await callback.message.answer(
                short_text,
                reply_markup=get_back_to_summary_keyboard(session_id),
            )
        except Exception as e2:
            logger.error(f"Fallback also failed: {e2}")


@router.callback_query(F.data.startswith("show:profile:"))
async def show_profile(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Показать профиль компетенций — автоматическое разбиение."""
    session_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    
    profile_text = data.get("result_profile")
    
    if not profile_text:
        await callback.answer("⚠️ Профиль недоступен", show_alert=True)
        return
    
    await callback.answer("🎯 Загружаю...")
    
    # === ДИАГНОСТИКА ДЛИНЫ СООБЩЕНИЙ ===
    logger.info(f"[MSG_LEN] show_profile: {len(profile_text)} chars")
    
    # Используем умное разбиение
    try:
        await send_with_continuation(
            bot=bot,
            chat_id=callback.message.chat.id,
            text=profile_text,
            reply_markup=get_back_to_summary_keyboard(session_id),
            continuation_text="🎯 <i>Продолжение профиля...</i>",
        )
    except Exception as e:
        logger.error(f"[MSG_LEN] Failed to send profile: {e}")
        # Fallback
        try:
            short_text = profile_text[:3500]
            last_newline = short_text.rfind('\n\n')
            if last_newline > 2000:
                short_text = short_text[:last_newline]
            short_text += "\n\n<i>📄 Полный профиль в PDF</i>"
            await callback.message.answer(
                short_text,
                reply_markup=get_back_to_summary_keyboard(session_id),
            )
        except Exception as e2:
            logger.error(f"Fallback also failed: {e2}")


@router.callback_query(F.data.startswith("show:pdp:"))
async def show_pdp(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Показать план развития — автоматическое разбиение."""
    session_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    
    pdp_text = data.get("result_pdp")
    
    if not pdp_text:
        await callback.answer("⚠️ План недоступен", show_alert=True)
        return
    
    await callback.answer("📈 Загружаю...")
    
    # === ДИАГНОСТИКА ДЛИНЫ СООБЩЕНИЙ ===
    logger.info(f"[MSG_LEN] show_pdp: {len(pdp_text)} chars")
    
    # Используем умное разбиение
    try:
        await send_with_continuation(
            bot=bot,
            chat_id=callback.message.chat.id,
            text=pdp_text,
            reply_markup=get_back_to_summary_keyboard(session_id),
            continuation_text="📈 <i>Продолжение плана развития...</i>",
        )
    except Exception as e:
        logger.error(f"[MSG_LEN] Failed to send PDP: {e}")
        # Fallback — обрезанная версия
        try:
            short_text = pdp_text[:3500]
            last_newline = short_text.rfind('\n\n')
            if last_newline > 2000:
                short_text = short_text[:last_newline]
            short_text += "\n\n<i>📄 Полный план в PDF</i>"
            await callback.message.answer(
                short_text,
                reply_markup=get_back_to_summary_keyboard(session_id),
            )
        except Exception as e2:
            logger.error(f"Fallback also failed: {e2}")


@router.callback_query(F.data.startswith("show:summary:"))
async def show_summary(callback: CallbackQuery, state: FSMContext):
    """Вернуться к summary card."""
    session_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    
    scores = data.get("result_scores")
    
    if not scores:
        await callback.answer("⚠️ Результаты недоступны. Попробуй /start", show_alert=True)
        return
    
    await callback.answer()
    
    # Генерируем summary заново (т.к. profile в state нет как объект)
    # Используем сохранённые данные
    profile_text = data.get("result_profile", "")
    
    # Извлекаем strengths/growth из scores (raw_averages)
    raw_avg = scores.get("raw_averages", {})
    sorted_metrics = sorted(
        [(k, v) for k, v in raw_avg.items()],
        key=lambda x: x[1],
        reverse=True,
    )
    strengths = [METRIC_NAMES_RU.get(m[0], m[0]) for m in sorted_metrics[:3]]
    growth = [METRIC_NAMES_RU.get(m[0], m[0]) for m in sorted_metrics[-3:]]
    
    total = scores["total"]
    
    if total >= 80:
        level = "🏆 Senior / Lead"
        level_comment = "Впечатляющий результат!"
    elif total >= 60:
        level = "💪 Middle+"
        level_comment = "Отличный уровень!"
    elif total >= 40:
        level = "📈 Middle"
        level_comment = "Хорошая база для роста!"
    elif total >= 25:
        level = "🌱 Junior+"
        level_comment = "Есть потенциал!"
    else:
        level = "🌱 Junior"
        level_comment = "Начало пути!"
    
    filled = int(total / 4)
    bar = "█" * filled + "░" * (25 - filled)
    
    hs = scores.get("hard_skills", 0)
    ss = scores.get("soft_skills", 0)
    th = scores.get("thinking", 0)
    ms = scores.get("mindset", 0)
    
    summary_card = f"""🎯 <b>РЕЗУЛЬТАТЫ ДИАГНОСТИКИ</b>

<b>{data.get('role_name', 'Специалист')}</b> • {data.get('experience_name', '')}

━━━━━━━━━━━━━━━━━━━━

<b>📊 ОБЩИЙ БАЛЛ: {total}/100</b>
<code>{bar}</code>
{level} — {level_comment}

━━━━━━━━━━━━━━━━━━━━

<b>По категориям:</b>
🔧 Hard Skills: {hs}/30
🗣 Soft Skills: {ss}/25
🧠 Thinking: {th}/25
💡 Mindset: {ms}/20

━━━━━━━━━━━━━━━━━━━━

<b>💪 Сильные стороны:</b>
{" • ".join(strengths)}

<b>📈 Фокус на развитие:</b>
{" • ".join(growth)}

━━━━━━━━━━━━━━━━━━━━

<i>Выбери, что хочешь изучить подробнее:</i>"""
    
    await callback.message.answer(
        summary_card,
        reply_markup=get_result_summary_keyboard(session_id),
    )


# ==================== QUICK FEEDBACK HANDLERS ====================

@router.callback_query(F.data.startswith("quick_feedback:"))
async def process_quick_feedback(callback: CallbackQuery, state: FSMContext):
    """Обработка быстрого feedback (👍/👎/подробнее)."""
    feedback_type = callback.data.split(":")[1]
    data = await state.get_data()
    db_session_id = data.get("db_session_id")
    
    if feedback_type == "good":
        # Сохраняем положительный отзыв
        if db_session_id:
            try:
                async with get_session() as db:
                    await save_feedback(
                        session=db,
                        session_id=db_session_id,
                        rating=8,  # 👍 = 8/10
                        comment="quick_feedback: good",
                    )
            except Exception as e:
                logger.error(f"Failed to save quick feedback: {e}")
        
        await callback.message.edit_text(
            "👍 <b>Спасибо!</b>\n\n"
            "Рады, что диагностика была полезной! 🙌",
        )
        await callback.answer("Спасибо! 💪")
        
    elif feedback_type == "bad":
        # Сохраняем отрицательный отзыв
        if db_session_id:
            try:
                async with get_session() as db:
                    await save_feedback(
                        session=db,
                        session_id=db_session_id,
                        rating=3,  # 👎 = 3/10
                        comment="quick_feedback: bad",
                    )
            except Exception as e:
                logger.error(f"Failed to save quick feedback: {e}")
        
        await callback.message.edit_text(
            "👎 <b>Спасибо за честность!</b>\n\n"
            "Расскажи, что можно улучшить?\n"
            "<i>Просто напиши сообщение:</i>",
        )
        await state.set_state(DiagnosticStates.feedback_comment)
        await callback.answer()
        
    elif feedback_type == "detailed":
        # Переход к детальному feedback
        await callback.message.edit_text(
            "📊 <b>Оцени качество диагностики</b>\n\n"
            "Насколько полезным был этот опыт?\n"
            "Выбери от 1 (плохо) до 10 (отлично):",
            reply_markup=get_feedback_rating_keyboard(),
        )
        await state.set_state(DiagnosticStates.feedback_rating)
        await callback.answer()
