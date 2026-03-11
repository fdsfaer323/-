"""
Вспомогательные функции (без БД)
"""
import random
import string
from datetime import datetime, timedelta, timezone
from database.db import get_user_deals, get_deal, get_wallets


def generate_deal_link(deal_id: int) -> str:
    """Генерирует уникальную ссылку на сделку"""
    random_token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    return f"deal_{deal_id}_{random_token}"


def generate_memo() -> str:
    """Генерирует memo для платежа в TON"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))


def get_utc3_time() -> str:
    """Получает текущее время в UTC+3"""
    utc3_tz = timezone(timedelta(hours=3))
    now = datetime.now(utc3_tz)
    return now.strftime("%Y-%m-%d %H:%M")


def get_utc3_date() -> str:
    """Получает текущую дату в UTC+3"""
    utc3_tz = timezone(timedelta(hours=3))
    now = datetime.now(utc3_tz)
    return now.strftime("%b %d, %Y")


def calculate_total_volume(user_id: int) -> float:
    """Расчёт общего объёма сделок пользователя"""
    deals_ids = get_user_deals(user_id)
    total = 0.0
    
    for deal_id in deals_ids:
        deal = get_deal(deal_id)
        if deal and deal["status"] == "payment_confirmed":
            try:
                amount = float(deal["amount"])
                total += amount
            except:
                pass
    
    return round(total, 2)


def calculate_monthly_volume(user_id: int) -> float:
    """Расчёт объёма сделок за текущий месяц"""
    deals_ids = get_user_deals(user_id)
    total = 0.0
    
    now = datetime.now(timezone.utc)
    current_month = now.month
    current_year = now.year
    
    for deal_id in deals_ids:
        deal = get_deal(deal_id)
        if deal:
            try:
                created_str = deal["created_at"]
                created = datetime.strptime(created_str, "%Y-%m-%d %H:%M")
                
                if (deal["status"] == "payment_confirmed" and 
                    created.month == current_month and 
                    created.year == current_year):
                    amount = float(deal["amount"])
                    total += amount
            except:
                pass
    
    return round(total, 2)


def calculate_avg_deal_value(user_id: int) -> float:
    """Расчёт средней стоимости сделки"""
    user = get_user(user_id)
    if not user:
        return 0.0
    
    completed = user["completed_deals"]
    if completed == 0:
        return 0.0
    
    total_volume = calculate_total_volume(user_id)
    avg = total_volume / completed
    
    return round(avg, 2)


def calculate_success_rate(user_id: int) -> float:
    """Расчёт процента успешных сделок"""
    user = get_user(user_id)
    if not user:
        return 0.0
    
    total = user["total_deals"]
    if total == 0:
        return 0.0
    
    completed = user["completed_deals"]
    success_rate = (completed / total) * 100
    
    return round(success_rate, 1)


def calculate_rating(user_id: int) -> float:
    """Расчёт рейтинга пользователя (0-5)"""
    success_rate = calculate_success_rate(user_id)
    rating = (success_rate / 100) * 5.0
    
    return round(rating, 1)