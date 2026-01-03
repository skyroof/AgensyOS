"""
Обработчик команды /history — просмотр прошлых диагностик.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.enums import ChatAction

from src.db import get_session
from src.db.repositories import (
    get_user_by_telegram_id, 
    get_user_sessions, 
    get_session_by_id,
    get_completed_sessions,
    get_user_stats,
)
from src.utils.pdf_generator import generate_pdf_report
from src.utils.message_splitter import send_with_continuation
from src.bot.keyboards.inline import (
    get_back_to_menu_keyboard,
    get_after_share_keyboard,
    get_result_summary_keyboard,
    get_history_keyboard,
)
from src.analytics import (
    build_profile, format_profile_text, 
    get_benchmark, format_benchmark_text,
    get_user_progress, format_progress_text,
    build_pdp, format_pdp_text,
    calculate_user_dynamics, format_dynamics_text, format_session_card,
)
from src.ai.answer_analyzer import calculate_category_scores, calibrate_scores
from src.ai.report_gen import split_message

router = Router(name="history")
logger = logging.getLogger(__name__)


@router.message(Command("history"))
async def cmd_history(message: Message, bot: Bot):
    """Показать историю диагностик пользователя с динамикой развития."""
    try:
        async with get_session() as db:
            user = await get_user_by_telegram_id(db, message.from_user.id)
            
            if not user:
                await message.answer(
                    "📭 <b>История диагностик</b>\n\n"
                    "У тебя ещё нет диагностик.\n\n"
                    "<i>Пройди первую: /start</i>",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                return
            
            # Получаем только завершённые сессии
            sessions = await get_completed_sessions(db, user.id, limit=10)
            
            if not sessions:
                await message.answer(
                    "📭 <b>История диагностик</b>\n\n"
                    "У тебя ещё нет завершённых диагностик.\n\n"
                    "<i>Пройди диагностику: /start</i>",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                return
            
            # Рассчитываем динамику
            dynamics = calculate_user_dynamics(sessions)
            
            # Форматируем текст с динамикой
            dynamics_text = format_dynamics_text(dynamics)
            
            # Отправляем с умным разбиением
            await send_with_continuation(
                bot=bot,
                chat_id=message.chat.id,
                text=dynamics_text,
                reply_markup=get_history_keyboard(sessions[0].id if sessions else None),
                continuation_text="📊 <i>Продолжение истории...</i>",
            )
            
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        await message.answer("❌ Не удалось загрузить историю. Попробуй позже.")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показать справку."""
    help_text = """
🎯 <b>MAX Diagnostic Bot</b>

Я оцениваю уровень дизайнеров и продактов за 10 глубоких вопросов.

<b>Команды:</b>
/start — начать новую диагностику
/history — посмотреть прошлые результаты
/profile — посмотреть свой профиль компетенций
/pdp — персональный план развития
/progress — отслеживать прогресс между диагностиками
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

<b>Доступность:</b> /accessibility — подсказки для удобства
"""
    await message.answer(help_text)


@router.message(Command("accessibility"))
async def cmd_accessibility(message: Message):
    """Показать подсказки по доступности."""
    from src.bot.keyboards.reply import get_accessibility_hint
    
    accessibility_text = f"""
♿ <b>Настройки доступности</b>

<b>📱 Увеличить шрифт:</b>
Настройки Telegram → Размер текста чата

<b>🎤 Голосовые ответы:</b>
Вместо текста можешь записать голосовое сообщение — 
бот его расшифрует и покажет для проверки.

<b>⌨️ Навигация:</b>
Все кнопки доступны с клавиатуры. 
Используй Tab и Enter для навигации.

<b>📖 Экранные читалки:</b>
Бот совместим с TalkBack (Android) и VoiceOver (iOS).
Все элементы имеют текстовые описания.

<b>🌐 Язык:</b>
Бот автоматически определяет язык ответа.
Можешь отвечать на русском или английском.

<b>⏱️ Без ограничения времени:</b>
На ответы нет таймера — думай сколько нужно.
Сессия сохраняется автоматически.

━━━━━━━━━━━━━━━━━━━━

💡 <i>Если есть предложения по улучшению доступности — 
напиши в /help</i>
"""
    await message.answer(accessibility_text)


from src.bot.handlers.payments import show_paywall

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Показать профиль компетенций из последней диагностики."""
    try:
        async with get_session() as db:
            user = await get_user_by_telegram_id(db, message.from_user.id)
            
            if not user:
                await message.answer(
                    "📭 У тебя ещё нет профиля.",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                return
            
            sessions = await get_user_sessions(db, user.id, limit=1)
            
            if not sessions or sessions[0].status != "completed":
                await message.answer(
                    "📭 Нет завершённых диагностик.",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                return
            
            session = sessions[0]

            # ПРОВЕРКА ДЛЯ ДЕМО-СЕССИЙ
            if session.mode == "demo":
                await show_paywall(message, demo_completed=True)
                return
            
            # Восстанавливаем analysis_history
            analysis_history = session.analysis_history or []
            if not analysis_history:
                await message.answer(
                    "⚠️ Данные для профиля недоступны.\n\n"
                    "Пройди новую диагностику: /start"
                )
                return
            
            # Рассчитываем scores
            raw_scores = calculate_category_scores(analysis_history)
            scores = calibrate_scores(raw_scores, session.experience)
            
            # Строим профиль
            profile = build_profile(
                role=session.role,
                role_name=session.role_name,
                experience=session.experience,
                experience_name=session.experience_name,
                scores=scores,
                analysis_history=analysis_history,
            )
            
            profile_text = format_profile_text(profile)
            
            # Отправляем по частям если длинный
            parts = split_message(profile_text, max_length=3500)
            for part in parts:
                try:
                    await message.answer(part)
                except Exception as e:
                    logger.warning(f"Profile HTML error: {e}")
                    await message.answer(part, parse_mode=None)
            
            # Добавляем бенчмарк
            try:
                benchmark = await get_benchmark(
                    session=db,
                    user_score=session.total_score or 0,
                    role=session.role,
                    role_name=session.role_name,
                    experience=session.experience,
                    experience_name=session.experience_name,
                )
                
                if benchmark.has_enough_data or benchmark.overall_total_sessions > 0:
                    benchmark_text = format_benchmark_text(benchmark, session.total_score or 0)
                    await message.answer(benchmark_text)
            except Exception as e:
                logger.warning(f"Failed to get benchmark in /profile: {e}")
            
            # Добавляем дату диагностики
            date_str = session.completed_at.strftime("%d.%m.%Y") if session.completed_at else "Неизвестно"
            await message.answer(
                f"<i>Профиль на основе диагностики от {date_str}</i>",
                reply_markup=get_back_to_menu_keyboard(),
            )
            
    except Exception as e:
        logger.error(f"Failed to get profile: {e}")
        await message.answer("❌ Не удалось загрузить профиль. Попробуй позже.")


@router.message(Command("progress"))
async def cmd_progress(message: Message):
    """Показать прогресс между диагностиками."""
    try:
        async with get_session() as db:
            user = await get_user_by_telegram_id(db, message.from_user.id)
            
            if not user:
                await message.answer(
                    "📊 <b>Прогресс</b>\n\n"
                    "У тебя ещё нет диагностик.",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                return

            # Проверяем последнюю сессию
            sessions = await get_user_sessions(db, user.id, limit=1)
            if sessions and sessions[0].mode == "demo":
                 await show_paywall(message, demo_completed=True)
                 return
            
            # Получаем отчёт о прогрессе
            progress = await get_user_progress(db, user.id)
            
            # Форматируем и отправляем
            progress_text = format_progress_text(progress)
            
            # Разбиваем на части если длинный
            parts = split_message(progress_text, max_length=3500)
            for part in parts:
                try:
                    await message.answer(part)
                except Exception as e:
                    logger.warning(f"Progress HTML error: {e}")
                    await message.answer(part, parse_mode=None)
            
    except Exception as e:
        logger.error(f"Failed to get progress: {e}")
        await message.answer("❌ Не удалось загрузить прогресс. Попробуй позже.")


@router.message(Command("pdp"))
async def cmd_pdp(message: Message):
    """Показать персональный план развития."""
    try:
        async with get_session() as db:
            user = await get_user_by_telegram_id(db, message.from_user.id)
            
            if not user:
                await message.answer(
                    "🎯 <b>План развития</b>\n\n"
                    "У тебя ещё нет диагностик.",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                return
            
            sessions = await get_user_sessions(db, user.id, limit=1)
            
            if not sessions or sessions[0].status != "completed":
                await message.answer(
                    "🎯 <b>План развития</b>\n\n"
                    "Нет завершённых диагностик.",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                return
            
            session = sessions[0]

            # ПРОВЕРКА ДЛЯ ДЕМО
            if session.mode == "demo":
                 await show_paywall(message, demo_completed=True)
                 return
            
            # Восстанавливаем analysis_history
            analysis_history = session.analysis_history or []
            if not analysis_history:
                await message.answer(
                    "⚠️ Данные для плана недоступны.\n\n"
                    "Пройди новую диагностику: /start"
                )
                return
            
            # Рассчитываем scores
            raw_scores = calculate_category_scores(analysis_history)
            calibrated = calibrate_scores(raw_scores, session.experience)
            
            # Строим профиль для strengths
            profile = build_profile(
                role=session.role,
                role_name=session.role_name,
                experience=session.experience,
                experience_name=session.experience_name,
                scores=calibrated,
                analysis_history=analysis_history,
            )
            
            # Строим PDP
            raw_averages = calibrated.get("raw_averages", {})
            pdp = build_pdp(
                role=session.role,
                role_name=session.role_name,
                experience=session.experience,
                experience_name=session.experience_name,
                total_score=session.total_score or 0,
                raw_averages=raw_averages,
                strengths=profile.strengths,
            )
            
            pdp_text = format_pdp_text(pdp)
            
            # Отправляем по частям если длинный
            parts = split_message(pdp_text, max_length=3800)
            for part in parts:
                try:
                    await message.answer(part)
                except Exception as e:
                    logger.warning(f"PDP HTML error: {e}")
                    await message.answer(part, parse_mode=None)
            
            # Дата диагностики
            date_str = session.completed_at.strftime("%d.%m.%Y") if session.completed_at else "Неизвестно"
            await message.answer(
                f"<i>План на основе диагностики от {date_str}</i>\n\n"
                f"🔄 Обновить результаты: /start\n"
                f"📊 Отследить прогресс: /progress"
            )
            
    except Exception as e:
        logger.error(f"Failed to get PDP: {e}")
        await message.answer("❌ Не удалось загрузить план развития. Попробуй позже.")


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
            
            # ПРОВЕРКА ДЛЯ ДЕМО
            if diagnostic_session.mode == "demo":
                 await show_paywall(callback.message, demo_completed=True)
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
            analysis_history = diagnostic_session.analysis_history or []
            
            # Строим профиль, PDP и бенчмарк для PDF
            profile_data = None
            pdp_data = None
            benchmark_data = None
            raw_averages = None
            
            if analysis_history:
                try:
                    raw_scores = calculate_category_scores(analysis_history)
                    calibrated = calibrate_scores(raw_scores, diagnostic_session.experience)
                    raw_averages = calibrated.get("raw_averages", {})
                    
                    profile = build_profile(
                        role=diagnostic_session.role,
                        role_name=diagnostic_session.role_name,
                        experience=diagnostic_session.experience,
                        experience_name=diagnostic_session.experience_name,
                        scores=calibrated,
                        analysis_history=analysis_history,
                    )
                    # Преобразуем в dict для PDF
                    from src.ai.answer_analyzer import METRIC_NAMES_RU
                    profile_data = {
                        "strengths": [METRIC_NAMES_RU.get(s, s) for s in profile.strengths],
                        "growth_areas": [METRIC_NAMES_RU.get(g, g) for g in profile.growth_areas],
                        "thinking_style": profile.thinking_style_description[:100] if profile.thinking_style_description else "",
                        "communication_style": profile.communication_style_description[:100] if profile.communication_style_description else "",
                    }
                    
                    # Строим PDP
                    pdp = build_pdp(
                        role=diagnostic_session.role,
                        role_name=diagnostic_session.role_name,
                        experience=diagnostic_session.experience,
                        experience_name=diagnostic_session.experience_name,
                        total_score=diagnostic_session.total_score or 0,
                        raw_averages=raw_averages,
                        strengths=profile.strengths,
                    )
                    
                    # Преобразуем PDP в dict для PDF
                    pdp_data = {
                        "main_focus": pdp.main_focus,
                        "motivation_message": pdp.motivation_message,
                        "plan_30_days": pdp.plan_30_days,
                        "plan_60_days": pdp.plan_60_days,
                        "plan_90_days": pdp.plan_90_days,
                        "success_metrics": pdp.success_metrics,
                        "primary_goals": [
                            {
                                "metric_name": g.metric_name,
                                "current_score": g.current_score,
                                "target_score": g.target_score,
                                "resources": [
                                    {"title": r.title, "type": r.type}
                                    for r in g.resources[:2]
                                ] if g.resources else [],
                            }
                            for g in pdp.primary_goals
                        ],
                    }
                    
                    # Получаем бенчмарк
                    try:
                        benchmark = await get_benchmark(
                            session=db,
                            user_score=diagnostic_session.total_score or 0,
                            role=diagnostic_session.role,
                            role_name=diagnostic_session.role_name,
                            experience=diagnostic_session.experience,
                            experience_name=diagnostic_session.experience_name,
                        )
                        if benchmark.overall_total_sessions > 0:
                            benchmark_data = {
                                "avg_score": benchmark.overall_avg_score,
                                "percentile": benchmark.overall_percentile,
                            }
                    except Exception as e:
                        logger.warning(f"Failed to get benchmark for PDF: {e}")
                        
                except Exception as e:
                    logger.warning(f"Failed to build profile/PDP for PDF: {e}")
            
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
                    profile_data=profile_data,
                    pdp_data=pdp_data,
                    benchmark_data=benchmark_data,
                    raw_averages=raw_averages,
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
                logger.error(f"PDF generation failed: {e}", exc_info=True)
                error_text = str(e)
                if "font" in error_text.lower():
                    await status_msg.edit_text("❌ Ошибка шрифтов на сервере. PDF временно недоступен.")
                else:
                    await status_msg.edit_text(f"❌ Не удалось сгенерировать PDF. Ошибка: {error_text[:100]}")
                
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        await callback.message.answer("❌ Ошибка при создании PDF.")


@router.callback_query(F.data.startswith("share:"))
async def process_share_card(callback: CallbackQuery, bot: Bot):
    """Генерация и отправка Share Card (PNG) для соцсетей."""
    await callback.answer("⏳ Рисую...", show_alert=False)
    
    session_id = int(callback.data.split(":")[1])
    
    try:
        await bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_PHOTO)
        
        async with get_session() as db:
            from src.db.repositories import get_session_by_id
            
            diagnostic_session = await get_session_by_id(db, session_id)
            
            if not diagnostic_session:
                await callback.message.answer("❌ Сессия не найдена.")
                return
            
            status_msg = await callback.message.answer("🎨 <b>Генерирую красивую картинку...</b>\n<i>Это займет пару секунд</i>")
            await bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_PHOTO)
            
            try:
                from src.utils.share_card import generate_share_card
                from aiogram.types import BufferedInputFile
                
                # Собираем данные для карточки
                category_scores = {
                    "hard_skills": diagnostic_session.hard_skills_score or 0,
                    "soft_skills": diagnostic_session.soft_skills_score or 0,
                    "thinking": diagnostic_session.thinking_score or 0,
                    "mindset": diagnostic_session.mindset_score or 0,
                }
                
                # Генерируем PNG
                png_bytes = generate_share_card(
                    total_score=diagnostic_session.total_score or 0,
                    role_name=diagnostic_session.role_name,
                    category_scores=category_scores,
                )
                
                # Отправляем как фото
                photo = BufferedInputFile(png_bytes, filename="diagnostic_result.png")
                
                # Формируем deep link
                bot_username = "deep_diagnostic_bot"  # TODO: получать динамически
                share_text = (
                    f"🎯 Прошёл диагностику {diagnostic_session.role_name}!\n"
                    f"Мой результат: {diagnostic_session.total_score}/100\n\n"
                    f"Пройди и ты: https://t.me/{bot_username}"
                )
                
                await callback.message.answer_photo(
                    photo=photo,
                    caption=f"📤 <b>Поделись своим результатом!</b>\n\n"
                            f"<code>{share_text}</code>\n\n"
                            f"<i>Скопируй текст или сохрани картинку</i>",
                    reply_markup=get_after_share_keyboard(session_id),
                )
                
                await status_msg.delete()
                
            except Exception as e:
                logger.error(f"Share card generation failed: {e}")
                await status_msg.edit_text("❌ Не удалось создать картинку. Попробуй позже.")
                
    except Exception as e:
        logger.error(f"Failed to generate share card: {e}")
        await callback.message.answer("❌ Ошибка при создании картинки.")


# ==================== NAVIGATION CALLBACKS ====================

@router.callback_query(F.data == "show_history")
async def show_history_callback(callback: CallbackQuery, bot: Bot):
    """Показ истории через callback с динамикой развития."""
    await callback.answer("📊 Загружаю историю...")
    
    try:
        async with get_session() as db:
            user = await get_user_by_telegram_id(db, callback.from_user.id)
            
            if not user:
                await callback.message.edit_text(
                    "📭 <b>История диагностик</b>\n\n"
                    "У тебя ещё нет диагностик.\n\n"
                    "<i>Пройди первую: /start</i>",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                return
            
            sessions = await get_completed_sessions(db, user.id, limit=10)
            
            if not sessions:
                await callback.message.edit_text(
                    "📭 <b>История диагностик</b>\n\n"
                    "У тебя ещё нет завершённых диагностик.\n\n"
                    "<i>Пройди диагностику: /start</i>",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                return
            
            # Рассчитываем динамику
            dynamics = calculate_user_dynamics(sessions)
            dynamics_text = format_dynamics_text(dynamics)
            
            # Отправляем новым сообщением (edit_text не подходит для длинных)
            await send_with_continuation(
                bot=bot,
                chat_id=callback.message.chat.id,
                text=dynamics_text,
                reply_markup=get_history_keyboard(sessions[0].id if sessions else None),
                continuation_text="📊 <i>Продолжение истории...</i>",
            )
            
    except Exception as e:
        logger.error(f"Failed to get history via callback: {e}")
        await callback.message.answer(
            "❌ Не удалось загрузить историю.",
            reply_markup=get_back_to_menu_keyboard(),
        )


@router.callback_query(F.data.startswith("back_to_results:"))
async def back_to_results(callback: CallbackQuery):
    """Возврат к результатам сессии."""
    await callback.answer()
    
    try:
        session_id = int(callback.data.split(":")[1])
        
        async with get_session() as db:
            diagnostic_session = await get_session_by_id(db, session_id)
            
            if not diagnostic_session:
                await callback.message.answer(
                    "❌ Сессия не найдена.",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                return
            
            from src.bot.keyboards.inline import get_result_summary_keyboard
            
            # Формируем summary card
            summary = (
                f"📊 <b>Результаты диагностики</b>\n\n"
                f"👤 {diagnostic_session.role_name} ({diagnostic_session.experience_name})\n"
                f"🏆 Общий балл: <b>{diagnostic_session.total_score}/100</b>\n"
            )
            
            if diagnostic_session.completed_at:
                date_str = diagnostic_session.completed_at.strftime("%d.%m.%Y")
                summary += f"📅 {date_str}\n"
            
            await callback.message.answer(
                summary,
                reply_markup=get_result_summary_keyboard(session_id),
            )
            
    except Exception as e:
        logger.error(f"Failed to return to results: {e}")
        await callback.message.answer(
            "❌ Ошибка при загрузке результатов.",
            reply_markup=get_back_to_menu_keyboard(),
        )

