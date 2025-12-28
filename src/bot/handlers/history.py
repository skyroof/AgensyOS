"""
Обработчик команды /history — просмотр прошлых диагностик.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command

from src.db import get_session
from src.db.repositories import get_user_by_telegram_id, get_user_sessions, get_session_by_id
from src.utils.pdf_generator import generate_pdf_report

router = Router(name="history")
logger = logging.getLogger(__name__)


@router.message(Command("history"))
async def cmd_history(message: Message):
    """Показать историю диагностик пользователя."""
    try:
        async with get_session() as db:
            user = await get_user_by_telegram_id(db, message.from_user.id)
            
            if not user:
                await message.answer(
                    "📭 У тебя ещё нет истории диагностик.\n\n"
                    "Нажми /start чтобы пройти первую!"
                )
                return
            
            sessions = await get_user_sessions(db, user.id, limit=5)
            
            if not sessions:
                await message.answer(
                    "📭 У тебя ещё нет завершённых диагностик.\n\n"
                    "Нажми /start чтобы пройти первую!"
                )
                return
            
            # Формируем список
            lines = ["📊 <b>Твои последние диагностики:</b>\n"]
            
            for i, sess in enumerate(sessions, 1):
                status_emoji = "✅" if sess.status == "completed" else "⏳"
                date_str = sess.started_at.strftime("%d.%m.%Y %H:%M")
                
                if sess.status == "completed" and sess.total_score is not None:
                    score_str = f"<b>{sess.total_score}/100</b>"
                else:
                    score_str = "не завершено"
                
                lines.append(
                    f"{i}. {status_emoji} {sess.role_name} ({sess.experience_name})\n"
                    f"   📅 {date_str} | {score_str}"
                )
            
            lines.append("\n\nНажми /start для новой диагностики")
            
            await message.answer("\n".join(lines))
            
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        await message.answer("❌ Не удалось загрузить историю. Попробуй позже.")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показать справку."""
    help_text = """
🎯 <b>Deep Diagnostic Bot</b>

Я оцениваю уровень дизайнеров и продактов за 10 глубоких вопросов.

<b>Команды:</b>
/start — начать новую диагностику
/history — посмотреть прошлые результаты
/help — эта справка

<b>Как это работает:</b>
1. Выбираешь роль и опыт
2. Отвечаешь на 10 вопросов (развёрнуто!)
3. AI анализирует ответы
4. Получаешь детальный отчёт с баллами

<b>Оценка идёт по 4 категориям:</b>
• Hard Skills (30 баллов)
• Soft Skills (25 баллов)
• Thinking (25 баллов)
• Mindset (20 баллов)

<b>Совет:</b> Чем подробнее отвечаешь — тем точнее диагностика!
"""
    await message.answer(help_text)


@router.callback_query(F.data.startswith("pdf:"))
async def process_pdf_download(callback: CallbackQuery):
    """Генерация и отправка PDF-отчёта."""
    await callback.answer("📄 Генерирую PDF...")
    
    session_id = int(callback.data.split(":")[1])
    
    try:
        async with get_session() as db:
            diagnostic_session = await get_session_by_id(db, session_id)
            
            if not diagnostic_session:
                await callback.message.answer("❌ Сессия не найдена.")
                return
            
            if diagnostic_session.status != "completed":
                await callback.message.answer("❌ Диагностика не завершена.")
                return
            
            # Получаем данные для PDF
            scores = {
                "total": diagnostic_session.total_score or 0,
                "hard_skills": diagnostic_session.hard_skills_score or 0,
                "soft_skills": diagnostic_session.soft_skills_score or 0,
                "thinking": diagnostic_session.thinking_score or 0,
                "mindset": diagnostic_session.mindset_score or 0,
            }
            
            conversation_history = diagnostic_session.conversation_history or []
            report_text = diagnostic_session.report or "Отчёт недоступен"
            
            # Получаем имя пользователя
            user_name = callback.from_user.first_name or "Кандидат"
            if callback.from_user.last_name:
                user_name += f" {callback.from_user.last_name}"
            
            # Генерируем PDF
            status_msg = await callback.message.answer("⏳ Генерирую PDF-отчёт...")
            
            try:
                pdf_bytes = generate_pdf_report(
                    role_name=diagnostic_session.role_name,
                    experience=diagnostic_session.experience_name,
                    scores=scores,
                    report_text=report_text,
                    conversation_history=conversation_history,
                    user_name=user_name,
                )
                
                # Формируем имя файла
                date_str = diagnostic_session.completed_at.strftime("%Y%m%d") if diagnostic_session.completed_at else "report"
                filename = f"diagnostic_{diagnostic_session.role}_{date_str}.pdf"
                
                # Отправляем файл
                document = BufferedInputFile(pdf_bytes, filename=filename)
                
                await callback.message.answer_document(
                    document=document,
                    caption=f"📄 <b>PDF-отчёт</b>\n\n"
                            f"Роль: {diagnostic_session.role_name}\n"
                            f"Балл: {diagnostic_session.total_score}/100",
                )
                
                await status_msg.delete()
                
            except Exception as e:
                logger.error(f"PDF generation failed: {e}")
                await status_msg.edit_text("❌ Не удалось сгенерировать PDF. Попробуй позже.")
                
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        await callback.message.answer("❌ Ошибка при создании PDF.")

