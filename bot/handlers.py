import logging
import os

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from database.crud import (
    clear_destination,
    clear_mailbox,
    get_user_by_telegram_id,
    set_destination,
)

router = Router()

WEB_BASE_URL = os.getenv("WEB_BASE_URL", "").rstrip("/")

if not WEB_BASE_URL:
    logging.error(
        "WEB_BASE_URL не задан в .env — кнопка \"Подключить почту\" будет вести "
        "на относительный путь, и Telegram отклонит такое сообщение "
        "(\"URL host is empty\"). Укажите полный https-адрес формы (домен или ngrok)."
    )


class GuideStates(StatesGroup):
    """Шаги гида-проводника — отслеживают, на каком шаге находится пользователь.
    Это не сбор данных (подключение почты остаётся в веб-форме), а просто
    инструкция с навигацией по инлайн-кнопкам."""
    mail = State()
    destination = State()
    done = State()


# ---------------------------------------------------------------------------
# Общие построители текста/клавиатур
# ---------------------------------------------------------------------------

def _connect_url(telegram_id):
    return f"{WEB_BASE_URL}/connect?telegram_id={telegram_id}"


def _confirm_keyboard(action):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm:{action}:yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"confirm:{action}:no"),
    ]])


def _menu_keyboard(telegram_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Подключить почту", url=_connect_url(telegram_id))],
        [InlineKeyboardButton(text="♻️ Сбросить чат", callback_data="menu:reset_chat")],
        [InlineKeyboardButton(text="🗑 Сбросить почту", callback_data="menu:reset_mail")],
        [InlineKeyboardButton(text="ℹ️ Статус", callback_data="menu:status")],
    ])


async def _status_text(telegram_id):
    user = await get_user_by_telegram_id(telegram_id)

    if user is None or user.email is None:
        mail_line = "📭 Почта: не подключена"
    else:
        mail_line = f"📬 Почта: {user.email}"

    if user is not None and user.dest_chat_id is not None:
        if user.dest_thread_id is not None:
            dest_line = "📍 Письма идут: в привязанный топик группы"
        else:
            dest_line = "📍 Письма идут: в привязанную группу"
    else:
        dest_line = "📍 Письма идут: в личные сообщения (по умолчанию)"

    return f"ℹ️ Статус\n\n{mail_line}\n{dest_line}"


# ---------------------------------------------------------------------------
# Гид-проводник: содержимое шагов
# ---------------------------------------------------------------------------

def _step1_mail(telegram_id):
    text = (
        "Шаг 1 из 3 — подключи почту 📬\n\n"
        "Нажми на кнопку ниже — откроется защищённая веб-страница. На ней "
        "нужно указать IMAP-сервер (для популярных почтовых служб подставится "
        "сам), адрес почты и пароль.\n\n"
        "⚠️ Для Gmail, Яндекс.Почты и Mail.ru вместо обычного пароля от "
        "аккаунта нужен «пароль приложения» — его создают в настройках "
        "безопасности аккаунта.\n\n"
        "Когда подключишь почту, нажми «Готово, дальше»."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Подключить почту", url=_connect_url(telegram_id))],
        [InlineKeyboardButton(text="Готово, дальше ➡️", callback_data="guide:next")],
    ])
    return text, keyboard


def _step2_destination():
    text = (
        "Шаг 2 из 3 — куда слать письма 📍\n\n"
        "По умолчанию я присылаю новые письма прямо сюда, в личные сообщения "
        "— ничего дополнительно делать не нужно.\n\n"
        "Если хочешь получать их в группе с темами (топиками):\n"
        "1. Добавь меня в нужную группу — я сам пришлю туда подсказку;\n"
        "2. Открой в группе тот топик, куда должны приходить письма;\n"
        "3. Отправь в этом топике команду /bind — и готово, письма пойдут туда.\n\n"
        "Если в группе нет топиков, /bind просто привяжет всю группу целиком.\n\n"
        "Это можно настроить в любой момент, не обязательно прямо сейчас."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Дальше ➡️", callback_data="guide:next")],
    ])
    return text, keyboard


async def _step3_done(telegram_id):
    status = await _status_text(telegram_id)
    text = (
        "Шаг 3 из 3 — готово ✅\n\n"
        f"{status}\n\n"
        "Настройки можно поменять в любой момент кнопками ниже или командой "
        "/menu. Чтобы снова открыть этот гид — отправь /help."
    )
    return text, _menu_keyboard(telegram_id)


# ---------------------------------------------------------------------------
# Команды (только в личном чате — гид и меню привязаны к telegram_id)
# ---------------------------------------------------------------------------

@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(GuideStates.mail)
    text, keyboard = _step1_mail(message.from_user.id)

    await message.answer(
        "👋 Привет! Я пересылаю новые письма с твоей почты прямо в Telegram — "
        "в личные сообщения или в групповой чат с топиками, как тебе удобнее.\n\n"
        "Сейчас коротко расскажу, как всё настроить.\n\n" + text,
        reply_markup=keyboard,
    )


@router.message(Command("help"), F.chat.type == "private")
async def cmd_help(message: Message, state: FSMContext):
    await state.set_state(GuideStates.mail)
    text, keyboard = _step1_mail(message.from_user.id)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("menu"), F.chat.type == "private")
async def cmd_menu(message: Message):
    await message.answer(
        "⚙️ Управление\n\nВыбери действие:",
        reply_markup=_menu_keyboard(message.from_user.id),
    )


# ---------------------------------------------------------------------------
# /bind — привязка группы/топика как места доставки
# ---------------------------------------------------------------------------

@router.message(Command("bind"), F.chat.type == "private")
async def cmd_bind_private(message: Message):
    await message.answer(
        "Команда /bind работает только внутри группы: добавь меня в группу "
        "(желательно с топиками), открой нужный топик и отправь /bind прямо там."
    )


@router.message(Command("bind"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_bind_group(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if user is None or user.email is None:
        await message.answer(
            "Сначала подключи почту в личном чате со мной — напиши мне /start "
            "и пройди шаг 1, потом возвращайся сюда и снова отправь /bind."
        )
        return

    thread_id = message.message_thread_id if message.is_topic_message else None
    await set_destination(message.from_user.id, message.chat.id, thread_id)
    await message.answer("✅ Письма будут приходить сюда.")


# ---------------------------------------------------------------------------
# Навигация по гиду
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "guide:next", GuideStates.mail)
async def guide_next_to_destination(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GuideStates.destination)
    text, keyboard = _step2_destination()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "guide:next", GuideStates.destination)
async def guide_next_to_done(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GuideStates.done)
    text, keyboard = await _step3_done(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ---------------------------------------------------------------------------
# Меню управления (кнопки из /start-финала, /menu)
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "menu:status")
async def menu_status(callback: CallbackQuery):
    await callback.message.answer(await _status_text(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data == "menu:reset_chat")
async def menu_reset_chat(callback: CallbackQuery):
    await callback.message.answer(
        "♻️ Сбросить привязку чата? Письма снова будут приходить в личные сообщения.",
        reply_markup=_confirm_keyboard("reset_chat"),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:reset_mail")
async def menu_reset_mail(callback: CallbackQuery):
    await callback.message.answer(
        "🗑 Удалить подключённую почту? Я остановлю опрос и сотру email и "
        "пароль из базы. Привязку чата это не затронет.",
        reply_markup=_confirm_keyboard("reset_mail"),
    )
    await callback.answer()


@router.callback_query(F.data == "confirm:reset_chat:yes")
async def confirm_reset_chat_yes(callback: CallbackQuery):
    await clear_destination(callback.from_user.id)
    await callback.message.edit_text(
        "✅ Привязка чата сброшена — письма снова идут в личные сообщения."
    )
    await callback.answer()


@router.callback_query(F.data == "confirm:reset_chat:no")
async def confirm_reset_chat_no(callback: CallbackQuery):
    await callback.message.edit_text("Отменено — привязка чата не изменена.")
    await callback.answer()


@router.callback_query(F.data == "confirm:reset_mail:yes")
async def confirm_reset_mail_yes(callback: CallbackQuery):
    await clear_mailbox(callback.from_user.id)
    await callback.message.edit_text(
        "✅ Почта удалена, опрос остановлен. Подключить новую можно в любой "
        "момент через /menu."
    )
    await callback.answer()


@router.callback_query(F.data == "confirm:reset_mail:no")
async def confirm_reset_mail_no(callback: CallbackQuery):
    await callback.message.edit_text("Отменено — почта осталась подключена.")
    await callback.answer()


# ---------------------------------------------------------------------------
# Бота добавили в группу — подсказываем, как привязать топик/чат
# ---------------------------------------------------------------------------

@router.my_chat_member()
async def on_bot_membership_changed(update: ChatMemberUpdated):
    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status
    became_member = old_status in ("left", "kicked") and new_status in ("member", "administrator")

    if not became_member:
        return

    try:
        await update.bot.send_message(
            chat_id=update.chat.id,
            text=(
                "👋 Спасибо, что добавили меня сюда!\n\n"
                "Чтобы письма с почты приходили именно в этот чат:\n"
                "1. Откройте нужный топик (если в группе включены темы);\n"
                "2. Отправьте в нём команду /bind.\n\n"
                "Я отвечу прямо там, и с этого момента письма будут приходить туда."
            ),
        )
    except Exception as e:
        logging.error(f"Не удалось отправить инструкцию в чат {update.chat.id}: {e}")

# Сообщение об успешном подключении ("✅ Почта ... подключена!") отправляется
# не отсюда, а из web/routes.py сразу после того, как веб-форма проверила и
# сохранила данные — у бота и веб-сервиса разные процессы, и у веб-сервиса нет
# экземпляра aiogram.Bot (см. _notify_connected в web/routes.py).
