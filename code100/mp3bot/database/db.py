"""
Работа с SQLite базой данных
"""
import sqlite3
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

DB_PATH = "data/bot.db"


def init_db():
    """Инициализирует БД и создаёт таблицы"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            joined_date TEXT NOT NULL,
            completed_deals INTEGER DEFAULT 0,
            total_deals INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица сделок
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            deal_id INTEGER PRIMARY KEY,
            seller_id INTEGER NOT NULL,
            seller_username TEXT NOT NULL,
            deal_type TEXT NOT NULL,
            offer TEXT NOT NULL,
            amount TEXT NOT NULL,
            currency TEXT DEFAULT 'TON',
            memo TEXT NOT NULL UNIQUE,
            link_token TEXT NOT NULL,
            status TEXT DEFAULT 'waiting_for_payment',
            created_at TEXT NOT NULL,
            completed_at TEXT,
            buyer_id INTEGER,
            buyer_username TEXT,
            tx_hash TEXT,
            payment_confirmed_at TEXT,
            FOREIGN KEY (seller_id) REFERENCES users(user_id)
        )
    """)
    
    # Таблица истории сделок пользователя
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            deal_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
        )
    """)
    
    # Таблица кошельков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            wallet_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            address TEXT NOT NULL,
            short TEXT NOT NULL,
            name TEXT,
            date_added TEXT NOT NULL,
            is_primary BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            UNIQUE(user_id, address)
        )
    """)
    
    # Таблица каналов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            channel_title TEXT NOT NULL,
            channel_link TEXT NOT NULL,
            channel_username TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    # Таблица seller_chats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seller_chats (
            deal_id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
        )
    """)

    # Таблица оценок
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id INTEGER NOT NULL,
            from_user_id INTEGER NOT NULL,
            to_user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals(deal_id),
            FOREIGN KEY (from_user_id) REFERENCES users(user_id),
            FOREIGN KEY (to_user_id) REFERENCES users(user_id),
            UNIQUE(deal_id, from_user_id)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("✅ БД инициализирована")


# ============ ПОЛЬЗОВАТЕЛИ ============

def create_user(user_id: int, username: str, joined_date: str):
    """Создаёт нового пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO users (user_id, username, joined_date)
            VALUES (?, ?, ?)
        """, (user_id, username, joined_date))
        conn.commit()
        logger.info(f"✅ Пользователь {user_id} создан")
    except sqlite3.IntegrityError:
        pass  # Уже существует
    finally:
        conn.close()


def get_user(user_id: int) -> Optional[Dict]:
    """Получает пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "user_id": row[0],
            "username": row[1],
            "joined_date": row[2],
            "completed_deals": row[3],
            "total_deals": row[4],
        }
    return None


def update_user_deals(user_id: int, completed: int, total: int):
    """Обновляет статистику пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE users 
        SET completed_deals = ?, total_deals = ?
        WHERE user_id = ?
    """, (completed, total, user_id))
    
    conn.commit()
    conn.close()


# ============ СДЕЛКИ ============

def create_deal(deal_id: int, seller_id: int, seller_username: str, deal_type: str,
                offer: str, amount: str, currency: str, memo: str, link_token: str,
                created_at: str) -> bool:
    """Создаёт новую сделку"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO deals 
            (deal_id, seller_id, seller_username, deal_type, offer, amount, currency, 
             memo, link_token, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (deal_id, seller_id, seller_username, deal_type, offer, amount, currency,
              memo, link_token, "waiting_for_payment", created_at))
        
        # Добавляем в историю пользователя
        cursor.execute("""
            INSERT INTO user_deals (user_id, deal_id)
            VALUES (?, ?)
        """, (seller_id, deal_id))
        
        conn.commit()
        logger.info(f"✅ Сделка #{deal_id} создана")
        return True
    except sqlite3.IntegrityError as e:
        logger.error(f"Ошибка при создании сделки: {e}")
        return False
    finally:
        conn.close()


def get_deal(deal_id: int) -> Optional[Dict]:
    """Получает сделку по ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "seller_id": row[1],
            "seller_username": row[2],
            "deal_type": row[3],
            "offer": row[4],
            "amount": row[5],
            "currency": row[6],
            "memo": row[7],
            "link_token": row[8],
            "status": row[9],
            "created_at": row[10],
            "completed_at": row[11],
            "buyer_id": row[12],
            "buyer_username": row[13],
            "tx_hash": row[14],
            "payment_confirmed_at": row[15],
        }
    return None


def get_deal_by_memo(memo: str) -> Optional[Dict]:
    """Получает сделку по memo"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM deals WHERE memo = ?", (memo,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "seller_id": row[1],
            "seller_username": row[2],
            "deal_type": row[3],
            "offer": row[4],
            "amount": row[5],
            "currency": row[6],
            "memo": row[7],
            "link_token": row[8],
            "status": row[9],
            "created_at": row[10],
            "completed_at": row[11],
            "buyer_id": row[12],
            "buyer_username": row[13],
            "tx_hash": row[14],
            "payment_confirmed_at": row[15],
        }
    return None


def get_waiting_deals() -> List[Dict]:
    """Получает все сделки в статусе waiting_for_payment"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM deals WHERE status = 'waiting_for_payment'")
    rows = cursor.fetchall()
    conn.close()
    
    deals = []
    for row in rows:
        deals.append({
            "id": row[0],
            "seller_id": row[1],
            "seller_username": row[2],
            "deal_type": row[3],
            "offer": row[4],
            "amount": row[5],
            "currency": row[6],
            "memo": row[7],
            "link_token": row[8],
            "status": row[9],
            "created_at": row[10],
            "completed_at": row[11],
            "buyer_id": row[12],
            "buyer_username": row[13],
            "tx_hash": row[14],
            "payment_confirmed_at": row[15],
        })
    
    return deals


def update_deal_status(deal_id: int, status: str, tx_hash: str = None, completed_at: str = None):
    """Обновляет статус сделки"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE deals 
        SET status = ?, tx_hash = ?, payment_confirmed_at = ?
        WHERE deal_id = ?
    """, (status, tx_hash, completed_at, deal_id))
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Сделка #{deal_id} обновлена: {status}")


def update_deal_buyer(deal_id: int, buyer_id: int, buyer_username: str):
    """Обновляет информацию о покупателе"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE deals 
        SET buyer_id = ?, buyer_username = ?
        WHERE deal_id = ?
    """, (buyer_id, buyer_username, deal_id))
    
    conn.commit()
    conn.close()


def get_user_deals(user_id: int) -> List[int]:
    """Получает историю сделок пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT deal_id FROM user_deals WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [row[0] for row in rows]


# ============ КОШЕЛЬКИ ============

def create_wallet(user_id: int, address: str, short: str, name: Optional[str], date_added: str):
    """Создаёт кошелёк"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO wallets (user_id, address, short, name, date_added, is_primary)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, address, short, name, date_added, 0))
        
        conn.commit()
        logger.info(f"✅ Кошелёк {short} создан для пользователя {user_id}")
        return True
    except sqlite3.IntegrityError:
        logger.error(f"Кошелёк {address} уже существует")
        return False
    finally:
        conn.close()


def get_wallets(user_id: int) -> List[Dict]:
    """Получает все кошельки пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT wallet_id, address, short, name, date_added, is_primary
        FROM wallets
        WHERE user_id = ?
        ORDER BY is_primary DESC
    """, (user_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    wallets = []
    for row in rows:
        wallets.append({
            "id": row[0],
            "address": row[1],
            "short": row[2],
            "name": row[3],
            "date_added": row[4],
            "is_primary": bool(row[5]),
        })
    
    return wallets


def delete_wallet(wallet_id: int):
    """Удаляет кошелёк"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM wallets WHERE wallet_id = ?", (wallet_id,))
    conn.commit()
    conn.close()
    logger.info(f"✅ Кошелёк #{wallet_id} удалён")


def set_primary_wallet(user_id: int, wallet_id: int):
    """Устанавливает кошелёк как основной"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Сбрасываем все кошельки
    cursor.execute("UPDATE wallets SET is_primary = 0 WHERE user_id = ?", (user_id,))
    
    # Устанавливаем выбранный
    cursor.execute("UPDATE wallets SET is_primary = 1 WHERE wallet_id = ?", (wallet_id,))
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Кошелёк #{wallet_id} установлен как основной")


# ============ КАНАЛЫ ============

def create_channel(channel_id: int, user_id: int, channel_title: str, 
                   channel_link: str, channel_username: Optional[str]):
    """Создаёт запись о канале"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO channels (channel_id, user_id, channel_title, channel_link, channel_username)
            VALUES (?, ?, ?, ?, ?)
        """, (channel_id, user_id, channel_title, channel_link, channel_username))
        
        conn.commit()
        logger.info(f"✅ Канал {channel_title} добавлен для пользователя {user_id}")
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_channel(user_id: int) -> Optional[Dict]:
    """Получает канал пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT channel_id, channel_title, channel_link, channel_username
        FROM channels
        WHERE user_id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "channel_id": row[0],
            "channel_title": row[1],
            "channel_link": row[2],
            "channel_username": row[3],
        }
    return None


# ============ SELLER CHATS ============

def set_seller_chat(deal_id: int, chat_id: int):
    """Сохраняет chat_id продавца для сделки"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO seller_chats (deal_id, chat_id)
            VALUES (?, ?)
        """, (deal_id, chat_id))
        
        conn.commit()
    finally:
        conn.close()


def get_seller_chat(deal_id: int) -> Optional[int]:
    """Получает chat_id продавца для сделки"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT chat_id FROM seller_chats WHERE deal_id = ?", (deal_id,))
    row = cursor.fetchone()
    conn.close()
    
    return row[0] if row else None


"""
Добавить в конец существующего файла database/db.py
"""

# ============ ПЛАТЕЖИ И ТРАНЗАКЦИИ ============

def update_deal_payment(deal_id: int, tx_hash: str, payment_confirmed_at: str,
                       buyer_wallet: str, seller_payout_amount: float):
    """Обновляет информацию о платеже сделки"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE deals 
        SET status = 'payment_confirmed',
            tx_hash = ?,
            payment_confirmed_at = ?,
            buyer_wallet = ?,
            seller_payout_amount = ?
        WHERE deal_id = ?
    """, (tx_hash, payment_confirmed_at, buyer_wallet, seller_payout_amount, deal_id))
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Пла��ёж для сделки #{deal_id} обновлен")


def update_deal_delivery(deal_id: int, delivery_confirmed_at: str):
    """Обновляет статус доставки"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE deals 
        SET status = 'completed',
            delivery_confirmed_at = ?
        WHERE deal_id = ?
    """, (delivery_confirmed_at, deal_id))
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Доставка для сделки #{deal_id} подтверждена")


def update_deal_timeout(deal_id: int, refund_amount: float, refund_tx_hash: str = None):
    """Обновляет статус при timeout (возврат денег)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE deals 
        SET status = 'closed_timeout_refunded',
            refund_tx_hash = ?
        WHERE deal_id = ?
    """, (refund_tx_hash, deal_id))
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Timeout для сделки #{deal_id}: возврат {refund_amount} TON")


def get_all_waiting_payment_deals() -> List[Dict]:
    """Получает все сделки в ожидании платежа"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM deals WHERE status = 'waiting_for_payment'")
    rows = cursor.fetchall()
    conn.close()
    
    deals = []
    for row in rows:
        deals.append({
            "id": row[0],
            "seller_id": row[1],
            "seller_username": row[2],
            "deal_type": row[3],
            "offer": row[4],
            "amount": row[5],
            "currency": row[6],
            "memo": row[7],
            "created_at": row[10],
        })
    
    return deals


def get_all_confirmed_payment_deals() -> List[Dict]:
    """Получает все сделки с подтвержденным платежом (ждут доставки)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM deals WHERE status = 'payment_confirmed'")
    rows = cursor.fetchall()
    conn.close()
    
    deals = []
    for row in rows:
        deals.append({
            "id": row[0],
            "seller_id": row[1],
            "seller_username": row[2],
            "buyer_id": row[12],
            "buyer_username": row[13],
            "amount": row[5],
            "currency": row[6],
            "payment_confirmed_at": row[15],
        })
    
    return deals


# ============ ОЦЕНКИ ============

def create_rating(deal_id: int, from_user_id: int, to_user_id: int, 
                  rating: int, comment: str = ""):
    """Создаёт оценку между пользователями"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO ratings (deal_id, from_user_id, to_user_id, rating, comment, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (deal_id, from_user_id, to_user_id, rating, comment))
        
        conn.commit()
        logger.info(f"✅ Оценка создана: {from_user_id} → {to_user_id}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Оценка уже существует для сделки {deal_id}")
        return False
    finally:
        conn.close()


def get_user_ratings(user_id: int) -> List[Dict]:
    """Получает все оценки пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT rating, comment, from_user_id
        FROM ratings
        WHERE to_user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    ratings = []
    for row in rows:
        ratings.append({
            "rating": row[0],
            "comment": row[1],
            "from_user_id": row[2],
        })
    
    return ratings


def get_user_avg_rating(user_id: int) -> float:
    """Получает среднюю оценку пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT AVG(rating)
        FROM ratings
        WHERE to_user_id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0]:
        return round(row[0], 1)
    return 0.0