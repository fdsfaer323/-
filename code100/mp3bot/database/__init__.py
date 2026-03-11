"""База данных проекта"""
from database.db import (
    init_db,
    create_user, get_user, update_user_deals,
    create_deal, get_deal, get_deal_by_memo, get_waiting_deals, 
    update_deal_status, update_deal_buyer, get_user_deals,
    create_wallet, get_wallets, delete_wallet, set_primary_wallet,
    create_channel, get_channel,
    set_seller_chat, get_seller_chat,
    # НОВЫЕ функции для платежей
    update_deal_payment, update_deal_delivery, update_deal_timeout,
    get_all_waiting_payment_deals, get_all_confirmed_payment_deals,
    # НОВЫЕ функции для оценок
    create_rating, get_user_ratings, get_user_avg_rating,
)
from database.models import (
    generate_deal_link, generate_memo,
    get_utc3_time, get_utc3_date,
    calculate_total_volume, calculate_monthly_volume,
    calculate_avg_deal_value, calculate_success_rate, calculate_rating,
)

__all__ = [
    # db.py - базовые функции
    'init_db',
    'create_user', 'get_user', 'update_user_deals',
    'create_deal', 'get_deal', 'get_deal_by_memo', 'get_waiting_deals',
    'update_deal_status', 'update_deal_buyer', 'get_user_deals',
    'create_wallet', 'get_wallets', 'delete_wallet', 'set_primary_wallet',
    'create_channel', 'get_channel',
    'set_seller_chat', 'get_seller_chat',
    # db.py - платежи
    'update_deal_payment', 'update_deal_delivery', 'update_deal_timeout',
    'get_all_waiting_payment_deals', 'get_all_confirmed_payment_deals',
    # db.py - оценки
    'create_rating', 'get_user_ratings', 'get_user_avg_rating',
    # models.py
    'generate_deal_link', 'generate_memo',
    'get_utc3_time', 'get_utc3_date',
    'calculate_total_volume', 'calculate_monthly_volume',
    'calculate_avg_deal_value', 'calculate_success_rate', 'calculate_rating',
]