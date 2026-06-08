import logging
import os

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router()

WEB_BASE_URL = os.getenv("WEB_BASE_URL", "").rstrip("/")

if not WEB_BASE_URL:
    logging.error(
        "WEB_BASE_URL не задан в .env — кнопка \"Подключить почту\" будет вести "
        "на относительный путь, и Telegram отклонит такое сообщение "
        "(\"URL host is empty\"). Укажите полный https-адрес формы (домен или ngrok)."
    )

@router.message(CommandStart())
async def cmd_start(message: Message):
    connect_url = f"{WEB_BASE_URL}/connect?telegram_id={message.from_user.id}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Подключить почту", url=connect_url)]
    ])

    await message.answer(
        "👋 Привет! Я пересылаю новые письма с твоей почты прямо в Telegram.\n\n"
        "Нажми на кнопку ниже — откроется защищённая страница, где нужно "
        "указать данные почтового ящика (IMAP-сервер, адрес и пароль). "
        "После проверки я начну присылать сюда новые письма.",
        reply_markup=keyboard
    )

# Сообщение об успешном подключении ("✅ Почта ... подключена!") отправляется
# не отсюда, а из web/routes.py сразу после того, как веб-форма проверила и
# сохранила данные — у бота и веб-сервиса разные процессы, и у веб-сервиса нет
# экземпляра aiogram.Bot (см. _notify_connected в web/routes.py).
