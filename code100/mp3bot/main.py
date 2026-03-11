"""
Основной файл бота - точка входа
"""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import config

# Создаём папку data если её нет
os.makedirs("data", exist_ok=True)

# Инициализируем БД
from database import init_db
init_db()

from handlers import commands, wallet, profile, settings, deals

# ============ ЛОГИРОВАНИЕ ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Валидируем конфигурацию
config.validate()

# ============ ИНИЦИАЛИЗАЦИЯ БОТА ============
bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

logger.info("🚀 Бот инициализирован")

# ============ РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ============
# Передаём экземпляр бота в модуль deals
deals.set_bot(bot)

# Регистрируем все роутеры (ПОРЯДОК ВАЖЕН!)
# Специфичные обработчики ПЕРВЫМИ
dp.include_router(deals.router)
dp.include_router(wallet.router)
dp.include_router(profile.router)
dp.include_router(settings.router)
# Общие обработчики В КОНЦЕ
dp.include_router(commands.router)


# ============ ТОЧКА ВХОДА ============
async def main():
    logger.info("✅ Бот запущен и начал polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())