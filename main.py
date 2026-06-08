import os
import asyncio
import logging

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv, find_dotenv

# .env должен быть загружен до импорта bot.handlers — он читает WEB_BASE_URL
# на уровне модуля (для проверки конфигурации сразу при старте).
load_dotenv(find_dotenv())

from bot.handlers import router
from bot.mail_loop import mail_loop

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("errors.log"),
        logging.StreamHandler()
    ]
)

bot = Bot(token=os.getenv("TOKEN"))
dp = Dispatcher()
dp.include_router(router)

async def main():
    asyncio.create_task(mail_loop(bot))
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
