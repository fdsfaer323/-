"""
Конфигурация приложения
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    
    # TON API
    TON_API_KEY = os.getenv("TON_API_KEY", "")
    TON_API_URL = os.getenv("TON_API_URL", "https://tonapi.io/v2")
    MASTER_WALLET = os.getenv("MASTER_WALLET", "")
    
    # Таймауты
    PAYMENT_TIMEOUT = int(os.getenv("PAYMENT_TIMEOUT", "900"))  # 15 минут
    DELIVERY_TIMEOUT = int(os.getenv("DELIVERY_TIMEOUT", "900"))  # 15 минут
    
    def validate(self):
        """Проверяет обязательные переменные"""
        required = ["BOT_TOKEN", "TON_API_KEY", "MASTER_WALLET"]
        missing = [var for var in required if not getattr(self, var)]
        
        if missing:
            raise ValueError(f"❌ Missing required env vars: {', '.join(missing)}")
        
        print("✅ Конфигурация загружена успешно")


config = Config()