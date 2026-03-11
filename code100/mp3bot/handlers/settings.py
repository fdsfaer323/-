"""
Обработчики для настроек
"""
from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

router = Router()


@router.callback_query(lambda c: c.data == "settings")
async def show_settings(callback: types.CallbackQuery):
    """Показывает меню настроек"""
    text = "<b>⚙️ Your Settings</b>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Language", callback_data="language_settings")],
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])

    await callback.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data == "language_settings")
async def language_settings(callback: types.CallbackQuery):
    """Настройки языка"""
    await callback.answer("🌍 Language settings — в разработке", show_alert=True)