import asyncio
import logging

from database.crud import build_credentials, get_all_users, update_last_uid
from imap.adapter import imap_message_to_dict
from imap.fetch import fetch_new_messages, get_latest_uid
from imap.service import connect, disconnect
from message.formater import format_msg

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
        if user.last_uid is None:
            # Первое подключение: запоминаем текущий последний UID и не шлём
            # историю — аналог фиксации стартового historyId в Gmail API.
            latest_uid = await get_latest_uid(client)
            await update_last_uid(user.telegram_id, latest_uid)
            return

        messages, new_last_uid = await fetch_new_messages(client, user.last_uid)

        for uid, msg in messages:
            try:
                msg_dict = imap_message_to_dict(msg)

                if msg_dict["sender_email"].lower() == user.email.lower():
                    continue  # пропускаем письма самому себе

                await bot.send_message(chat_id=user.telegram_id, text=format_msg(msg_dict))
                await asyncio.sleep(POLL_INTERVAL)
            except Exception as e:
                logging.error(f"Ошибка обработки письма UID {uid} (пользователь {user.telegram_id}): {e}")
                continue

        if new_last_uid != user.last_uid:
            await update_last_uid(user.telegram_id, new_last_uid)
    except Exception as e:
        logging.error(f"Ошибка опроса почты пользователя {user.telegram_id}: {e}")
    finally:
        await disconnect(client)
