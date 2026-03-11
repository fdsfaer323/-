"""
Обработчики команд (/start, меню, навигация)
"""
from typing import Union

from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from database import (
    create_user, get_user, get_utc3_date,
    get_deal, update_deal_buyer, get_seller_chat,
)
from handlers.deals import show_buyer_deal_screen, notify_seller_buyer_joined

# Создаём router для этого модуля
router = Router()


async def show_main_menu(obj: Union[types.Message, types.CallbackQuery]):
    """Показывает главное меню"""
    text = (
        "<b>👋 Greetings!</b>\n\n"
        "<b>💼 Reliable escrow service for smooth and protected deals</b>\n"
        "<b>🐇 Fast, automated, and built for efficiency</b>\n\n"
        "<blockquote expandable>"
        "<b>◼️ Service fee — 1%</b>\n"
        "<b>◼️ PM — @tiltin</b>"
        "</blockquote>\n\n"
        "<b>🛡 Every deal is secured and protected</b>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Create Deal", callback_data="create_deal"),
            InlineKeyboardButton(text="💰 My Wallet", callback_data="my_wallet"),
        ],
        [
            InlineKeyboardButton(text="👤 Profile", callback_data="profile"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="settings"),
        ]
    ])

    if isinstance(obj, types.Message):
        await obj.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await obj.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        await obj.answer()


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    
    # Создаём/получаем пользователя
    if not get_user(user_id):
        create_user(user_id, username, get_utc3_date())
    
    # Загружаем кошельки в state
    from database import get_wallets
    wallets = get_wallets(user_id)
    await state.update_data(wallets=wallets)
    
    args = message.text.split()
    if len(args) > 1:
        deal_link = args[1]
        
        if deal_link.startswith("deal_"):
            # Парсим deal_id из ссылки
            try:
                parts = deal_link.split("_")
                deal_id = int(parts[1])
                deal = get_deal(deal_id)
                
                if deal and deal.get("status") == "waiting_for_payment":
                    await show_buyer_deal_screen(message, deal, state)
                    
                    seller_chat_id = get_seller_chat(deal_id)
                    if seller_chat_id:
                        buyer_user = message.from_user
                        await notify_seller_buyer_joined(
                            seller_chat_id=seller_chat_id,
                            deal=deal,
                            buyer_id=buyer_user.id,
                            buyer_username=buyer_user.username or "unknown"
                        )
                        
                        # Сохраняем информацию о покупателе
                        update_deal_buyer(deal_id, buyer_user.id, buyer_user.username or "unknown")
                    
                    return
            except:
                pass
    
    await show_main_menu(message)


@router.callback_query(lambda c: c.data == "to_main_menu")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    """Вернуться в главное меню"""
    data = await state.get_data()
    wallets = data.get("wallets", [])
    await state.clear()
    await state.update_data(wallets=wallets)
    await show_main_menu(callback)


@router.callback_query(lambda c: c.data == "wallet_none")
async def wallet_none(callback: types.CallbackQuery):
    """Обработка нажатия на 'None' в списке кошельков"""
    await callback.answer("Пока нет подключённых кошельков", show_alert=True)


@router.callback_query()
async def catch_all_callbacks(callback: types.CallbackQuery):
    """Обработчик неизвестных callback'ов (в конце!)"""
    await callback.answer("Неизвестная команда", show_alert=True)