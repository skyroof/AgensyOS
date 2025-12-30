"""
Хендлеры для настроек пользователя и напоминаний.

Команды:
- /settings — управление настройками
- Callbacks для напоминаний (postpone, unsubscribe)
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.db.database import get_session
from src.db.repositories.user_repo import get_user_by_telegram_id
from src.db.repositories.reminder_repo import (
    get_or_create_user_settings,
    update_user_settings,
    postpone_reminder,
    cancel_reminder,
    cancel_user_reminders,
    get_user_pending_reminder,
)

logger = logging.getLogger(__name__)
router = Router()


# ==================== KEYBOARDS ====================

def get_settings_keyboard(
    diagnostic_reminders: bool,
    pdp_reminders: bool,
) -> InlineKeyboardMarkup:
    """Клавиатура настроек."""
    builder = InlineKeyboardBuilder()
    
    # Напоминания о диагностике
    diag_status = "✅" if diagnostic_reminders else "❌"
    diag_action = "off" if diagnostic_reminders else "on"
    builder.row(
        InlineKeyboardButton(
            text=f"{diag_status} Напоминания о диагностике",
            callback_data=f"settings:diagnostic:{diag_action}",
        ),
    )
    
    # Напоминания PDP
    pdp_status = "✅" if pdp_reminders else "❌"
    pdp_action = "off" if pdp_reminders else "on"
    builder.row(
        InlineKeyboardButton(
            text=f"{pdp_status} Напоминания PDP",
            callback_data=f"settings:pdp:{pdp_action}",
        ),
    )
    
    builder.row(
        InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu"),
    )
    
    return builder.as_markup()


# ==================== COMMANDS ====================

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Показать настройки."""
    async with get_session() as db:
        user = await get_user_by_telegram_id(db, message.from_user.id)
        
        if not user:
            await message.answer(
                "⚙️ <b>Настройки</b>\n\n"
                "Сначала пройди диагностику: /start"
            )
            return
        
        settings = await get_or_create_user_settings(db, user.id)
        await db.commit()
        
        text = f"""⚙️ <b>НАСТРОЙКИ</b>

<b>Напоминания:</b>
• О повторной диагностике (через 30 дней)
• О задачах PDP (ежедневно)

<i>Нажми на пункт, чтобы включить/выключить:</i>"""
        
        await message.answer(
            text,
            reply_markup=get_settings_keyboard(
                settings.diagnostic_reminders_enabled,
                settings.pdp_reminders_enabled,
            ),
        )


# ==================== SETTINGS CALLBACKS ====================

@router.callback_query(F.data.startswith("settings:diagnostic:"))
async def toggle_diagnostic_reminders(callback: CallbackQuery):
    """Переключить напоминания о диагностике."""
    action = callback.data.split(":")[2]
    new_value = action == "on"
    
    await callback.answer("✅ Сохранено" if new_value else "🔕 Отключено")
    
    async with get_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        if not user:
            return
        
        await update_user_settings(db, user.id, diagnostic_reminders_enabled=new_value)
        
        # Если отключили — отменяем все pending напоминания
        if not new_value:
            await cancel_user_reminders(db, user.id)
        
        settings = await get_or_create_user_settings(db, user.id)
        await db.commit()
        
        await callback.message.edit_reply_markup(
            reply_markup=get_settings_keyboard(
                settings.diagnostic_reminders_enabled,
                settings.pdp_reminders_enabled,
            ),
        )


@router.callback_query(F.data.startswith("settings:pdp:"))
async def toggle_pdp_reminders(callback: CallbackQuery):
    """Переключить напоминания PDP."""
    action = callback.data.split(":")[2]
    new_value = action == "on"
    
    await callback.answer("✅ Сохранено" if new_value else "🔕 Отключено")
    
    async with get_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        if not user:
            return
        
        await update_user_settings(db, user.id, pdp_reminders_enabled=new_value)
        settings = await get_or_create_user_settings(db, user.id)
        await db.commit()
        
        await callback.message.edit_reply_markup(
            reply_markup=get_settings_keyboard(
                settings.diagnostic_reminders_enabled,
                settings.pdp_reminders_enabled,
            ),
        )


# ==================== REMINDER CALLBACKS ====================

@router.callback_query(F.data.startswith("remind:postpone:"))
async def postpone_reminder_callback(callback: CallbackQuery):
    """Отложить напоминание на неделю."""
    reminder_id = int(callback.data.split(":")[2])
    
    await callback.answer("⏰ Напомню через неделю!")
    
    async with get_session() as db:
        await postpone_reminder(db, reminder_id, days=7)
        await db.commit()
    
    await callback.message.edit_text(
        "⏰ <b>Хорошо!</b>\n\n"
        "Напомню тебе через неделю.\n\n"
        "<i>Если захочешь пройти раньше — просто напиши /start</i>",
    )


@router.callback_query(F.data.startswith("remind:unsubscribe:"))
async def unsubscribe_reminder_callback(callback: CallbackQuery):
    """Отписаться от напоминаний."""
    reminder_id = int(callback.data.split(":")[2])
    
    await callback.answer("🔕 Напоминания отключены")
    
    async with get_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        
        if user:
            # Отключаем все напоминания
            await update_user_settings(db, user.id, diagnostic_reminders_enabled=False)
            await cancel_user_reminders(db, user.id)
        
        await db.commit()
    
    await callback.message.edit_text(
        "🔕 <b>Напоминания отключены</b>\n\n"
        "Ты можешь включить их снова в /settings\n\n"
        "<i>Диагностика всегда доступна по /start</i>",
    )

