import asyncio
import logging

from bot.attachment_sender import send_email_to_telegram
from database.crud import build_credentials, get_all_users, get_destination, set_mailbox_baseline, update_last_uid
from imap.adapter import imap_message_to_dict
from imap.fetch import MAX_CATCHUP, fetch_message, find_new_uids, get_mailbox_state
from imap.service import connect, disconnect

POLL_INTERVAL = 5

async def mail_loop(bot):
    while True:
        try:
            users = await get_all_users()
            for user in users:
                await _poll_user(bot, user)
                await asyncio.sleep(POLL_INTERVAL)
        except Exception as e:
            logging.error(f"Ошибка mail_loop: {e}")

        await asyncio.sleep(POLL_INTERVAL)

async def _poll_user(bot, user):
    try:
        credentials = build_credentials(user)
        client = await connect(user.imap_host, user.imap_port, credentials)
    except Exception as e:
        logging.error(f"Не удалось подключиться к почте пользователя {user.telegram_id}: {e}")
        return

    try:
        uid_validity, max_uid = await get_mailbox_state(client)
        if uid_validity is None:
            logging.error(f"Не удалось получить UIDVALIDITY ({user.telegram_id})")
            return

        if user.uid_validity is None or user.last_uid is None:
            # Первое подключение: запоминаем текущий UIDVALIDITY и последний UID,
            # не шлём историю — аналог фиксации стартового historyId в Gmail API.
            await set_mailbox_baseline(user.telegram_id, uid_validity, max_uid)
            return

        if user.uid_validity != uid_validity:
            # Папка пересоздана — старые UID больше не валидны, сбрасываемся
            # на новый baseline, как при первом подключении.
            logging.warning(
                f"UIDVALIDITY ящика {user.telegram_id} изменился "
                f"({user.uid_validity} -> {uid_validity}), сброс на UID {max_uid}"
            )
            await set_mailbox_baseline(user.telegram_id, uid_validity, max_uid)
            return

        uids, skip_to_uid = await find_new_uids(client, user.last_uid)

        if skip_to_uid is not None:
            logging.warning(
                f"У пользователя {user.telegram_id} накопилось больше {MAX_CATCHUP} писем, "
                f"пропускаем до UID {skip_to_uid}, чтобы не флудить"
            )
            await update_last_uid(user.telegram_id, skip_to_uid)

        for uid in uids:
            await _process_message(bot, user, client, uid)
            await update_last_uid(user.telegram_id, uid)
    except Exception as e:
        logging.error(f"Ошибка опроса почты пользователя {user.telegram_id}: {e}")
    finally:
        await disconnect(client)

async def _process_message(bot, user, client, uid):
    """Обрабатывает одно письмо: скачивает, парсит и отправляет в чат (если оно
    не от самого пользователя). При любой ошибке логирует её и уведомляет
    пользователя, какое именно письмо не удалось доставить — но не прерывает
    обход, чтобы один проблемный UID не застревал в очереди навсегда."""
    msg_dict = None
    try:
        msg = await fetch_message(client, uid)
        if msg is None:
            raise RuntimeError("сервер не вернул содержимое письма")

        msg_dict = imap_message_to_dict(msg)

        if msg_dict["sender_email"].lower() != user.email.lower():
            chat_id, thread_id = get_destination(user)
            await send_email_to_telegram(bot, msg_dict, chat_id, thread_id)
            await asyncio.sleep(POLL_INTERVAL)
    except Exception as e:
        logging.error(f"Ошибка обработки письма UID {uid} (пользователь {user.telegram_id}): {e}")
        await _notify_processing_error(bot, user, uid, msg_dict)

async def _notify_processing_error(bot, user, uid, msg_dict):
    if msg_dict is not None:
        text = (
            "⚠️ Не удалось доставить одно из писем.\n"
            f"UID: {uid}\n"
            f"От: {msg_dict['sender_name']} <{msg_dict['sender_email']}>\n"
            f"Тема: {msg_dict['subject']}"
        )
    else:
        text = (
            "⚠️ Не удалось получить одно из писем с почтового сервера.\n"
            f"UID: {uid}"
        )

    try:
        chat_id, thread_id = get_destination(user)
        await bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text=text)
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление об ошибке (пользователь {user.telegram_id}): {e}")
