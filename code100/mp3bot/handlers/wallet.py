"""
Обработчики для работы с кошельками
"""
import re

from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils import is_valid_ton_address, shorten_address, format_wallet_list_label
from utils.formatters import format_wallet_success_message
from database import (
    get_utc3_time, create_wallet, get_wallets, 
    delete_wallet, set_primary_wallet
)

router = Router()


class WalletStates(StatesGroup):
    waiting_for_address = State()
    waiting_for_name = State()


@router.callback_query(lambda c: c.data == "my_wallet")
async def show_wallets(callback: types.CallbackQuery, state: FSMContext):
    """Показывает список кошельков"""
    user_id = callback.from_user.id
    wallets = get_wallets(user_id)
    
    await state.update_data(wallets=wallets)

    text = (
        "<b>🪙 Your Wallets</b>\n\n"
        "<blockquote expandable>"
        "<b>Select a wallet from the list below or connect a new one:</b>"
        "</blockquote>"
    )

    rows = []

    if wallets:
        primary_wallets = [w for w in wallets if w.get("is_primary")]
        other_wallets = [w for w in wallets if not w.get("is_primary")]
        sorted_wallets = primary_wallets + other_wallets

        for w in sorted_wallets:
            wallet_id = w.get("id")
            label = format_wallet_list_label(w)
            rows.append([InlineKeyboardButton(text=label, callback_data=f"select_wallet_{wallet_id}")])
    else:
        rows.append([InlineKeyboardButton(text="🔘 None", callback_data="wallet_none")])

    if len(wallets) < 2:
        rows.append([InlineKeyboardButton(text="👛 Add Wallet", callback_data="add_wallet")])

    rows.append([InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await callback.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data == "add_wallet")
async def start_add_wallet(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс добавления кошелька"""
    text = (
        "<b>👛 Connect Wallet</b>\n\n"
        "<blockquote expandable>"
        "<b>Send the TON wallet address you want to link:</b>"
        "</blockquote>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_add_wallet")]
    ])

    msg = await callback.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.update_data(address_request_msg_id=msg.message_id)
    await state.set_state(WalletStates.waiting_for_address)
    await callback.answer()


@router.callback_query(lambda c: c.data == "cancel_add_wallet")
async def cancel_add_wallet(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет добавление кошелька"""
    from handlers.commands import show_main_menu
    
    user_id = callback.from_user.id
    wallets = get_wallets(user_id)
    await state.clear()
    await state.update_data(wallets=wallets)
    await show_main_menu(callback)


@router.message(WalletStates.waiting_for_address)
async def process_wallet_address(message: types.Message, state: FSMContext):
    """Обрабатывает введённый адрес кошелька"""
    addr = message.text.strip()
    data = await state.get_data()
    req_id = data.get("address_request_msg_id")
    
    user_id = message.from_user.id
    wallets = get_wallets(user_id)

    if not is_valid_ton_address(addr):
        text = (
            "<b>❌ Invalid TON wallet address format.</b>\n\n"
            "<blockquote expandable>"
            "<b>Please check the address and try again (should start with EQ, UQ, kQ or 0Q and be 48 chars long).</b>"
            "</blockquote>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="add_wallet")]
        ])
        
        for mid in [req_id, message.message_id]:
            if mid:
                try:
                    await message.bot.delete_message(message.chat.id, mid)
                except:
                    pass
        
        await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    for wallet in wallets:
        if wallet["address"] == addr:
            text = (
                "<b>❌ You have already added this wallet.</b>\n\n"
                "<blockquote expandable>"
                "<b>Try a different address.</b>"
                "</blockquote>"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
            ])
            
            for mid in [req_id, message.message_id]:
                if mid:
                    try:
                        await message.bot.delete_message(message.chat.id, mid)
                    except:
                        pass
            
            await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
            await state.clear()
            await state.update_data(wallets=wallets)
            return

    await state.update_data(wallet_address=addr)

    for mid in [req_id, message.message_id]:
        if mid:
            try:
                await message.bot.delete_message(message.chat.id, mid)
            except:
                pass

    text = (
        "<b>⭕️ Wallet added!</b>\n\n"
        "<blockquote expandable>"
        "<b>Would you like to name your wallet?</b>"
        "</blockquote>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Name", callback_data="add_name")],
        [InlineKeyboardButton(text="Skip", callback_data="skip_name")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="my_wallet")],
    ])

    msg = await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.update_data(name_request_msg_id=msg.message_id)
    await state.set_state(WalletStates.waiting_for_name)


@router.callback_query(lambda c: c.data == "add_name")
async def start_add_name(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс добавления имени кошелька"""
    data = await state.get_data()
    addr = data.get("wallet_address", "unknown")
    short = shorten_address(addr)

    text = (
        "<b>➕ Set Wallet Name</b>\n\n"
        "<blockquote expandable>"
        f"<b>Send the name you want to assign to <code>{short}</code></b>"
        "</blockquote>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data="wallet_added_skip")]
    ])

    msg = await callback.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.update_data(name_request_msg_id=msg.message_id)
    await callback.answer()


@router.message(WalletStates.waiting_for_name)
async def process_wallet_name(message: types.Message, state: FSMContext):
    """Обрабатывает введённое имя кошелька"""
    name = message.text.strip()
    data = await state.get_data()
    addr = data.get("wallet_address", "unknown")
    short = shorten_address(addr)
    name_request_msg_id = data.get("name_request_msg_id")
    timestamp = get_utc3_time()

    user_id = message.from_user.id
    wallets = get_wallets(user_id)
    
    if len(wallets) >= 2:
        await message.answer("<b>❌ Maximum 2 wallets allowed.</b>", parse_mode=ParseMode.HTML)
        await state.clear()
        await state.update_data(wallets=wallets)
        return

    for mid in [name_request_msg_id, message.message_id]:
        if mid:
            try:
                await message.bot.delete_message(message.chat.id, mid)
            except:
                pass

    # Создаём кошелёк в БД
    create_wallet(user_id, addr, short, name, timestamp)
    
    # Обновляем список в state
    wallets = get_wallets(user_id)
    await state.update_data(wallets=wallets)

    new_wallet = {
        "address": addr,
        "short": short,
        "name": name,
        "date_added": timestamp,
        "is_primary": False
    }

    text = format_wallet_success_message(new_wallet)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])

    await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.clear()
    await state.update_data(wallets=wallets)


@router.callback_query(lambda c: c.data == "skip_name")
async def skip_name(callback: types.CallbackQuery, state: FSMContext):
    """Пропускает добавление имени кошелька"""
    data = await state.get_data()
    addr = data.get("wallet_address", "unknown")
    short = shorten_address(addr)
    name_request_msg_id = data.get("name_request_msg_id")
    timestamp = get_utc3_time()

    user_id = callback.from_user.id
    wallets = get_wallets(user_id)
    
    if len(wallets) >= 2:
        await callback.message.edit_text("<b>❌ Maximum 2 wallets allowed.</b>", parse_mode=ParseMode.HTML)
        await state.clear()
        await state.update_data(wallets=wallets)
        return

    if name_request_msg_id:
        try:
            await callback.message.bot.delete_message(callback.message.chat.id, name_request_msg_id)
        except:
            pass

    # Создаём кошелё�� в БД без имени
    create_wallet(user_id, addr, short, None, timestamp)
    
    # Обновляем список в state
    wallets = get_wallets(user_id)
    await state.update_data(wallets=wallets)

    new_wallet = {
        "address": addr,
        "short": short,
        "name": None,
        "date_added": timestamp,
        "is_primary": False
    }

    text = format_wallet_success_message(new_wallet)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])

    await callback.message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.clear()
    await state.update_data(wallets=wallets)
    await callback.answer()


@router.callback_query(lambda c: c.data == "wallet_added_skip")
async def back_from_name(callback: types.CallbackQuery, state: FSMContext):
    """Возврат из добавления имени"""
    await skip_name(callback, state)


@router.callback_query(lambda c: re.match(r"^select_wallet_\d+$", c.data))
async def select_wallet(callback: types.CallbackQuery, state: FSMContext):
    """Выбирает кошелёк для просмотра"""
    match = re.match(r"^select_wallet_(\d+)$", callback.data)
    if not match:
        await callback.answer("Ошибка выбора", show_alert=True)
        return

    wallet_id = int(match.group(1))
    user_id = callback.from_user.id
    wallets = get_wallets(user_id)
    
    wallet = None
    for w in wallets:
        if w["id"] == wallet_id:
            wallet = w
            break
    
    if not wallet:
        await callback.answer("Кошелёк не найден", show_alert=True)
        return

    full_address = wallet.get("address", "unknown")
    name = wallet.get("name") or "Empty"
    date_added = wallet.get("date_added", "Unknown")
    short = wallet.get("short", "unknown")
    
    text = (
        f"<b>👛 Wallet {short}</b>\n"
        f"<b>🔖 Name: {name}</b>\n\n"
        "<blockquote>"
        f"<b>Date added:</b> <code>{date_added} (UTC +3)</code>\n"
        f"<b>Address:</b> <code>{full_address}</code>"
        "</blockquote>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔝 Set as Primary", callback_data=f"set_primary_{wallet_id}")],
        [InlineKeyboardButton(text="🗑 Delete", callback_data=f"delete_wallet_{wallet_id}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="my_wallet")]
    ])

    await callback.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: re.match(r"^delete_wallet_\d+$", c.data))
async def delete_wallet_handler(callback: types.CallbackQuery, state: FSMContext):
    """Удаляет кошелёк"""
    match = re.match(r"^delete_wallet_(\d+)$", callback.data)
    if not match:
        return

    wallet_id = int(match.group(1))
    user_id = callback.from_user.id
    
    delete_wallet(wallet_id)
    
    await state.update_data(wallets=[])
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.answer()
    
    # Получаем обновленный список
    wallets = get_wallets(user_id)
    await state.update_data(wallets=wallets)
    
    await show_wallets_after_delete(callback, state)


async def show_wallets_after_delete(callback: types.CallbackQuery, state: FSMContext):
    """Показывает список кошельков после удаления"""
    user_id = callback.from_user.id
    wallets = get_wallets(user_id)

    text = (
        "<b>🪙 Your Wallets</b>\n\n"
        "<blockquote expandable>"
        "<b>Select a wallet from the list below or connect a new one:</b>"
        "</blockquote>"
    )

    rows = []

    if wallets:
        primary_wallets = [w for w in wallets if w.get("is_primary")]
        other_wallets = [w for w in wallets if not w.get("is_primary")]
        sorted_wallets = primary_wallets + other_wallets

        for w in sorted_wallets:
            wallet_id = w.get("id")
            label = format_wallet_list_label(w)
            rows.append([InlineKeyboardButton(text=label, callback_data=f"select_wallet_{wallet_id}")])
    else:
        rows.append([InlineKeyboardButton(text="🔘 None", callback_data="wallet_none")])

    if len(wallets) < 2:
        rows.append([InlineKeyboardButton(text="👛 Add Wallet", callback_data="add_wallet")])

    rows.append([InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await callback.message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)


@router.callback_query(lambda c: re.match(r"^set_primary_\d+$", c.data))
async def set_primary_wallet_handler(callback: types.CallbackQuery, state: FSMContext):
    """Устанавливает кошелёк как основной"""
    match = re.match(r"^set_primary_(\d+)$", callback.data)
    if not match:
        await callback.answer("Ошибка", show_alert=True)
        return

    wallet_id = int(match.group(1))
    user_id = callback.from_user.id
    
    set_primary_wallet(user_id, wallet_id)

    await callback.answer()
    
    try:
        await callback.message.delete()
    except:
        pass
    
    # Обновляем список
    wallets = get_wallets(user_id)
    await state.update_data(wallets=wallets)
    
    text = (
        "<b>🪙 Your Wallets</b>\n\n"
        "<blockquote expandable>"
        "<b>Select a wallet from the list below or connect a new one:</b>"
        "</blockquote>"
    )

    rows = []

    if wallets:
        primary_wallets = [w for w in wallets if w.get("is_primary")]
        other_wallets = [w for w in wallets if not w.get("is_primary")]
        sorted_wallets = primary_wallets + other_wallets

        for w in sorted_wallets:
            wallet_id = w.get("id")
            label = format_wallet_list_label(w)
            rows.append([InlineKeyboardButton(text=label, callback_data=f"select_wallet_{wallet_id}")])
    else:
        rows.append([InlineKeyboardButton(text="🔘 None", callback_data="wallet_none")])

    if len(wallets) < 2:
        rows.append([InlineKeyboardButton(text="👛 Add Wallet", callback_data="add_wallet")])

    rows.append([InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await callback.message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)