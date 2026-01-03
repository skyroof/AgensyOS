"""
Хендлеры для интерактивного PDP 2.0.

Команды:
- /pdp — показать текущий план или создать новый
- Кнопки: ✅ Сделано, ⏭️ Пропустить, 📝 Заметка
- Прогресс и геймификация
"""
import logging
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.db import get_session
from src.db.repositories.user_repo import get_user_by_telegram_id
from src.db.repositories.diagnostic_repo import get_completed_sessions
from src.db.repositories.pdp_repo import (
    get_active_pdp_plan,
    create_pdp_plan,
    add_tasks_batch,
    get_today_task,
    get_tasks_for_week,
    get_task_by_id,
    complete_task,
    skip_task,
    update_streak,
    add_points,
    add_badge,
    get_pdp_stats,
    update_pdp_progress,
    get_or_create_reminder,
    update_reminder_settings,
)
from src.db.repositories.reminder_repo import schedule_task_reminder
from src.analytics.pdp_generator import (
    generate_pdp_plan,
    format_pdp_plan_text,
    format_today_task,
    DAY_NAMES,
    TASK_TYPES,
)
from src.utils.message_splitter import send_with_continuation
from src.bot.handlers.payments import show_paywall


logger = logging.getLogger(__name__)
router = Router()


# ==================== STATES ====================

class PdpStates(StatesGroup):
    """Состояния для настройки PDP."""
    choosing_time = State()  # Выбор времени в день
    choosing_style = State()  # Выбор стиля обучения
    adding_note = State()  # Добавление заметки к задаче


# ==================== KEYBOARDS ====================

def get_pdp_main_keyboard(plan_id: int, current_week: int = 1) -> InlineKeyboardMarkup:
    """Главная клавиатура PDP."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Задача на сегодня", callback_data=f"pdp:today:{plan_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Неделя 1", callback_data=f"pdp:week:1:{plan_id}"),
        InlineKeyboardButton(text="📊 Неделя 2", callback_data=f"pdp:week:2:{plan_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Неделя 3", callback_data=f"pdp:week:3:{plan_id}"),
        InlineKeyboardButton(text="📊 Неделя 4", callback_data=f"pdp:week:4:{plan_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📈 Мой прогресс", callback_data=f"pdp:stats:{plan_id}"),
        InlineKeyboardButton(text="🔍 Сравнить", callback_data=f"pdp:compare:{plan_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data=f"pdp:settings:{plan_id}"),
    )
    return builder.as_markup()


def get_task_keyboard(task_id: int, plan_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для задачи."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Сделано!", callback_data=f"pdp:done:{task_id}:{plan_id}"),
        InlineKeyboardButton(text="⏭️ Пропустить", callback_data=f"pdp:skip:{task_id}:{plan_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📝 Добавить заметку", callback_data=f"pdp:note:{task_id}:{plan_id}"),
        InlineKeyboardButton(text="⏰ Напомнить", callback_data=f"pdp:remind_menu:{task_id}:{plan_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ К плану", callback_data=f"pdp:main:{plan_id}"),
    )
    return builder.as_markup()


def get_time_choice_keyboard() -> InlineKeyboardMarkup:
    """Выбор времени в день."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚡ 15 мин/день", callback_data="pdp:time:15"),
        InlineKeyboardButton(text="💪 30 мин/день", callback_data="pdp:time:30"),
    )
    builder.row(
        InlineKeyboardButton(text="🔥 60 мин/день", callback_data="pdp:time:60"),
    )
    return builder.as_markup()


def get_style_choice_keyboard() -> InlineKeyboardMarkup:
    """Выбор стиля обучения."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📖 Читать", callback_data="pdp:style:read"),
        InlineKeyboardButton(text="🎬 Смотреть", callback_data="pdp:style:watch"),
    )
    builder.row(
        InlineKeyboardButton(text="💪 Практиковать", callback_data="pdp:style:do"),
        InlineKeyboardButton(text="🔀 Микс", callback_data="pdp:style:mixed"),
    )
    return builder.as_markup()


def get_back_to_pdp_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    """Кнопка назад к PDP."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ К плану", callback_data=f"pdp:main:{plan_id}"),
    )
    return builder.as_markup()


def get_no_plan_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура когда нет плана."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎯 Создать план", callback_data="pdp:create"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Пройти диагностику", callback_data="restart"),
    )
    return builder.as_markup()


# ==================== BADGES ====================

BADGES = {
    "first_task": {"name": "🎯 Первый шаг", "description": "Выполнил первую задачу"},
    "week_1_done": {"name": "📅 Неделя 1", "description": "Завершил первую неделю"},
    "week_2_done": {"name": "📅 Неделя 2", "description": "Завершил вторую неделю"},
    "week_3_done": {"name": "📅 Неделя 3", "description": "Завершил третью неделю"},
    "week_4_done": {"name": "🏆 Марафонец", "description": "Завершил весь план!"},
    "streak_3": {"name": "🔥 3 дня подряд", "description": "3 дня выполнения задач"},
    "streak_7": {"name": "🔥🔥 Неделя огня", "description": "7 дней подряд"},
    "streak_14": {"name": "🔥🔥🔥 Две недели!", "description": "14 дней подряд"},
    "streak_30": {"name": "👑 Мастер дисциплины", "description": "30 дней подряд!"},
    "perfect_week": {"name": "💎 Идеальная неделя", "description": "Все задачи недели выполнены"},
}


# ==================== COMMANDS ====================

@router.message(Command("pdp"))
@router.message(F.text == "📚 Мой PDP")
async def cmd_pdp(message: Message, state: FSMContext):
    """Показать PDP или предложить создать."""
    try:
        await state.clear()
        
        async with get_session() as db:
            user = await get_user_by_telegram_id(db, message.from_user.id)
            
            if not user:
                await message.answer(
                    "📋 <b>План развития</b>\n\n"
                    "Сначала пройди диагностику, чтобы я мог создать персональный план.\n\n"
                    "<i>Начни с /start</i>",
                )
                return
            
            # Ищем активный план
            plan = await get_active_pdp_plan(db, user.id)
            
            if plan:
                # Показываем существующий план
                stats = await get_pdp_stats(db, plan.id)
                
                text = f"""🎯 <b>ТВОЙ ПЛАН РАЗВИТИЯ</b>
    
    <b>Прогресс:</b> {stats['completed_tasks']}/{stats['total_tasks']} задач ({stats['completion_rate']}%)
    <b>Неделя:</b> {stats['current_week']}/4
    <b>Серия:</b> 🔥 {stats['current_streak']} дней
    
    <b>Очки:</b> {stats['total_points']} ⭐
    <b>Бейджи:</b> {stats['badges_count']} 🏅
    
    <i>Выбери действие:</i>"""
                
                await message.answer(
                    text,
                    reply_markup=get_pdp_main_keyboard(plan.id),
                )
            else:
                # Предлагаем создать
                sessions = await get_completed_sessions(db, user.id, limit=1)
                
                if sessions:
                    # ПРОВЕРКА ДЛЯ ДЕМО
                    if sessions[0].diagnostic_mode == "demo":
                        await show_paywall(message, demo_completed=True)
                        return

                    await message.answer(
                        "📋 <b>План развития</b>\n\n"
                        "У тебя есть завершённая диагностика!\n"
                        "Создадим персональный 30-дневный план?\n\n"
                        "<i>Это займёт 2 минуты.</i>",
                        reply_markup=get_no_plan_keyboard(),
                    )
                else:
                    await message.answer(
                        "📋 <b>План развития</b>\n\n"
                        "Сначала пройди диагностику, чтобы я понял твои зоны роста.\n\n"
                        "<i>Начни с /start</i>",
                        reply_markup=get_no_plan_keyboard(),
                    )
    except Exception as e:
        logger.error(f"Failed to open PDP: {e}")
        await message.answer("❌ Не удалось загрузить PDP. Попробуй позже.")


# ==================== CREATE PLAN ====================

@router.callback_query(F.data == "pdp:create")
async def start_create_pdp(callback: CallbackQuery, state: FSMContext):
    """Начать создание плана."""
    await callback.answer()
    
    async with get_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Сначала пройди диагностику: /start")
            return
        
        sessions = await get_completed_sessions(db, user.id, limit=1)
        if not sessions:
            await callback.message.edit_text(
                "❌ Нужна завершённая диагностика.\n\n"
                "<i>Пройди: /start</i>"
            )
            return
        
        # Сохраняем сессию для создания плана
        await state.update_data(session_id=sessions[0].id)
    
    await callback.message.edit_text(
        "⏱ <b>Сколько времени готов уделять развитию?</b>\n\n"
        "Выбери реалистичный вариант — лучше меньше, но регулярно!",
        reply_markup=get_time_choice_keyboard(),
    )
    await state.set_state(PdpStates.choosing_time)


@router.callback_query(F.data.startswith("pdp:time:"), PdpStates.choosing_time)
async def choose_time(callback: CallbackQuery, state: FSMContext):
    """Выбор времени в день."""
    await callback.answer()
    
    time = int(callback.data.split(":")[2])
    await state.update_data(daily_time=time)
    
    await callback.message.edit_text(
        "📚 <b>Как тебе удобнее учиться?</b>\n\n"
        "• 📖 <b>Читать</b> — книги, статьи, документация\n"
        "• 🎬 <b>Смотреть</b> — видео, курсы, лекции\n"
        "• 💪 <b>Практиковать</b> — сразу делать, учиться на ходу\n"
        "• 🔀 <b>Микс</b> — сбалансированный подход",
        reply_markup=get_style_choice_keyboard(),
    )
    await state.set_state(PdpStates.choosing_style)


@router.callback_query(F.data.startswith("pdp:style:"), PdpStates.choosing_style)
async def choose_style_and_create(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Выбор стиля и создание плана."""
    await callback.answer("🔄 Создаю план...")
    
    style = callback.data.split(":")[2]
    data = await state.get_data()
    daily_time = data.get("daily_time", 30)
    session_id = data.get("session_id")
    
    await state.clear()
    
    async with get_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        if not user or not session_id:
            await callback.message.edit_text("❌ Ошибка. Попробуй /pdp")
            return
        
        # Получаем данные сессии для определения фокуса
        from src.db.repositories.diagnostic_repo import get_session_by_id
        session = await get_session_by_id(db, session_id)
        
        if not session or not session.analysis_history:
            await callback.message.edit_text("❌ Данные диагностики не найдены.")
            return
        
        # Определяем топ-3 зоны роста
        analysis = session.analysis_history
        # Рассчитываем scores для получения raw_averages
        scores = calculate_category_scores(analysis)
        raw_averages = scores.get("raw_averages", {})
        
        # Сортируем метрики по gap (10 - score)
        sorted_metrics = sorted(
            raw_averages.items(),
            key=lambda x: 10 - x[1],
            reverse=True,
        )
        focus_skills = [m[0] for m in sorted_metrics[:3]]
        
        if not focus_skills:
            focus_skills = ["depth", "systems_thinking", "creativity"]
        
        # Генерируем план
        pdp_plan = generate_pdp_plan(focus_skills, daily_time, style)
        
        # Создаём в БД
        db_plan = await create_pdp_plan(
            db,
            user_id=user.id,
            session_id=session_id,
            focus_skills=focus_skills,
            daily_time_minutes=daily_time,
            learning_style=style,
        )
        
        # Добавляем задачи
        tasks_data = []
        for week in pdp_plan.weeks:
            for day, day_tasks in week.days.items():
                for order, task in enumerate(day_tasks, 1):
                    tasks_data.append({
                        "week": week.week_number,
                        "day": day,
                        "order": order,
                        "skill": task.skill,
                        "skill_name": task.skill_name,
                        "title": task.title,
                        "description": task.description,
                        "duration_minutes": task.duration_minutes,
                        "task_type": task.task_type,
                        "resource_type": task.resource_type,
                        "resource_title": task.resource_title,
                        "resource_url": task.resource_url,
                        "xp": task.xp,
                        "status": "pending",
                    })
        
        total = await add_tasks_batch(db, db_plan.id, tasks_data)
        await update_pdp_progress(db, db_plan.id, total_tasks=total)
        
        await db.commit()
    
    # Показываем результат
    text = f"""🎉 <b>ПЛАН СОЗДАН!</b>

<b>Твой фокус на 30 дней:</b>
{chr(10).join(f'• {name}' for name in pdp_plan.focus_skill_names)}

<b>Время:</b> {daily_time} мин/день
<b>Стиль:</b> {style}
<b>Всего задач:</b> {pdp_plan.total_tasks}

<i>Начнём с первой задачи?</i>"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_pdp_main_keyboard(db_plan.id),
    )


# ==================== VIEW PLAN ====================

@router.callback_query(F.data.startswith("pdp:main:"))
async def show_pdp_main(callback: CallbackQuery):
    """Главный экран PDP."""
    await callback.answer()
    
    plan_id = int(callback.data.split(":")[2])
    
    async with get_session() as db:
        stats = await get_pdp_stats(db, plan_id)
        
        if not stats:
            await callback.message.edit_text("❌ План не найден.")
            return
        
        text = f"""🎯 <b>ТВОЙ ПЛАН РАЗВИТИЯ</b>

<b>Прогресс:</b> {stats['completed_tasks']}/{stats['total_tasks']} задач ({stats['completion_rate']}%)
<b>Неделя:</b> {stats['current_week']}/4
<b>Серия:</b> 🔥 {stats['current_streak']} дней

<b>Очки:</b> {stats['total_points']} ⭐
<b>Бейджи:</b> {stats['badges_count']} 🏅

<i>Выбери действие:</i>"""
        
        await callback.message.edit_text(
            text,
            reply_markup=get_pdp_main_keyboard(plan_id),
        )


@router.callback_query(F.data.startswith("pdp:today:"))
async def show_today_task(callback: CallbackQuery):
    """Показать задачу на сегодня."""
    await callback.answer()
    
    plan_id = int(callback.data.split(":")[2])
    
    async with get_session() as db:
        task = await get_today_task(db, plan_id)
        
        if not task:
            await callback.message.edit_text(
                "🎉 <b>Все задачи на сегодня выполнены!</b>\n\n"
                "Отличная работа! Отдохни или посмотри план на неделю.",
                reply_markup=get_back_to_pdp_keyboard(plan_id),
            )
            return
        
        type_name = TASK_TYPES.get(task.task_type, "📌 Задача")
        
        text = f"""📅 <b>ЗАДАЧА НА СЕГОДНЯ</b>

<b>{type_name}</b>
<b>{task.title}</b>

{task.description}

⏱ <b>Время:</b> {task.duration_minutes} мин
🎯 <b>Навык:</b> {task.skill_name}"""
        
        if task.resource_title:
            text += f"\n\n📚 <b>Ресурс:</b> {task.resource_title}"
            if task.resource_url:
                text += f"\n🔗 {task.resource_url}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_task_keyboard(task.id, plan_id),
        )


@router.callback_query(F.data.startswith("pdp:view_task:"))
async def show_specific_task(callback: CallbackQuery):
    """Показать конкретную задачу."""
    await callback.answer()
    
    parts = callback.data.split(":")
    task_id = int(parts[2])
    plan_id = int(parts[3])
    
    async with get_session() as db:
        task = await get_task_by_id(db, task_id)
        
        if not task:
            await callback.message.edit_text(
                "❌ Задача не найдена.",
                reply_markup=get_back_to_pdp_keyboard(plan_id),
            )
            return
        
        type_name = TASK_TYPES.get(task.task_type, "📌 Задача")
        
        text = f"""📅 <b>ЗАДАЧА</b>

<b>{type_name}</b>
<b>{task.title}</b>

{task.description}

⏱ <b>Время:</b> {task.duration_minutes} мин
🎯 <b>Навык:</b> {task.skill_name}"""
        
        if task.resource_title:
            text += f"\n\n📚 <b>Ресурс:</b> {task.resource_title}"
            if task.resource_url:
                text += f"\n🔗 {task.resource_url}"
        
        # Если задача выполнена, показываем соответствующий статус
        if task.status == "completed":
             text += "\n\n✅ <b>Выполнено!</b>"
        elif task.status == "skipped":
             text += "\n\n⏭️ <b>Пропущено.</b>"

        await callback.message.edit_text(
            text,
            reply_markup=get_task_keyboard(task.id, plan_id),
        )


@router.callback_query(F.data.startswith("pdp:week:"))
async def show_week_plan(callback: CallbackQuery, bot: Bot):
    """Показать план на неделю."""
    await callback.answer()
    
    parts = callback.data.split(":")
    week_num = int(parts[2])
    plan_id = int(parts[3])
    
    async with get_session() as db:
        tasks = await get_tasks_for_week(db, plan_id, week_num)
        
        if not tasks:
            await callback.message.edit_text(
                f"📅 <b>Неделя {week_num}</b>\n\n"
                "Задачи ещё не созданы.",
                reply_markup=get_back_to_pdp_keyboard(plan_id),
            )
            return
        
        # Группируем по дням
        days = {}
        for task in tasks:
            if task.day not in days:
                days[task.day] = []
            days[task.day].append(task)
        
        text = f"📅 <b>НЕДЕЛЯ {week_num}/4</b>\n\n"
        
        for day in range(1, 8):
            day_name = DAY_NAMES.get(day, str(day))
            day_tasks = days.get(day, [])
            
            if day_tasks:
                task = day_tasks[0]
                status_emoji = "✅" if task.status == "completed" else "⏭️" if task.status == "skipped" else "🔲"
                type_emoji = TASK_TYPES.get(task.task_type, "📌").split()[0]
                text += f"<b>{day_name}:</b> {status_emoji} {type_emoji} {task.title}\n"
            else:
                text += f"<b>{day_name}:</b> —\n"
        
        # Статистика недели
        completed = sum(1 for t in tasks if t.status == "completed")
        total = len(tasks)
        text += f"\n<b>Выполнено:</b> {completed}/{total}"
        
        # Кнопки
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📊 Итоги недели", callback_data=f"pdp:weekly:{week_num}:{plan_id}"),
        )
        builder.row(
            InlineKeyboardButton(text="◀️ К плану", callback_data=f"pdp:main:{plan_id}"),
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
        )


# ==================== TASK ACTIONS ====================

@router.callback_query(F.data.startswith("pdp:done:"))
async def mark_task_done(callback: CallbackQuery):
    """Отметить задачу выполненной."""
    parts = callback.data.split(":")
    task_id = int(parts[2])
    plan_id = int(parts[3])
    
    await callback.answer("✅ Отлично!")
    
    async with get_session() as db:
        # Получаем задачу для XP
        task = await get_task_by_id(db, task_id)
        if not task:
            await callback.message.edit_text("❌ Задача не найдена")
            return

        # Выполняем задачу
        await complete_task(db, task_id)
        
        # Обновляем прогресс плана
        stats = await get_pdp_stats(db, plan_id)
        await update_pdp_progress(
            db, plan_id,
            completed_tasks=stats['completed_tasks'],
        )
        
        # Обновляем streak
        streak_result = await update_streak(db, plan_id, completed_today=True)
        
        # Добавляем очки
        points = task.xp
        if streak_result['current_streak'] >= 3:
            points += 5  # Бонус за streak
        new_total = await add_points(db, plan_id, points)
        
        # Проверяем бейджи
        badges_earned = []
        
        # Первая задача
        if stats['completed_tasks'] == 1:
            if await add_badge(db, plan_id, "first_task", BADGES["first_task"]["name"]):
                badges_earned.append(BADGES["first_task"])
        
        # Streak бейджи
        streak = streak_result['current_streak']
        if streak >= 3:
            if await add_badge(db, plan_id, "streak_3", BADGES["streak_3"]["name"]):
                badges_earned.append(BADGES["streak_3"])
        if streak >= 7:
            if await add_badge(db, plan_id, "streak_7", BADGES["streak_7"]["name"]):
                badges_earned.append(BADGES["streak_7"])
        if streak >= 14:
            if await add_badge(db, plan_id, "streak_14", BADGES["streak_14"]["name"]):
                badges_earned.append(BADGES["streak_14"])
        
        await db.commit()
    
    # Формируем ответ
    text = f"""✅ <b>Задача выполнена!</b>

+{points} очков ⭐
Всего: {new_total} очков

🔥 Серия: {streak_result['current_streak']} дней"""
    
    if streak_result.get('new_best'):
        text += " (новый рекорд!)"
    
    if badges_earned:
        text += "\n\n🏅 <b>Новые бейджи:</b>"
        for badge in badges_earned:
            text += f"\n{badge['name']}"
    
    text += "\n\n<i>Продолжай в том же духе!</i>"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_pdp_keyboard(plan_id),
    )


@router.callback_query(F.data.startswith("pdp:skip:"))
async def skip_task_callback(callback: CallbackQuery):
    """Пропустить задачу."""
    parts = callback.data.split(":")
    task_id = int(parts[2])
    plan_id = int(parts[3])
    
    await callback.answer("⏭️ Пропущено")
    
    async with get_session() as db:
        await skip_task(db, task_id)
        
        stats = await get_pdp_stats(db, plan_id)
        await update_pdp_progress(
            db, plan_id,
            skipped_tasks=stats['skipped_tasks'],
        )
        
        await db.commit()
    
    await callback.message.edit_text(
        "⏭️ <b>Задача пропущена</b>\n\n"
        "Ничего страшного! Главное — не бросать совсем.\n\n"
        "<i>Может, сделаешь завтра?</i>",
        reply_markup=get_back_to_pdp_keyboard(plan_id),
    )


@router.callback_query(F.data.startswith("pdp:remind_menu:"))
async def remind_menu_callback(callback: CallbackQuery):
    """Меню выбора времени напоминания."""
    parts = callback.data.split(":")
    task_id = int(parts[2])
    plan_id = int(parts[3])

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🕐 Через 1 час", callback_data=f"pdp:remind_set:{task_id}:{plan_id}:60"),
        InlineKeyboardButton(text="🕒 Через 3 часа", callback_data=f"pdp:remind_set:{task_id}:{plan_id}:180"),
    )
    builder.row(
        InlineKeyboardButton(text="🌅 Завтра утром", callback_data=f"pdp:remind_set:{task_id}:{plan_id}:tomorrow"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"pdp:main:{plan_id}"),
    )
    
    await callback.message.edit_text(
        "⏰ <b>Когда напомнить о задаче?</b>",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("pdp:remind_set:"))
async def remind_set_callback(callback: CallbackQuery):
    """Установить напоминание."""
    parts = callback.data.split(":")
    task_id = int(parts[2])
    plan_id = int(parts[3])
    time_val = parts[4]
    
    now = datetime.utcnow()
    
    if time_val == "tomorrow":
        # Завтра в 9:00 MSK (6:00 UTC)
        tomorrow = now + timedelta(days=1)
        remind_at = tomorrow.replace(hour=6, minute=0, second=0, microsecond=0)
        if remind_at < now:
            remind_at += timedelta(days=1)
    else:
        minutes = int(time_val)
        remind_at = now + timedelta(minutes=minutes)
        
    async with get_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        await schedule_task_reminder(db, user.id, task_id, remind_at)
        await db.commit()
        
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К плану", callback_data=f"pdp:main:{plan_id}"))
    
    await callback.message.edit_text(
        f"✅ <b>Напоминание установлено!</b>\n\nЯ напомню тебе о задаче {remind_at.strftime('%d.%m в %H:%M')} (UTC).",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("pdp:note:"))
async def add_note_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление заметки."""
    parts = callback.data.split(":")
    task_id = int(parts[2])
    plan_id = int(parts[3])
    
    await callback.answer()
    
    await state.update_data(task_id=task_id, plan_id=plan_id)
    await state.set_state(PdpStates.adding_note)
    
    await callback.message.edit_text(
        "📝 <b>Добавь заметку</b>\n\n"
        "Напиши, что узнал или что хочешь запомнить.\n\n"
        "<i>Отправь текст сообщением:</i>",
    )


@router.message(PdpStates.adding_note)
async def save_note(message: Message, state: FSMContext):
    """Сохранить заметку."""
    data = await state.get_data()
    task_id = data.get("task_id")
    plan_id = data.get("plan_id")
    
    await state.clear()
    
    if not task_id:
        await message.answer("❌ Ошибка. Попробуй /pdp")
        return
    
    async with get_session() as db:
        from sqlalchemy import update
        from src.db.models import PdpTask
        
        stmt = (
            update(PdpTask)
            .where(PdpTask.id == task_id)
            .values(user_note=message.text)
        )
        await db.execute(stmt)
        await db.commit()
    
    await message.answer(
        "📝 <b>Заметка сохранена!</b>\n\n"
        f"<i>{message.text[:100]}{'...' if len(message.text) > 100 else ''}</i>",
        reply_markup=get_back_to_pdp_keyboard(plan_id),
    )


# ==================== STATS ====================

@router.callback_query(F.data.startswith("pdp:stats:"))
async def show_stats(callback: CallbackQuery):
    """Показать статистику."""
    await callback.answer()
    
    plan_id = int(callback.data.split(":")[2])
    
    async with get_session() as db:
        stats = await get_pdp_stats(db, plan_id)
        plan = await get_active_pdp_plan(db, (await get_user_by_telegram_id(db, callback.from_user.id)).id)
        
        if not stats:
            await callback.message.edit_text("❌ Статистика недоступна.")
            return
        
        # Прогресс-бар
        progress = stats['completion_rate']
        bar_filled = int(progress / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        
        text = f"""📈 <b>МОЙ ПРОГРЕСС</b>

<code>{bar}</code> {progress}%

<b>Задачи:</b>
✅ Выполнено: {stats['completed_tasks']}
⏭️ Пропущено: {stats['skipped_tasks']}
🔲 Осталось: {stats['pending_tasks']}

<b>Геймификация:</b>
⭐ Очки: {stats['total_points']}
🔥 Текущая серия: {stats['current_streak']} дней
🏆 Лучшая серия: {stats['best_streak']} дней
🏅 Бейджи: {stats['badges_count']}"""
        
        # Показываем бейджи если есть
        if plan and plan.badges:
            text += "\n\n<b>Мои бейджи:</b>"
            for badge_id, badge_data in plan.badges.items():
                badge_info = BADGES.get(badge_id, {})
                text += f"\n{badge_info.get('name', badge_data.get('name', badge_id))}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_back_to_pdp_keyboard(plan_id),
        )


# ==================== SETTINGS ====================

@router.callback_query(F.data.startswith("pdp:settings:"))
async def show_settings(callback: CallbackQuery):
    """Показать настройки."""
    await callback.answer()
    
    plan_id = int(callback.data.split(":")[2])
    
    async with get_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        if not user:
            return
        
        reminder = await get_or_create_reminder(db, user.id)
        await db.commit()
    
    status = "✅ Включены" if reminder.enabled else "❌ Выключены"
    
    builder = InlineKeyboardBuilder()
    
    if reminder.enabled:
        builder.row(
            InlineKeyboardButton(text="🔕 Выключить напоминания", callback_data=f"pdp:reminder:off:{plan_id}"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🔔 Включить напоминания", callback_data=f"pdp:reminder:on:{plan_id}"),
        )
    
    builder.row(
        InlineKeyboardButton(text="⏰ Изменить время", callback_data=f"pdp:reminder:time:{plan_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"pdp:main:{plan_id}"),
    )
    
    await callback.message.edit_text(
        f"""⚙️ <b>НАСТРОЙКИ PDP</b>

<b>Напоминания:</b> {status}
<b>Время:</b> {reminder.reminder_time}
<b>Часовой пояс:</b> {reminder.timezone}

<i>Ежедневные напоминания помогают не забывать о плане!</i>""",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("pdp:reminder:"))
async def toggle_reminder(callback: CallbackQuery):
    """Переключить напоминания."""
    parts = callback.data.split(":")
    action = parts[2]
    plan_id = int(parts[3])
    
    await callback.answer()
    
    async with get_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        if not user:
            return
        
        if action == "on":
            await update_reminder_settings(db, user.id, enabled=True)
            await db.commit()
            await callback.message.edit_text(
                "🔔 <b>Напоминания включены!</b>\n\n"
                f"Буду напоминать каждый день.",
                reply_markup=get_back_to_pdp_keyboard(plan_id),
            )
        elif action == "off":
            await update_reminder_settings(db, user.id, enabled=False)
            await db.commit()
            await callback.message.edit_text(
                "🔕 <b>Напоминания выключены.</b>\n\n"
                "Не забывай про /pdp!",
                reply_markup=get_back_to_pdp_keyboard(plan_id),
            )
        elif action == "time":
            # Показываем выбор времени
            builder = InlineKeyboardBuilder()
            for hour in [8, 9, 10, 11, 12, 18, 19, 20, 21]:
                builder.button(text=f"{hour}:00", callback_data=f"pdp:settime:{hour}:{plan_id}")
            builder.adjust(3)
            builder.row(
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"pdp:settings:{plan_id}"),
            )
            
            await callback.message.edit_text(
                "⏰ <b>Выбери время напоминания:</b>",
                reply_markup=builder.as_markup(),
            )


@router.callback_query(F.data.startswith("pdp:settime:"))
async def set_reminder_time(callback: CallbackQuery):
    """Установить время напоминания."""
    parts = callback.data.split(":")
    hour = int(parts[2])
    plan_id = int(parts[3])
    
    await callback.answer(f"⏰ Время: {hour}:00")
    
    async with get_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        if user:
            await update_reminder_settings(db, user.id, reminder_time=f"{hour:02d}:00")
            await db.commit()
    
    await callback.message.edit_text(
        f"✅ <b>Время установлено: {hour}:00</b>\n\n"
        "Буду напоминать каждый день в это время!",
        reply_markup=get_back_to_pdp_keyboard(plan_id),
    )


# ==================== WEEKLY SUMMARY ====================

@router.callback_query(F.data.startswith("pdp:weekly:"))
async def show_weekly_summary(callback: CallbackQuery):
    """Показать итоги недели."""
    await callback.answer()
    
    parts = callback.data.split(":")
    week_num = int(parts[2])
    plan_id = int(parts[3])
    
    async with get_session() as db:
        tasks = await get_tasks_for_week(db, plan_id, week_num)
        plan = await get_active_pdp_plan(db, (await get_user_by_telegram_id(db, callback.from_user.id)).id)
        
        if not tasks:
            await callback.message.edit_text(
                f"📅 <b>Неделя {week_num}</b>\n\nЗадачи не найдены.",
                reply_markup=get_back_to_pdp_keyboard(plan_id),
            )
            return
        
        # Считаем статистику
        completed = sum(1 for t in tasks if t.status == "completed")
        skipped = sum(1 for t in tasks if t.status == "skipped")
        pending = sum(1 for t in tasks if t.status == "pending")
        total = len(tasks)
        
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        # Группируем по навыкам
        skills_progress = {}
        for task in tasks:
            if task.skill_name not in skills_progress:
                skills_progress[task.skill_name] = {"done": 0, "total": 0}
            skills_progress[task.skill_name]["total"] += 1
            if task.status == "completed":
                skills_progress[task.skill_name]["done"] += 1
        
        # Прогресс-бар
        bar_filled = int(completion_rate / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        
        text = f"""📊 <b>ИТОГИ НЕДЕЛИ {week_num}</b>

<code>{bar}</code> {completion_rate:.0f}%

<b>Задачи:</b>
✅ Выполнено: {completed}
⏭️ Пропущено: {skipped}
🔲 Осталось: {pending}

<b>По навыкам:</b>"""
        
        for skill_name, data in skills_progress.items():
            emoji = "✅" if data["done"] == data["total"] else "🔄"
            text += f"\n{emoji} {skill_name}: {data['done']}/{data['total']}"
        
        # Мотивация в зависимости от результата
        if completion_rate >= 80:
            text += "\n\n🎉 <b>Отличная неделя!</b> Ты молодец!"
        elif completion_rate >= 50:
            text += "\n\n👍 <b>Хорошая работа!</b> Продолжай в том же духе."
        elif completion_rate > 0:
            text += "\n\n💪 <b>Есть прогресс!</b> Следующая неделя будет лучше."
        else:
            text += "\n\n🤔 <b>Неделя без прогресса.</b> Не сдавайся!"
        
        # Кнопки
        builder = InlineKeyboardBuilder()
        if week_num < 4:
            builder.row(
                InlineKeyboardButton(
                    text=f"➡️ Перейти к неделе {week_num + 1}",
                    callback_data=f"pdp:week:{week_num + 1}:{plan_id}",
                ),
            )
        builder.row(
            InlineKeyboardButton(text="📝 Рефлексия недели", callback_data=f"pdp:reflect:{week_num}:{plan_id}"),
        )
        builder.row(
            InlineKeyboardButton(text="◀️ К плану", callback_data=f"pdp:main:{plan_id}"),
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())


# ==================== WEEKLY REFLECTION (CHECK-IN) ====================

class ReflectionStates(StatesGroup):
    """Состояния для рефлексии."""
    writing_reflection = State()


@router.callback_query(F.data.startswith("pdp:reflect:"))
async def start_reflection(callback: CallbackQuery, state: FSMContext):
    """Начать рефлексию недели (шаг 1: оценка сложности)."""
    await callback.answer()
    
    parts = callback.data.split(":")
    week_num = int(parts[2])
    plan_id = int(parts[3])
    
    await state.update_data(week_num=week_num, plan_id=plan_id)
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="😅 Было тяжело", callback_data=f"pdp:reflect_diff:hard"),
        InlineKeyboardButton(text="👌 Нормально", callback_data=f"pdp:reflect_diff:ok"),
    )
    builder.row(
        InlineKeyboardButton(text="😎 Слишком легко", callback_data=f"pdp:reflect_diff:easy"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"pdp:weekly:{week_num}:{plan_id}"))

    await callback.message.edit_text(
        f"""📝 <b>РЕФЛЕКСИЯ НЕДЕЛИ {week_num}</b>

Чтобы следующая неделя была эффективнее, оцени нагрузку:""",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("pdp:reflect_diff:"))
async def handle_reflection_difficulty(callback: CallbackQuery, state: FSMContext):
    """Обработка оценки сложности и переход к текстовой рефлексии."""
    difficulty = callback.data.split(":")[2]
    data = await state.get_data()
    week_num = data.get("week_num")
    plan_id = data.get("plan_id")
    
    msg_prefix = ""
    
    async with get_session() as db:
        if difficulty == "hard":
            # Reduce duration for next week tasks
            from sqlalchemy import update
            from src.db.models import PdpTask
            
            stmt = (
                update(PdpTask)
                .where(PdpTask.plan_id == plan_id)
                .where(PdpTask.week == week_num + 1)
                .where(PdpTask.status == 'pending')
                .values(duration_minutes=15)
            )
            await db.execute(stmt)
            await db.commit()
            msg_prefix = "👌 <b>Понял, снизил нагрузку на следующую неделю.</b>\n\n"
        elif difficulty == "easy":
            msg_prefix = "💪 <b>Отлично! В следующей неделе дам задачи посложнее.</b>\n\n"
        else:
            msg_prefix = "✅ <b>Супер! Продолжаем в том же темпе.</b>\n\n"

    await state.update_data(difficulty=difficulty)
    await state.set_state(ReflectionStates.writing_reflection)
    
    await callback.message.edit_text(
        f"""{msg_prefix}📝 <b>А теперь немного мыслей:</b>

1. Что получилось на этой неделе?
2. Что было сложно?
3. Что хочешь изменить?

<i>Напиши ответ одним сообщением:</i>"""
    )


@router.message(ReflectionStates.writing_reflection)
async def save_reflection(message: Message, state: FSMContext):
    """Сохранить рефлексию."""
    data = await state.get_data()
    week_num = data.get("week_num", 1)
    plan_id = data.get("plan_id")
    difficulty = data.get("difficulty", "normal")
    
    await state.clear()
    
    # Сохраняем рефлексию в БД
    async with get_session() as db:
        from src.db.repositories.pdp_repo import update_pdp_reflection
        
        # Сохраняем данные
        reflection_data = {
            "difficulty": difficulty,
            "text": message.text,
            "date": datetime.utcnow().isoformat()
        }
        await update_pdp_reflection(db, plan_id, week_num, reflection_data)

        # Получаем план для начисления бонусов
        plan = await get_active_pdp_plan(db, (await get_user_by_telegram_id(db, message.from_user.id)).id)
        
        if plan:
            # Добавляем бейдж за рефлексию
            badge_id = f"reflect_week_{week_num}"
            badge_name = f"🪞 Рефлексия W{week_num}"
            is_new = await add_badge(db, plan.id, badge_id, badge_name)
            
            # Добавляем очки
            points = await add_points(db, plan.id, 15)
            
            await db.commit()
            
            text = f"""✅ <b>Рефлексия сохранена!</b>

+15 очков за рефлексию ⭐

<i>Твои мысли:</i>
{message.text[:300]}{'...' if len(message.text) > 300 else ''}"""
            
            if is_new:
                text += f"\n\n🏅 Новый бейдж: {badge_name}"
            
            await message.answer(
                text,
                reply_markup=get_back_to_pdp_keyboard(plan.id),
            )
        else:
            await message.answer("❌ План не найден. Попробуй /pdp")


# ==================== PLAN PROGRESS & COMPLETION ====================

@router.callback_query(F.data.startswith("pdp:complete_plan:"))
async def complete_plan_callback(callback: CallbackQuery):
    """Завершить план и предложить повторную диагностику."""
    await callback.answer()
    
    plan_id = int(callback.data.split(":")[2])
    
    async with get_session() as db:
        from src.db.repositories.pdp_repo import complete_pdp_plan
        
        stats = await get_pdp_stats(db, plan_id)
        plan = await get_active_pdp_plan(db, (await get_user_by_telegram_id(db, callback.from_user.id)).id)
        
        if not plan:
            await callback.message.edit_text("❌ План не найден.")
            return
        
        # Завершаем план
        await complete_pdp_plan(db, plan_id)
        
        # Добавляем финальный бейдж
        await add_badge(db, plan_id, "plan_complete", "🏆 План завершён!")
        await add_points(db, plan_id, 100)  # Бонус за завершение
        
        await db.commit()
        
        completion_rate = stats.get('completion_rate', 0)
        
        text = f"""🎉 <b>ПОЗДРАВЛЯЕМ!</b>

Ты завершил 30-дневный план развития!

<b>Твои результаты:</b>
✅ Выполнено: {stats['completed_tasks']} задач
📈 Прогресс: {completion_rate}%
🔥 Лучшая серия: {stats['best_streak']} дней
⭐ Всего очков: {stats['total_points'] + 100}

<b>+100 бонусных очков</b> за завершение!
🏆 Бейдж: "План завершён!"

<i>Хочешь увидеть свой прогресс?</i>
Пройди повторную диагностику и сравни результаты!"""
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📊 Пройти диагностику", callback_data="restart"),
        )
        builder.row(
            InlineKeyboardButton(text="📈 История результатов", callback_data="show_history"),
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())


# ==================== COMPARE WITH DIAGNOSTIC ====================

@router.callback_query(F.data.startswith("pdp:compare:"))
async def compare_with_diagnostic(callback: CallbackQuery):
    """Сравнить результаты до и после PDP."""
    await callback.answer()
    
    plan_id = int(callback.data.split(":")[2])
    
    async with get_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        if not user:
            return
        
        # Получаем план
        plan = await get_active_pdp_plan(db, user.id)
        if not plan:
            await callback.message.edit_text("❌ План не найден.")
            return
        
        # Получаем сессию диагностики, на которой основан план
        from src.db.repositories.diagnostic_repo import get_session_by_id, get_completed_sessions
        
        old_session = await get_session_by_id(db, plan.session_id)
        
        # Получаем последнюю диагностику (если есть новая)
        sessions = await get_completed_sessions(db, user.id, limit=2)
        
        if len(sessions) < 2 or not old_session:
            # Только одна диагностика — предлагаем пройти новую
            text = """📊 <b>Сравнение результатов</b>

У тебя пока только одна диагностика.

Чтобы увидеть прогресс:
1. Заверши план развития
2. Пройди повторную диагностику
3. Сравни результаты!

<i>Рекомендуем проходить диагностику каждые 30-60 дней.</i>"""
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="📊 Пройти диагностику", callback_data="restart"),
            )
            builder.row(
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"pdp:main:{plan_id}"),
            )
            
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
            return
        
        # Есть две диагностики — сравниваем
        new_session = sessions[0]
        
        if new_session.id == old_session.id:
            # Новая диагностика ещё не пройдена
            text = """📊 <b>Сравнение результатов</b>

Ты ещё не проходил новую диагностику после начала плана.

Пройди диагностику, чтобы увидеть свой прогресс!"""
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="📊 Пройти диагностику", callback_data="restart"),
            )
            builder.row(
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"pdp:main:{plan_id}"),
            )
            
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
            return
        
        # Сравниваем баллы
        old_score = old_session.total_score or 0
        new_score = new_session.total_score or 0
        delta = new_score - old_score
        
        delta_emoji = "📈" if delta > 0 else "📉" if delta < 0 else "➡️"
        delta_sign = "+" if delta > 0 else ""
        
        # Сравниваем категории
        old_analysis = old_session.analysis_history or {}
        new_analysis = new_session.analysis_history or {}
        
        old_avgs = old_analysis.get("raw_averages", {})
        new_avgs = new_analysis.get("raw_averages", {})
        
        # Находим улучшения и снижения
        improvements = []
        declines = []
        
        focus_skills = plan.focus_skills.get("skills", []) if plan.focus_skills else []
        
        for skill in focus_skills:
            old_val = old_avgs.get(skill, 5)
            new_val = new_avgs.get(skill, 5)
            skill_delta = new_val - old_val
            
            skill_name = TASK_TYPES.get(skill, skill)  # Fallback
            from src.ai.answer_analyzer import METRIC_NAMES_RU
            skill_name = METRIC_NAMES_RU.get(skill, skill)
            
            if skill_delta > 0.5:
                improvements.append(f"🟢 {skill_name}: +{skill_delta:.1f}")
            elif skill_delta < -0.5:
                declines.append(f"🔴 {skill_name}: {skill_delta:.1f}")
        
        stats = await get_pdp_stats(db, plan_id)
        completion_rate = stats.get('completion_rate', 0)
        
        text = f"""📊 <b>СРАВНЕНИЕ РЕЗУЛЬТАТОВ</b>

<b>До PDP:</b> {old_score}/100
<b>После PDP:</b> {new_score}/100
{delta_emoji} <b>Изменение:</b> {delta_sign}{delta}

<b>Выполнение плана:</b> {completion_rate}%
"""
        
        if improvements:
            text += "\n<b>Улучшения:</b>\n" + "\n".join(improvements)
        
        if declines:
            text += "\n\n<b>Снижение:</b>\n" + "\n".join(declines)
        
        if delta > 0 and completion_rate >= 50:
            text += "\n\n🎉 <b>Отличный результат!</b> План сработал!"
        elif delta > 0:
            text += "\n\n👍 <b>Есть прогресс!</b> Продолжай развиваться."
        elif delta == 0:
            text += "\n\n🤔 <b>Результат стабильный.</b> Попробуй более интенсивный план."
        else:
            text += "\n\n💪 <b>Не сдавайся!</b> Развитие — это марафон, не спринт."
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔄 Новый план развития", callback_data="pdp:create"),
        )
        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"pdp:main:{plan_id}"),
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())

