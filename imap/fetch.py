import email
import logging

async def get_latest_uid(client):
    """UID последнего письма в INBOX. Используется при первом подключении пользователя,
    чтобы не присылать всю историю почты — аналог получения текущего historyId в Gmail API."""
    response = await client.uid_search("ALL", charset=None)
    if response.result != "OK":
        return 0

    uids = response.lines[0].split()
    return int(uids[-1]) if uids else 0

async def fetch_new_messages(client, last_uid):
    """Возвращает новые письма с UID > last_uid и новый последний UID.

    Дедупликация в мультипользовательском режиме строится на этом же last_uid,
    который хранится в БД per-user (вместо общего processed_msg_ids/history_id).
    """
    response = await client.uid_search("UID", f"{last_uid + 1}:*", charset=None)
    if response.result != "OK":
        return [], last_uid

    uids = sorted({int(u) for u in response.lines[0].split() if int(u) > last_uid})
    if not uids:
        return [], last_uid

    messages = []
    for uid in uids:
        msg = await _fetch_message(client, uid)
        if msg is not None:
            messages.append((uid, msg))

    return messages, uids[-1]

async def _fetch_message(client, uid):
    try:
        response = await client.uid("fetch", str(uid), "BODY.PEEK[]")
    except Exception as e:
        logging.error(f"Ошибка получения письма UID {uid}: {e}")
        return None

    if response.result != "OK":
        return None

    for line in response.lines:
        if isinstance(line, bytearray):
            try:
                return email.message_from_bytes(bytes(line))
            except Exception as e:
                logging.error(f"Не удалось разобрать письмо UID {uid}: {e}")
                return None

    return None
