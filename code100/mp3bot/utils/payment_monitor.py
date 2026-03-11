"""
Фоновый мониторинг платежей и таймаутов
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from database import (
    get_all_waiting_payment_deals, get_all_confirmed_payment_deals,
    get_deal, update_deal_payment, update_deal_timeout, 
    get_seller_chat, get_utc3_time, update_deal_status
)
from utils.ton_api import ton_api
from config import config
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
bot: Bot = None


def set_bot(b: Bot):
    """Устанавливает экземпляр бота"""
    global bot
    bot = b


def get_utc3_now() -> datetime:
    """Получает текущее время в UTC+3"""
    utc3_tz = timezone(timedelta(hours=3))
    return datetime.now(utc3_tz)


async def monitor_payments():
    """Мониторит входящие пл��тежи"""
    logger.info("🔍 Запущен мониторинг платежей...")
    
    while True:
        try:
            deals = get_all_waiting_payment_deals()
            
            for deal in deals:
                deal_id = deal["id"]
                memo = deal["memo"]
                expected_amount = float(deal["amount"])
                seller_id = deal["seller_id"]
                created_at_str = deal["created_at"]
                
                # Проверяем таймаут (15 минут)
                try:
                    created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M")
                    created_at_utc = created_at.replace(tzinfo=timezone(timedelta(hours=3)))
                    now = get_utc3_now()
                    
                    if now - created_at_utc > timedelta(seconds=config.PAYMENT_TIMEOUT):
                        logger.info(f"⏰ Timeout платежа для сделки #{deal_id}")
                        update_deal_status(deal_id, "closed_no_payment")
                        
                        # Уведомляем продавца
                        seller_chat_id = get_seller_chat(deal_id)
                        if seller_chat_id and bot:
                            text = (
                                "<b>⏰ Time Expired</b>\n\n"
                                "<b>No payment received in 15 minutes</b>\n\n"
                                "<blockquote>"
                                "<b>The deal has been closed</b>"
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
                                logger.error(f"Ошибка при уведомлении продавца: {e}")
                        
                        continue
                except Exception as e:
                    logger.error(f"Ошибка при проверке таймаута: {e}")
                
                # Проверяем платёж
                payment = await ton_api.find_payment(
                    wallet_address=config.MASTER_WALLET,
                    expected_memo=memo,
                    expected_amount=expected_amount
                )
                
                if payment:
                    logger.info(f"✅ Платёж найден для сделки #{deal_id}")
                    
                    tx_hash = payment["tx_hash"]
                    buyer_wallet = payment["from"]
                    commission = expected_amount * 0.01
                    seller_payout = expected_amount - commission
                    
                    # Обновляем БД
                    update_deal_payment(
                        deal_id=deal_id,
                        tx_hash=tx_hash,
                        payment_confirmed_at=get_utc3_time(),
                        buyer_wallet=buyer_wallet,
                        seller_payout_amount=seller_payout
                    )
                    
                    # Уведомляем обе стороны
                    seller_chat_id = get_seller_chat(deal_id)
                    
                    if seller_chat_id and bot:
                        text = (
                            "<b>💰 Payment Received</b>\n\n"
                            f"<b>Amount: {expected_amount} {deal['currency']}</b>\n\n"
                            "<blockquote>"
                            "<b>Send the item to the buyer now</b>\n"
                            "<b>You have 15 minutes to confirm</b>"
                            "</blockquote>"
                        )
                        
                        kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="✅ Item Sent", callback_data=f"seller_delivered_{deal_id}")],
                            [InlineKeyboardButton(text="❌ Cancel Deal", callback_data=f"seller_cancel_{deal_id}")]
                        ])
                        
                        try:
                            await bot.send_message(
                                chat_id=seller_chat_id,
                                text=text,
                                parse_mode=ParseMode.HTML,
                                reply_markup=kb
                            )
                        except Exception as e:
                            logger.error(f"Ошибка при уведомлении продавца: {e}")
                    
                    # TODO: Уведомить покупателя
        
        except Exception as e:
            logger.error(f"Ошибка в monitor_payments: {e}")
        
        # Проверяем каждые 10 секунд
        await asyncio.sleep(10)


async def monitor_delivery_timeouts():
    """Мониторит таймауты доставки"""
    logger.info("🔍 Запущен мониторинг таймаутов доставки...")
    
    while True:
        try:
            deals = get_all_confirmed_payment_deals()
            
            for deal in deals:
                deal_id = deal["id"]
                payment_confirmed_at_str = deal["payment_confirmed_at"]
                seller_payout_amount = deal.get("seller_payout_amount", float(deal["amount"]) * 0.99)
                buyer_id = deal["buyer_id"]
                
                # Проверяем таймаут (15 ми��ут)
                try:
                    confirmed_at = datetime.strptime(payment_confirmed_at_str, "%Y-%m-%d %H:%M")
                    confirmed_at_utc = confirmed_at.replace(tzinfo=timezone(timedelta(hours=3)))
                    now = get_utc3_now()
                    
                    if now - confirmed_at_utc > timedelta(seconds=config.DELIVERY_TIMEOUT):
                        logger.info(f"⏰ Timeout доставки для сделки #{deal_id}, возврат покупателю")
                        
                        # Обновляем статус
                        update_deal_timeout(deal_id, seller_payout_amount)
                        
                        # TODO: Отправляем деньги обратно покупателю
                        # TODO: Уведомляем обе стороны
                
                except Exception as e:
                    logger.error(f"Ошибка при проверке таймаута доставки: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка в monitor_delivery_timeouts: {e}")
        
        # Проверяем каждые 15 секунд
        await asyncio.sleep(15)