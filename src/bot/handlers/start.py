"""
Обработчик команды /start и выбора параметров.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from src.bot.states import DiagnosticStates
from src.bot.keyboards.inline import (
    get_role_keyboard,
    get_experience_keyboard,
    get_start_diagnostic_keyboard,
    get_onboarding_keyboard,
)
from src.db import get_session
from src.db.repositories import get_or_create_user, create_session as create_db_session

router = Router(name="start")
logger = logging.getLogger(__name__)


WELCOME_TEXT = """
🎯 <b>Deep Diagnostic Bot</b>

Привет! Я помогу оценить твой уровень как специалиста за <b>10 глубоких вопросов</b>.

<b>Что я оценю:</b>
• Hard Skills — технические навыки
• Soft Skills — коммуникация и лидерство  
• Thinking — системное мышление
• Mindset — ценности и зрелость

<b>Важно:</b> Отвечай развёрнуто и честно. Чем подробнее ответы — тем точнее диагностика.

Время прохождения: ~15-20 минут.
"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start."""
    # Сбрасываем состояние
    await state.clear()
    
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
            await state.update_data(db_user_id=user.id)
            logger.info(f"User {user.telegram_id} (@{user.username}) started bot")
    except Exception as e:
        logger.error(f"Failed to save user: {e}")
        # Продолжаем работу даже без БД
    
    await message.answer(
        WELCOME_TEXT,
        reply_markup=get_role_keyboard(),
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


ONBOARDING_TEXT = """
📋 <b>Как проходит диагностика</b>

✅ Роль: <b>{role_name}</b>
✅ Опыт: <b>{exp_value}</b>

━━━━━━━━━━━━━━━━━━━━

<b>📝 Важные правила:</b>

1️⃣ <b>Честность важнее "правильности"</b>
   Нет плохих ответов — есть неточная диагностика из-за приукрашивания.

2️⃣ <b>Текст или голос</b>
   Пиши текстом или отправляй голосовые. Стикеры и картинки не анализируются.

3️⃣ <b>Развёрнуто = точнее</b>
   На каждый вопрос достаточно 2-5 минут. Чем больше деталей — тем точнее результат.

━━━━━━━━━━━━━━━━━━━━

<b>💡 Пример хорошего ответа:</b>

<i>Вопрос: "Расскажи о сложном проекте"</i>

❌ Плохо: "Делал редизайн, было сложно, справился."

✅ Хорошо: "Редизайн B2B-портала для финтеха. 50k пользователей. 
Главная сложность — 4 разных UI за 5 лет. Провёл 12 интервью, 
нашёл топ-5 проблем. Создал дизайн-систему. Результат: 
время разработки -30%, NPS +15. Ошибка — недооценил 
сопротивление команды, пришлось переделывать документацию."

<b>Формула:</b> Контекст → Действия → Результат → Выводы

━━━━━━━━━━━━━━━━━━━━
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
    
    # Создаём сессию диагностики в БД
    try:
        async with get_session() as db:
            db_user_id = data.get("db_user_id")
            if db_user_id:
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
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
    
    # Показываем онбординг с правилами
    onboarding = ONBOARDING_TEXT.format(
        role_name=data['role_name'],
        exp_value=exp_value,
    )
    
    await callback.message.edit_text(
        onboarding,
        reply_markup=get_onboarding_keyboard(),
    )
    await state.set_state(DiagnosticStates.onboarding)
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
