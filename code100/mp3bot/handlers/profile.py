"""
Обработчики для профиля и статистики пользователя
"""
from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from database import (
    get_user, create_user, get_utc3_date,
    calculate_total_volume, calculate_monthly_volume,
    calculate_avg_deal_value, calculate_success_rate, calculate_rating,
    get_user_ratings, get_user_avg_rating
)

router = Router()


@router.callback_query(lambda c: c.data == "profile")
async def show_trader_profile(callback: types.CallbackQuery):
    """Показывает профиль трейдера с статистикой"""
    user_id = callback.from_user.id
    username = callback.from_user.username or "unknown"
    
    # Создаём/получаем пользователя
    user = get_user(user_id)
    if not user:
        create_user(user_id, username, get_utc3_date())
        user = get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка загрузки профиля", show_alert=True)
        return
    
    # Расчёты
    total_volume = calculate_total_volume(user_id)
    monthly_volume = calculate_monthly_volume(user_id)
    avg_deal = calculate_avg_deal_value(user_id)
    success_rate = calculate_success_rate(user_id)
    rating = calculate_rating(user_id)
    completed = user["completed_deals"]
    
    rating_text = f"{rating} / 5.0" if completed > 0 else "No rating yet"
    success_rate_text = f"{success_rate}%" if completed > 0 else "0%"
    
    text = (
        "<b>👤 Trader Profile</b>\n\n"
        "<b>🟢 @" + username + "</b>\n"
        f"<b>📱 Telegram ID: <code>{user_id}</code></b>\n"
        f"<b>🕐 Joined: {user['joined_date']}</b>\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "<b>🏆 Your Reputation</b>\n\n"
        f"<b>⭐️ Rating — {rating_text}</b>\n"
        f"<b>🤝 Completed — {completed} deals</b>\n"
        f"<b>📊 Success rate — {success_rate_text}</b>\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "<b>💰 Trading Volume</b>\n\n"
        f"<b>📈 Total: {total_volume} TON</b>\n"
        f"<b>📅 This month: {monthly_volume} TON</b>\n"
        f"<b>🔄 Avg deal: {avg_deal} TON</b>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ To Menu", callback_data="to_main_menu")]
    ])
    
    await callback.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()