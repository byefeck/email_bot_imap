import logging
import os

import aiohttp
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from auth.credentials import PasswordCredentials
from database.crud import upsert_user
from imap.service import test_login
from web.presets import IMAP_PRESETS

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

TOKEN = os.getenv("TOKEN")

def _render_form(request, telegram_id, error=None, prefill_email="", prefill_host="", prefill_port=993):
    return templates.TemplateResponse(
        request,
        "connect.html",
        {
            "telegram_id": telegram_id,
            "presets": IMAP_PRESETS,
            "error": error,
            "prefill_email": prefill_email,
            "prefill_host": prefill_host,
            "prefill_port": prefill_port,
        },
    )

@router.get("/connect", response_class=HTMLResponse)
async def connect_form(request: Request, telegram_id: int):
    return _render_form(request, telegram_id)

@router.post("/connect", response_class=HTMLResponse)
async def connect_submit(
    request: Request,
    telegram_id: int = Form(...),
    imap_host: str = Form(...),
    imap_port: int = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    email = email.strip()
    imap_host = imap_host.strip()
    credentials = PasswordCredentials(email, password)

    try:
        await test_login(imap_host, imap_port, credentials)
    except Exception as e:
        logging.error(f"Тестовый IMAP-логин не удался для {email} ({imap_host}:{imap_port}): {e}")
        return _render_form(
            request,
            telegram_id,
            error=(
                "Не удалось подключиться с этими данными. Проверьте сервер, порт, "
                "адрес почты и пароль (для Gmail и Mail.ru нужен пароль приложения, "
                "а не обычный пароль от аккаунта)."
            ),
            prefill_email=email,
            prefill_host=imap_host,
            prefill_port=imap_port,
        )

    await upsert_user(
        telegram_id=telegram_id,
        imap_host=imap_host,
        imap_port=imap_port,
        email=email,
        password=password,
    )

    await _notify_connected(telegram_id, email)

    return templates.TemplateResponse(request, "connected.html", {"email": email})

async def _notify_connected(telegram_id, email):
    """Шлём уведомление напрямую через Bot API (без импорта aiogram.Bot),
    чтобы веб-сервис оставался независимым процессом от бота."""
    if not TOKEN:
        return

    text = (
        f"✅ Почта {email} подключена!\n"
        f"Теперь я буду присылать сюда новые письма."
    )
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"chat_id": telegram_id, "text": text}) as resp:
                if resp.status != 200:
                    logging.error(f"Telegram API ответил {resp.status} для {telegram_id}: {await resp.text()}")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление {telegram_id}: {e}")
