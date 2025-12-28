"""
Обработчик диагностики — flow 10 вопросов с AI.
"""
import logging
import asyncio
import time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.bot.states import DiagnosticStates
from src.bot.keyboards.inline import (
    get_restart_keyboard, 
    get_report_keyboard, 
    get_confirm_answer_keyboard,
    get_feedback_rating_keyboard,
    get_skip_comment_keyboard,
)
from src.ai.question_gen import generate_question
from src.ai.answer_analyzer import (
    analyze_answer, 
    calculate_category_scores,
    calibrate_scores,
    METRIC_NAMES_RU,
    METRIC_CATEGORIES,
)
from src.ai.report_gen import generate_detailed_report, split_message, split_report_into_blocks, sanitize_html
from src.ai.client import AIServiceError
from src.db import get_session
from src.db.repositories import save_answer, update_session_progress, complete_session, save_feedback

router = Router(name="diagnostic")
logger = logging.getLogger(__name__)

TOTAL_QUESTIONS = 10
REMINDER_TIMEOUT = 5 * 60  # 5 минут

# Хранилище таймеров напоминаний {chat_id: asyncio.Task}
_reminder_tasks: dict[int, asyncio.Task] = {}


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
    
    await state.update_data(
        current_question=1,
        conversation_history=[],
        analysis_history=[],
    )
    
    # Показываем "печатает..."
    await callback.message.edit_text("🔍 Готовлю первый вопрос...")
    
    # Генерируем первый вопрос
    question = await generate_question(
        role=data["role"],
        role_name=data["role_name"],
        experience=data["experience_name"],
        question_number=1,
        conversation_history=[],
        analysis_history=[],
    )
    
    await state.update_data(current_question_text=question)
    
    await callback.message.edit_text(
        f"<b>Вопрос 1/{TOTAL_QUESTIONS}</b>\n\n{question}",
    )
    await state.set_state(DiagnosticStates.answering)
    await callback.answer()
    
    # Запускаем таймер напоминания
    start_reminder(bot, callback.message.chat.id, 1)


MIN_ANSWER_LENGTH = 20  # Минимальная длина ответа


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
            f"✏️ Ответ слишком короткий ({len(text_stripped)} символов).\n\n"
            "Для точной диагностики нужны развёрнутые ответы.\n"
            "Расскажи подробнее — хотя бы 2-3 предложения."
        )
        return
    
    # Сохраняем черновик ответа
    answer_text = message.text.strip()
    await state.update_data(draft_answer=answer_text)
    
    # Показываем preview с кнопками подтверждения
    preview_text = answer_text[:300] + "..." if len(answer_text) > 300 else answer_text
    
    await message.answer(
        f"📝 <b>Твой ответ:</b>\n\n"
        f"<i>{preview_text}</i>\n\n"
        f"Отправить этот ответ?",
        reply_markup=get_confirm_answer_keyboard(),
    )
    await state.set_state(DiagnosticStates.confirming_answer)


@router.message(DiagnosticStates.confirming_answer)
async def handle_new_answer_while_confirming(message: Message, state: FSMContext):
    """Обработка нового текста во время подтверждения — обновляем черновик."""
    if not message.text:
        return
    
    # Обновляем черновик
    answer_text = message.text.strip()
    await state.update_data(draft_answer=answer_text)
    
    preview_text = answer_text[:300] + "..." if len(answer_text) > 300 else answer_text
    
    await message.answer(
        f"📝 <b>Обновлённый ответ:</b>\n\n"
        f"<i>{preview_text}</i>\n\n"
        f"Отправить этот ответ?",
        reply_markup=get_confirm_answer_keyboard(),
    )


@router.callback_query(F.data == "edit_answer", DiagnosticStates.confirming_answer)
async def edit_answer(callback: CallbackQuery, state: FSMContext):
    """Возврат к редактированию ответа."""
    data = await state.get_data()
    current = data.get("current_question", 1)
    question = data.get("current_question_text", "")
    
    await callback.message.edit_text(
        f"<b>Вопрос {current}/{TOTAL_QUESTIONS}</b>\n\n{question}\n\n"
        f"✏️ <i>Введи новый ответ:</i>"
    )
    await state.set_state(DiagnosticStates.answering)
    await callback.answer("Введи новый ответ")


@router.callback_query(F.data == "confirm_answer", DiagnosticStates.confirming_answer)
async def confirm_answer(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение ответа — запускаем анализ."""
    from aiogram.enums import ChatAction
    
    data = await state.get_data()
    current = data["current_question"]
    answer_text = data.get("draft_answer", "")
    
    if not answer_text:
        await callback.answer("❌ Ответ не найден", show_alert=True)
        return
    
    await callback.answer("✅ Анализирую...")
    
    # Показываем typing indicator
    await bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)
    
    # Показываем, что анализируем с прогрессом
    thinking_msg = await callback.message.edit_text(
        f"🧠 Анализирую ответ {current}/{TOTAL_QUESTIONS}...\n\n<code>▓░░░░░░░░░</code> 10%"
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
    
    # === ПРОГРЕСС-БАР ===
    async def update_progress():
        """Обновляет прогресс-бар во время AI запросов."""
        progress_states = [
            ("▓▓░░░░░░░░", "20%", "Анализирую глубину..."),
            ("▓▓▓▓░░░░░░", "40%", "Оцениваю структуру..."),
            ("▓▓▓▓▓▓░░░░", "60%", "Выявляю инсайты..."),
            ("▓▓▓▓▓▓▓▓░░", "80%", "Генерирую вопрос..."),
        ]
        chat_id = callback.message.chat.id
        try:
            for bar, pct, status in progress_states:
                await asyncio.sleep(3)  # Обновляем каждые 3 сек
                await bot.send_chat_action(chat_id, ChatAction.TYPING)
                try:
                    await thinking_msg.edit_text(
                        f"🧠 {status}\n\n<code>{bar}</code> {pct}"
                    )
                except Exception:
                    pass  # Сообщение могло быть уже отредактировано
        except asyncio.CancelledError:
            pass  # Задача отменена — AI завершился раньше
    
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
        if next_question_num > TOTAL_QUESTIONS:
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
    
    # Запускаем параллельно
    if next_question_num <= TOTAL_QUESTIONS:
        analysis, next_question = await asyncio.gather(_analyze(), _generate_next())
    else:
        analysis = await _analyze()
        next_question = None
    
    # Останавливаем прогресс-бар
    progress_task.cancel()
    try:
        await progress_task
    except asyncio.CancelledError:
        pass
    
    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"Answer {current} analyzed: {analysis.get('scores', {})} | Next Q generated | {duration_ms:.0f}ms total")
    
    # Уведомляем пользователя о проблемах с AI (если были)
    if ai_had_issues:
        try:
            await callback.message.answer(
                "⚠️ <i>AI-сервис временно перегружен. Диагностика продолжается в упрощённом режиме.</i>",
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
    if next_question_num <= TOTAL_QUESTIONS:
        
        await state.update_data(
            current_question=next_question_num,
            current_question_text=next_question,
            conversation_history=conversation_history,
            analysis_history=analysis_history,
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
        
        await thinking_msg.edit_text(
            f"<b>Вопрос {next_question_num}/{TOTAL_QUESTIONS}</b>\n\n{next_question}",
        )
        await state.set_state(DiagnosticStates.answering)
        
        # Запускаем таймер напоминания для следующего вопроса
        start_reminder(bot, callback.message.chat.id, next_question_num)
    else:
        # Все вопросы заданы — генерируем детальный отчёт
        cancel_reminder(callback.message.chat.id)  # Отменяем таймер
        from aiogram.enums import ChatAction
        
        await state.update_data(
            conversation_history=conversation_history,
            analysis_history=analysis_history,
        )
        await state.set_state(DiagnosticStates.finished)
        
        await thinking_msg.edit_text(
            "📊 <b>Генерирую детальный AI-отчёт...</b>\n\n"
            "<code>▓░░░░░░░░░</code> 10%\n\n"
            "<i>Анализирую все 10 ответов...</i>"
        )
        
        # Прогресс-бар для отчёта
        async def report_progress():
            progress_states = [
                ("▓▓▓░░░░░░░", "30%", "Выявляю паттерны..."),
                ("▓▓▓▓▓░░░░░", "50%", "Формирую рекомендации..."),
                ("▓▓▓▓▓▓▓░░░", "70%", "Оцениваю потенциал..."),
                ("▓▓▓▓▓▓▓▓▓░", "90%", "Финализирую отчёт..."),
            ]
            try:
                for bar, pct, status in progress_states:
                    await asyncio.sleep(5)
                    await bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)
                    try:
                        await thinking_msg.edit_text(
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
        
        # Рассчитываем баллы и калибруем по опыту
        raw_scores = calculate_category_scores(analysis_history)
        scores = calibrate_scores(raw_scores, data.get("experience", "middle"))
        header = generate_score_header(data, scores)
        
        # Сохраняем результат в БД
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
            except Exception as e:
                logger.error(f"Failed to complete session: {e}")
        
        # Выбираем клавиатуру (с PDF если есть session_id)
        if db_session_id:
            keyboard = get_report_keyboard(db_session_id)
        else:
            keyboard = get_restart_keyboard()
        
        # === ОТПРАВКА ОТЧЁТА БЛОКАМИ С ПАУЗАМИ ===
        
        # 1️⃣ Шапка с баллами (редактируем thinking_msg)
        await thinking_msg.edit_text(header)
        
        # 2️⃣ Разбиваем AI-отчёт на блоки
        report_blocks = split_report_into_blocks(report)
        
        # Если блоков мало — fallback на простую отправку
        if len(report_blocks) <= 1:
            await asyncio.sleep(1)
            try:
                await callback.message.answer(sanitize_html(report))
            except Exception as e:
                logger.warning(f"Report HTML error: {e}")
                await callback.message.answer(report, parse_mode=None)
        else:
            # Отправляем блоки с паузами
            for i, block in enumerate(report_blocks):
                await asyncio.sleep(1)  # Пауза между блоками
                await bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)
                
                # Форматируем блок и санитизируем HTML
                block_text = f"{block['emoji']} <b>{block['title']}</b>\n\n{block['content']}"
                block_text = sanitize_html(block_text)
                
                # Разбиваем если слишком длинный
                block_parts = split_message(block_text, max_length=3500)
                for part in block_parts:
                    try:
                        await callback.message.answer(part)
                    except Exception as e:
                        # Если HTML всё ещё сломан — отправляем plain text
                        logger.warning(f"HTML parse error, sending as plain: {e}")
                        plain_text = part.replace('<b>', '').replace('</b>', '')
                        plain_text = plain_text.replace('<i>', '').replace('</i>', '')
                        await callback.message.answer(plain_text, parse_mode=None)
        
        await asyncio.sleep(0.5)
        
        # 3️⃣ Показываем кнопки PDF/рестарт
        await callback.message.answer(
            "✅ <b>Диагностика завершена!</b>\n\n"
            "Сохрани результаты или пройди ещё раз:",
            reply_markup=keyboard,
        )
        
        # 4️⃣ Запрашиваем feedback
        await asyncio.sleep(1)
        await callback.message.answer(
            "📊 <b>Оцени качество диагностики</b>\n\n"
            "Насколько полезным был этот опыт?\n"
            "Выбери от 1 (плохо) до 10 (отлично):",
            reply_markup=get_feedback_rating_keyboard(),
        )
        await state.set_state(DiagnosticStates.feedback_rating)


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
    
    await message.answer(
        "✅ <b>Спасибо за обратную связь!</b>\n\n"
        "Твой отзыв поможет улучшить диагностику 💪\n\n"
        "Хочешь пройти ещё раз? Нажми /start",
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
    
    await callback.message.edit_text(
        "✅ <b>Спасибо за оценку!</b>\n\n"
        "Твой отзыв поможет улучшить диагностику 💪\n\n"
        "Хочешь пройти ещё раз? Нажми /start",
    )
    await state.set_state(DiagnosticStates.finished)
    await callback.answer()
