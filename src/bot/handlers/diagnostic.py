"""
Обработчик диагностики — flow 10 вопросов с AI.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.bot.states import DiagnosticStates
from src.bot.keyboards.inline import get_restart_keyboard, get_report_keyboard
from src.ai.question_gen import generate_question
from src.ai.answer_analyzer import analyze_answer, calculate_category_scores
from src.ai.report_gen import generate_detailed_report, split_message
from src.db import get_session
from src.db.repositories import save_answer, update_session_progress, complete_session

router = Router(name="diagnostic")
logger = logging.getLogger(__name__)

TOTAL_QUESTIONS = 10


@router.callback_query(F.data == "start_diagnostic", DiagnosticStates.ready_to_start)
async def start_diagnostic(callback: CallbackQuery, state: FSMContext):
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


MIN_ANSWER_LENGTH = 20  # Минимальная длина ответа


@router.message(DiagnosticStates.answering)
async def process_answer(message: Message, state: FSMContext, bot: Bot):
    """Обработка ответа на вопрос."""
    # Проверяем, что это текстовое сообщение
    if not message.text:
        await message.answer(
            "📝 Пожалуйста, отправь текстовый ответ.\n\n"
            "<i>Голосовые сообщения тоже поддерживаются!</i>"
        )
        return
    
    # Проверяем длину ответа
    if len(message.text.strip()) < MIN_ANSWER_LENGTH:
        await message.answer(
            f"✏️ Ответ слишком короткий ({len(message.text)} символов).\n\n"
            "Для точной диагностики нужны развёрнутые ответы.\n"
            "Расскажи подробнее — хотя бы 2-3 предложения."
        )
        return
    
    data = await state.get_data()
    current = data["current_question"]
    
    # Показываем, что анализируем
    thinking_msg = await message.answer("🧠 Анализирую ответ...")
    
    # Сохраняем ответ
    conversation_history = data.get("conversation_history", [])
    analysis_history = data.get("analysis_history", [])
    
    current_question = data.get("current_question_text", f"Вопрос {current}")
    
    conversation_history.append({
        "question": current_question,
        "answer": message.text,
    })
    
    # Анализируем ответ через AI
    analysis = None
    try:
        analysis = await analyze_answer(
            question=current_question,
            answer=message.text,
            role=data["role"],
        )
        analysis_history.append(analysis)
        logger.info(f"Answer {current} analyzed: {analysis.get('scores', {})}")
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        analysis = {
            "scores": {"depth": 5, "self_awareness": 5, "structure": 5, "honesty": 5, "expertise": 5},
            "key_insights": [],
            "gaps": [],
            "hypothesis": "Анализ недоступен",
        }
        analysis_history.append(analysis)
    
    # Сохраняем ответ в БД
    db_session_id = data.get("db_session_id")
    if db_session_id:
        try:
            async with get_session() as db:
                await save_answer(
                    session=db,
                    diagnostic_session_id=db_session_id,
                    question_number=current,
                    question_text=current_question,
                    answer_text=message.text,
                    analysis=analysis,
                )
        except Exception as e:
            logger.error(f"Failed to save answer to DB: {e}")
    
    next_question_num = current + 1
    
    # Проверяем, есть ли ещё вопросы
    if next_question_num <= TOTAL_QUESTIONS:
        # Обновляем статус
        await thinking_msg.edit_text(f"✅ Ответ принят\n\n🔍 Готовлю вопрос {next_question_num}...")
        
        # Генерируем следующий вопрос
        next_question = await generate_question(
            role=data["role"],
            role_name=data["role_name"],
            experience=data["experience_name"],
            question_number=next_question_num,
            conversation_history=conversation_history,
            analysis_history=analysis_history,
        )
        
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
    else:
        # Все вопросы заданы — генерируем детальный отчёт
        await state.update_data(
            conversation_history=conversation_history,
            analysis_history=analysis_history,
        )
        await state.set_state(DiagnosticStates.finished)
        
        await thinking_msg.edit_text("📊 Генерирую детальный AI-отчёт...\n\n<i>Это может занять 15-30 секунд</i>")
        
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
        
        # Рассчитываем баллы и добавляем шапку
        scores = calculate_category_scores(analysis_history)
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
        
        # Отправляем отчёт (возможно несколькими сообщениями)
        parts = split_message(full_report)
        
        # Выбираем клавиатуру (с PDF если есть session_id)
        if db_session_id:
            keyboard = get_report_keyboard(db_session_id)
        else:
            keyboard = get_restart_keyboard()
        
        # Первую часть редактируем в существующее сообщение
        await thinking_msg.edit_text(parts[0])
        
        # Остальные части отправляем новыми сообщениями
        for i, part in enumerate(parts[1:], 1):
            # Последняя часть — с кнопкой
            if i == len(parts) - 1:
                await message.answer(part, reply_markup=keyboard)
            else:
                await message.answer(part)
        
        # Если была только одна часть — добавляем кнопку отдельным сообщением
        if len(parts) == 1:
            await message.answer("👆 Твой отчёт выше", reply_markup=keyboard)


def generate_score_header(data: dict, scores: dict) -> str:
    """Генерация шапки с баллами."""
    total = scores["total"]
    
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
    
    return f"""🎯 <b>ДИАГНОСТИКА ЗАВЕРШЕНА</b>

<b>Профиль:</b> {data['role_name']}
<b>Опыт:</b> {data['experience_name']}
<b>Уровень:</b> {level}

<b>📊 ОБЩИЙ БАЛЛ: {total}/100</b>
<code>{bar}</code>

<b>Breakdown:</b>
• Hard Skills: <b>{scores['hard_skills']}</b>/30
• Soft Skills: <b>{scores['soft_skills']}</b>/25
• Thinking: <b>{scores['thinking']}</b>/25
• Mindset: <b>{scores['mindset']}</b>/20

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
