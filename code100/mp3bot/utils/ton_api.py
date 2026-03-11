"""
Интеграция с TON API для мониторинга платежей
"""
import aiohttp
import logging
from typing import Optional, List, Dict
from config import config

logger = logging.getLogger(__name__)


class TONApi:
    """Класс для работы с TON API"""
    
    def __init__(self):
        self.api_url = config.TON_API_URL
        self.api_key = config.TON_API_KEY
        self.master_wallet = config.MASTER_WALLET
    
    async def get_wallet_transactions(self, wallet_address: str, limit: int = 10) -> Optional[Dict]:
        """Получает последние транзакции кошелька"""
        url = f"{self.api_url}/blockchain/accounts/{wallet_address}/transactions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data
                    else:
                        logger.error(f"TON API error: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Ошибка при запросе к TON API: {e}")
            return None
    
    async def find_payment(self, wallet_address: str, expected_memo: str, 
                          expected_amount: float) -> Optional[Dict]:
        """Ищет платёж по memo и сумме"""
        txs_data = await self.get_wallet_transactions(wallet_address, limit=20)
        
        if not txs_data or "transactions" not in txs_data:
            return None
        
        for tx in txs_data["transactions"]:
            try:
                # Проверяем входящие транзакции
                if "in_msg" not in tx:
                    continue
                
                in_msg = tx["in_msg"]
                
                # Получаем memo из сообщения
                message_text = in_msg.get("message", "")
                memo = message_text if message_text else None
                
                # Получаем сумму
                amount_str = in_msg.get("value", "0")
                try:
                    amount_nanoton = int(amount_str)
                    amount_ton = amount_nanoton / 1e9
                except:
                    amount_ton = 0
                
                # Проверяем совпадение
                if memo and memo.strip() == expected_memo.strip():
                    if amount_ton >= expected_amount:
                        return {
                            "tx_hash": tx.get("hash", ""),
                            "amount": amount_ton,
                            "memo": memo,
                            "from": in_msg.get("source", ""),
                            "utime": tx.get("utime", 0),
                        }
            except Exception as e:
                logger.error(f"Ошибка при обработке транзакции: {e}")
                continue
        
        return None
    
    async def send_transaction(self, to_address: str, amount: float, memo: str = "") -> Optional[str]:
        """
        Отправляет транзакцию (требует приватный ключ)
        ВНИМАНИЕ: В production используй более безопасный способ!
        """
        logger.warning("⚠️ send_transaction требует реальной реализации с приватным ключом")
        return None


# Глобальный экземпляр
ton_api = TONApi()