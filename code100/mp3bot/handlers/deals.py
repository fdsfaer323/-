"""
Обработчики для создания и управления сделками
"""
from typing import Optional

from aiogram import Router, Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils import is_valid_amount, get_deal_type_emoji
from database import (
    create_user, get_user, get_utc3_date, get_utc3_time,
    create_deal, get_deal, update_deal_status, update_deal_buyer,
    create_channel, get_channel,
    set_seller_chat, get_seller_chat,
    generate_deal_link, generate_memo
)
import logging

logger = logging.getLogger(__name__)
router = Router()
bot: Optional[Bot] = None


def set_bot(b: Bot):
    """Устанавливает экземпляр бота"""
    global bot
    bot = b


class DealStates(StatesGroup):
    waiting_for_offer = State()
    waiting_for_currency = State()
    waiting_for_amount = State()


class ChannelStates(StatesGroup):
    waiting_for_currency_channel = State()
    waiting_for_amount_channel = State()


async def show_buyer_deal_screen(message: types.Message, deal: dict, state: FSMContext):
    """Показывает экран сделки для покупателя"""
    deal_id = deal.get("id")
    deal_type = deal.get("deal_type", "unknown")
    seller_username = deal.get("seller_username", "unknown")
    seller_id = deal.get("seller_id", "unknown")
    offer = deal.get("offer", "unknown")
    amount = float(deal.get("amount", "0"))
    currency = deal.get("currency", "TON")
    memo = deal.get("memo", "unknown")
    
    commission = amount * 0.01
    total_amount = amount + commission
    total_amount_str = f"{total_amount:.2f}".rstrip('0').rstrip('.')
    
    deal_type_emoji = get_deal_type_emoji(deal_type)
    
    text = (
        f"<b>💼 Deal #{deal_id}</b>\n"
        f"<b>Deal type: {deal_type_emoji} {deal_type.capitalize()}</b>\n\n"
        f"<b>👤 Your role: Buyer</b>\n"
        f"<b>⏳ Payment time: 15 minutes</b>\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "<blockquote>"
        f"<b>🧑 Seller</b>\n"
        f"<b>@{seller_username} (<code>{seller_id}</code>)</b>\n"
        f"<b>• Completed deals: 0</b>\n\n"
        f"<b>📦 You receive</b>\n"
        f"<code>{offer}</code>\n\n"
        f"<b>💎 You pay</b>\n"
        f"<code>{total_amount_str} {currency}</code>"
        "</blockquote>\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "<blockquote>"
        f"<b>👛 Payment wallet</b>\n"
        f"<code>UQDxPxTu1Xskt-k01azOKw2z3gt3qWFx71if7zUl9FihKZpP</code>\n\n"
        f"<b>📝 Required memo</b>\n"
        f"<code>{memo}</code>\n\n"
        f"<b>⚠️ Important</b>\n"
        f"<b>Send exactly </b><code>{total_amount_str} {currency}</code><b> and include the memo in the transaction.</b>"
        "</blockquote>\n\n"
        "<b>🤖 Payment will be confirmed automatically after it is detected on the blockchain.</b>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆘 Support", url="https://t.me/tiltin")],
        [InlineKeyboardButton(text="🔴 Terminate Deal", callback_data=f"buyer_terminate_{deal_id}")]
    ])
    
    await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.update_data(current_deal_id=deal_id)


async def notify_seller_buyer_joined(seller_chat_id: int, deal: dict, buyer_id: int, buyer_username: str):
    """Уведомляет продавца о присоединении покупателя"""
    deal_id = deal.get("id")
    
    text = (
        f"<b>👤 Buyer Joined</b>\n"
        f"<b>User: @{buyer_username} (<code>{buyer_id}</code>)</b>\n"
        f"<b>Deal: #<code>{deal_id}</code></b>\n\n"
        f"<b>• Buyer completed deals: 0</b>\n\n"
        "<blockquote>"
        "<b>🔒 Security reminder</b>\n"
        "<b>Confirm that this is the same person you arranged the deal with.</b>"
        "</blockquote>\n\n"
        "<b>❗️ Do not deliver the item(s) until the bot confirms the payment.</b>"
    )
    
    try:
        await bot.send_message(
            chat_id=seller_chat_id,
            text=text,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления продавцу: {e}")


@router.callback_query(lambda c: c.data == "create_deal")
async def create_deal_menu(callback: types.CallbackQuery):
    """Меню выбора типа сделки"""
    text = "<b>🔭 Choose deal type:</b>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Gifts", callback_data="deal_gifts")],
        [InlineKeyboardButton(text="📢 Channels", callback_data="deal_channels")],
        [InlineKeyboardButton(text="👾 Accounts", callback_data="deal_accounts")],
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])

    await callback.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


async def check_wallet_and_proceed(callback: types.CallbackQuery, state: FSMContext, deal_type: str):
    """Проверяет наличие кошелька и переходит к созданию сделки"""
    data = await state.get_data()
    wallets = data.get("wallets", [])

    if not wallets:
        text = (
            "<b>⚠️ Creating a Deal</b>\n\n"
            "<blockquote expandable>"
            "<b>🔸 Add your wallet in the main menu first to continue.</b>"
            "</blockquote>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
        ])

        await callback.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        await callback.answer()
        return False

    if deal_type == "channels":
        text = (
            "<b>🤖 Channel Access Required</b>\n\n"
            "<blockquote>"
            "<b>Add the bot as an administrator to the channel you are selling.</b>\n"
            "<b>Use the button below to select the channel.</b>\n"
            "<b>Make sure you add it from your current account.</b> <b>👇</b>"
            "</blockquote>"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Bot", url=f"https://t.me/{(await bot.get_me()).username}?startchannel=true&admin=change_info,manage_messages,invite_users,ban_users")],
            [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
        ])

        await callback.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        await callback.answer("⚠️ Make sure Cloud Password is enabled and you can transfer channel ownership to the buyer.", show_alert=True)
        return False

    if deal_type == "accounts":
        text = (
            "<b>💼 Creating a Deal</b>\n\n"
            "<blockquote>"
            "<b>Specify what you are offering in this deal.</b>\n"
            "<b>Example: </b><code>Aged Telegram Accounts</code><b> 💭</b>"
            "</blockquote>"
        )
    else:
        text = (
            "<b>💼 Creating a Deal</b>\n\n"
            "<blockquote expandable>"
            "<b>Specify what you are offering in this deal.</b>\n"
            f"<b>Example:</b> <code>2 Scared Cats and a Cap 💭</code>"
            "</blockquote>"
        )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])

    msg = await callback.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.set_state(DealStates.waiting_for_offer)
    await state.update_data(deal_type=deal_type, deal_message_id=msg.message_id)
    await callback.answer()
    return True


@router.callback_query(lambda c: c.data == "deal_gifts")
async def deal_gifts(callback: types.CallbackQuery, state: FSMContext):
    """Создание сделки для подарков"""
    await check_wallet_and_proceed(callback, state, "gifts")


@router.callback_query(lambda c: c.data == "deal_channels")
async def deal_channels(callback: types.CallbackQuery, state: FSMContext):
    """Создание сделки для каналов"""
    await check_wallet_and_proceed(callback, state, "channels")


@router.callback_query(lambda c: c.data == "deal_accounts")
async def deal_accounts(callback: types.CallbackQuery, state: FSMContext):
    """Создание сделки для аккаунтов"""
    await check_wallet_and_proceed(callback, state, "accounts")


@router.callback_query(lambda c: c.data.startswith("buyer_terminate_"))
async def buyer_terminate_deal(callback: types.CallbackQuery, state: FSMContext):
    """Закрывает сделку для покупателя"""
    deal_id_str = callback.data.replace("buyer_terminate_", "")
    try:
        deal_id = int(deal_id_str)
        deal = get_deal(deal_id)
        if deal:
            update_deal_status(deal_id, "closed")
            
            seller_chat_id = get_seller_chat(deal_id)
            if seller_chat_id:
                buyer_username = callback.from_user.username or "unknown"
                buyer_id = callback.from_user.id
                
                text = (
                    f"<b>💼 Deal #{deal_id}</b>\n\n"
                    f"<b>👤 Buyer @{buyer_username} (<code>{buyer_id}</code>) has left the deal.</b>\n\n"
                    "<blockquote>"
                    "<b>🔎 You can now find a new buyer.</b>"
                    "</blockquote>"
                )
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
                ])
                
                try:
                    await bot.send_message(
                        chat_id=seller_chat_id,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления продавцу: {e}")
    except:
        pass
    
    try:
        await callback.message.delete()
    except:
        pass
    
    text = (
        f"<b>💼 Deal #{deal_id}</b>\n\n"
        "<blockquote>"
        "<b>✅ You left the deal.</b>"
        "</blockquote>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])
    
    await callback.message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.clear()


@router.my_chat_member()
async def on_bot_added_to_channel(update: types.ChatMemberUpdated):
    """Обработчик добавления бота в канал"""
    chat = update.chat
    new_member = update.new_chat_member
    
    if new_member.status == ChatMemberStatus.ADMINISTRATOR:
        try:
            user_id = update.from_user.id
            channel_id = chat.id
            channel_title = chat.title or "Unknown Channel"
            channel_link = f"https://t.me/{chat.username}" if chat.username else f"https://t.me/c/{str(channel_id)[4:]}"
            
            create_channel(channel_id, user_id, channel_title, channel_link, chat.username)
            
            text = (
                "<b>✅ You have added the bot to the channel!</b>\n\n"
                "<blockquote>"
                "<b>Now you can create a deal for selling this channel:</b>\n\n"
                f"<b>Name: </b><code>{channel_title}</code>\n"
                f"<b>Channel link: </b><code>{channel_link}</code>"
                "</blockquote>"
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛠 Create deal", callback_data=f"create_channel_deal_{user_id}")],
                [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
            ])
            
            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении бота в канал: {e}")


@router.callback_query(lambda c: c.data.startswith("create_channel_deal_"))
async def create_channel_deal(callback: types.CallbackQuery, state: FSMContext):
    """Начало создания сделки для канала"""
    user_id_str = callback.data.replace("create_channel_deal_", "")
    try:
        user_id = int(user_id_str)
        
        channel_info = get_channel(user_id)
        if channel_info:
            text = (
                "<b>💼 Creating a Deal</b>\n\n"
                "<blockquote>"
                "<b>Please choose the currency for this deal 👇</b>"
                "</blockquote>"
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 TON", callback_data=f"channel_currency_ton_{user_id}")],
                [InlineKeyboardButton(text="💲 USDT TON", callback_data=f"channel_currency_usdt_{user_id}")],
                [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
            ])
            
            msg = await callback.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
            await state.set_state(ChannelStates.waiting_for_currency_channel)
            await state.update_data(
                selected_channel_user_id=user_id,
                channel_info=channel_info,
                currency_message_id=msg.message_id
            )
            await callback.answer()
        else:
            await callback.answer("Канал не найден", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("channel_currency_ton_"))
async def select_channel_currency_ton(callback: types.CallbackQuery, state: FSMContext):
    """Выбор валюты TON для канала"""
    data = await state.get_data()
    currency_message_id = data.get("currency_message_id")

    if currency_message_id:
        try:
            await bot.delete_message(callback.message.chat.id, currency_message_id)
        except:
            pass

    try:
        await callback.message.delete()
    except:
        pass

    text = (
        "<b>💼 Creating a Deal</b>\n\n"
        "<blockquote>"
        "<b>💰 Deal Amount</b>\n"
        "<b>Please provide the amount in TON </b><code>(e.g. 123.4)</code><b> 👇</b>"
        "</blockquote>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])

    msg = await callback.message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.set_state(ChannelStates.waiting_for_amount_channel)
    await state.update_data(currency="TON", amount_message_id_channel=msg.message_id)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("channel_currency_usdt_"))
async def select_channel_currency_usdt(callback: types.CallbackQuery, state: FSMContext):
    """Выбор валюты USDT для канала"""
    data = await state.get_data()
    currency_message_id = data.get("currency_message_id")

    if currency_message_id:
        try:
            await bot.delete_message(callback.message.chat.id, currency_message_id)
        except:
            pass

    try:
        await callback.message.delete()
    except:
        pass

    text = (
        "<b>💼 Creating a Deal</b>\n\n"
        "<blockquote>"
        "<b>💰 Deal Amount</b>\n"
        "<b>Please provide the amount in USDT TON </b><code>(e.g. 123.4)</code><b> 👇</b>"
        "</blockquote>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])

    msg = await callback.message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.set_state(ChannelStates.waiting_for_amount_channel)
    await state.update_data(currency="USDT TON", amount_message_id_channel=msg.message_id)
    await callback.answer()


@router.message(ChannelStates.waiting_for_amount_channel)
async def process_channel_deal_amount(message: types.Message, state: FSMContext):
    """Обработка суммы для сделки канала"""
    amount_str = message.text.strip()
    data = await state.get_data()
    channel_info = data.get("channel_info", {})
    currency = data.get("currency", "TON")
    amount_message_id = data.get("amount_message_id_channel")
    user = message.from_user
    wallets = data.get("wallets", [])

    if not is_valid_amount(amount_str):
        if amount_message_id:
            try:
                await bot.delete_message(message.chat.id, amount_message_id)
            except:
                pass
        
        try:
            await message.delete()
        except:
            pass

        text = (
            "<b>❌ Invalid amount format!</b>\n\n"
            "<blockquote>"
            "<b>Only numbers are allowed.</b>\n"
            "<b>Example: </b><code>123.4</code><b> 👇</b>"
            "</blockquote>"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
        ])

        await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    amount = str(float(amount_str))
    channel_title = channel_info.get("channel_title", "Unknown Channel")

    # Создаём пользователя если его нет
    if not get_user(user.id):
        create_user(user.id, user.username or "unknown", get_utc3_date())
    
    # Генерируем ID сделки
    from time import time
    deal_id = int(time() * 1000) % 1000000
    
    deal_link = generate_deal_link(deal_id)
    memo = generate_memo()
    
    # Создаём сделку в БД
    create_deal(
        deal_id=deal_id,
        seller_id=user.id,
        seller_username=user.username or "unknown",
        deal_type="channels",
        offer=channel_title,
        amount=amount,
        currency=currency,
        memo=memo,
        link_token=deal_link.split("_", 2)[2],
        created_at=get_utc3_time()
    )
    
    set_seller_chat(deal_id, message.chat.id)

    if amount_message_id:
        try:
            await bot.delete_message(message.chat.id, amount_message_id)
        except:
            pass

    try:
        await message.delete()
    except:
        pass

    buyer_link = f"https://t.me/SecuMMabot?start={deal_link}"

    text = (
        f"<b>🎉 Your deal has been created!</b>\n"
        f"<b>Deal Type: 📢 Channels</b>\n\n"
        f"<b>Offer: </b><code>{channel_title}</code>\n"
        f"<b>Expected payment: </b><code>{amount} {currency}</code>\n\n"
        f"<b>⛓️ Buyer access link:</b>\n"
        f"<code>{buyer_link}</code>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Terminate Deal", callback_data=f"seller_terminate_{deal_id}")]
    ])

    await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.clear()
    await state.update_data(wallets=wallets)


@router.message(DealStates.waiting_for_offer)
async def process_deal_offer(message: types.Message, state: FSMContext):
    """Обработка описания предложения"""
    offer = message.text.strip()
    data = await state.get_data()
    deal_message_id = data.get("deal_message_id")

    await state.update_data(deal_offer=offer)

    if deal_message_id:
        try:
            await bot.delete_message(message.chat.id, deal_message_id)
        except:
            pass

    try:
        await message.delete()
    except:
        pass

    text = (
        "<b>💼 Creating a Deal</b>\n\n"
        "<blockquote>"
        "<b>Please choose the currency for this deal 👇</b>"
        "</blockquote>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 TON", callback_data="currency_ton")],
        [InlineKeyboardButton(text="💲 USDT TON", callback_data="currency_usdt")],
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])

    msg = await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.set_state(DealStates.waiting_for_currency)
    await state.update_data(currency_message_id=msg.message_id)


@router.callback_query(lambda c: c.data == "currency_ton")
async def select_currency_ton(callback: types.CallbackQuery, state: FSMContext):
    """Выбор TON валюты"""
    data = await state.get_data()
    currency_message_id = data.get("currency_message_id")

    if currency_message_id:
        try:
            await bot.delete_message(callback.message.chat.id, currency_message_id)
        except:
            pass

    try:
        await callback.message.delete()
    except:
        pass

    text = (
        "<b>💼 Creating a Deal</b>\n\n"
        "<blockquote>"
        "<b>💰 Deal Amount</b>\n"
        "<b>Please provide the amount in TON </b><code>(e.g. 123.4)</code><b> 👇</b>"
        "</blockquote>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])

    msg = await callback.message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.set_state(DealStates.waiting_for_amount)
    await state.update_data(currency="TON", amount_message_id=msg.message_id)
    await callback.answer()


@router.callback_query(lambda c: c.data == "currency_usdt")
async def select_currency_usdt(callback: types.CallbackQuery, state: FSMContext):
    """Выбор USDT валюты"""
    data = await state.get_data()
    currency_message_id = data.get("currency_message_id")

    if currency_message_id:
        try:
            await bot.delete_message(callback.message.chat.id, currency_message_id)
        except:
            pass

    try:
        await callback.message.delete()
    except:
        pass

    text = (
        "<b>💼 Creating a Deal</b>\n\n"
        "<blockquote>"
        "<b>💰 Deal Amount</b>\n"
        "<b>Please provide the amount in USDT TON </b><code>(e.g. 123.4)</code><b> 👇</b>"
        "</blockquote>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])

    msg = await callback.message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.set_state(DealStates.waiting_for_amount)
    await state.update_data(currency="USDT TON", amount_message_id=msg.message_id)
    await callback.answer()


@router.message(DealStates.waiting_for_amount)
async def process_deal_amount(message: types.Message, state: FSMContext):
    """Обработка суммы сделки"""
    amount_str = message.text.strip()
    data = await state.get_data()
    deal_offer = data.get("deal_offer", "unknown")
    deal_type = data.get("deal_type", "unknown")
    currency = data.get("currency", "TON")
    amount_message_id = data.get("amount_message_id")
    user = message.from_user
    wallets = data.get("wallets", [])

    if not is_valid_amount(amount_str):
        if amount_message_id:
            try:
                await bot.delete_message(message.chat.id, amount_message_id)
            except:
                pass
        
        try:
            await message.delete()
        except:
            pass

        text = (
            "<b>❌ Invalid amount format!</b>\n\n"
            "<blockquote>"
            "<b>Only numbers are allowed.</b>\n"
            "<b>Example: </b><code>123.4</code><b> 👇</b>"
            "</blockquote>"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
        ])

        await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    amount = str(float(amount_str))

    await state.update_data(deal_amount=amount)

    if amount_message_id:
        try:
            await bot.delete_message(message.chat.id, amount_message_id)
        except:
            pass

    try:
        await message.delete()
    except:
        pass

    # Создаём пользователя если его нет
    if not get_user(user.id):
        create_user(user.id, user.username or "unknown", get_utc3_date())
    
    # Генерируем ID сделки
    from time import time
    deal_id = int(time() * 1000) % 1000000
    
    deal_link = generate_deal_link(deal_id)
    memo = generate_memo()
    
    # Создаём сделку в БД
    create_deal(
        deal_id=deal_id,
        seller_id=user.id,
        seller_username=user.username or "unknown",
        deal_type=deal_type,
        offer=deal_offer,
        amount=amount,
        currency=currency,
        memo=memo,
        link_token=deal_link.split("_", 2)[2],
        created_at=get_utc3_time()
    )
    
    set_seller_chat(deal_id, message.chat.id)

    deal_type_emoji = get_deal_type_emoji(deal_type)

    buyer_link = f"https://t.me/SecuMMabot?start={deal_link}"

    text = (
        f"<b>🎉 Your deal has been created!</b>\n"
        f"<b>Deal Type: {deal_type_emoji} {deal_type.capitalize()}</b>\n\n"
        f"<b>Offer: </b><code>{deal_offer}</code>\n"
        f"<b>Expected payment: </b><code>{amount} {currency}</code>\n\n"
        f"<b>⛓️ Buyer access link:</b>\n"
        f"<code>{buyer_link}</code>"
    )

    # УСЛОВИЕ: Показываем кнопку для типов Gifts и Channels, но НЕ для Accounts
    if deal_type in ["gifts", "channels"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔴 Terminate Deal", callback_data=f"seller_terminate_{deal_id}")]
        ])
        await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        # Для Accounts - БЕЗ КНОПОК
        await message.answer(text=text, parse_mode=ParseMode.HTML)
    
    await state.clear()
    await state.update_data(wallets=wallets)


@router.callback_query(lambda c: c.data.startswith("seller_terminate_"))
async def seller_terminate_deal(callback: types.CallbackQuery, state: FSMContext):
    """Закрывает сделку для продавца"""
    from handlers.commands import show_main_menu
    
    deal_id_str = callback.data.replace("seller_terminate_", "")
    try:
        deal_id = int(deal_id_str)
        deal = get_deal(deal_id)
        if deal:
            update_deal_status(deal_id, "closed")
    except:
        pass
    
    await callback.answer("🔴 Deal closed", show_alert=True)
    
    try:
        await callback.message.delete()
    except:
        pass
    
    text = (
        f"<b>💼 Deal #{deal_id}</b>\n\n"
        "<blockquote>"
        "<b>✅ You closed the deal.</b>"
        "</blockquote>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])
    
    await callback.message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.clear()