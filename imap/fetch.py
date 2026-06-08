import email
import logging
import os
import re

# Предохранитель от лавины: если за время простоя бота накопилось больше
# MAX_CATCHUP писем, шлём только последние MAX_CATCHUP, а более старые сразу
# помечаем обработанными (см. find_new_uids), чтобы не топить чат историей.
MAX_CATCHUP = int(os.getenv("MAX_CATCHUP", "50"))

_UIDVALIDITY_RE = re.compile(rb"UIDVALIDITY (\d+)")

async def get_mailbox_state(client):
    """Текущие (uid_validity, max_uid) папки INBOX.

    uid_validity — версия "пространства UID" на сервере (RFC 3501 §2.3.1.1):
    меняется, если папка была пересоздана и старые UID больше не валидны
    (аналог 404 при протухшем historyId в Gmail API). max_uid — текущий
    максимальный UID, используется как стартовая точка при первом подключении
    или после сброса. Если сервер не ответил, uid_validity будет None —
    вызывающий код должен в этом случае ничего не сохранять и попробовать позже.
    """
    uid_validity = await _get_uid_validity(client)
    max_uid = await get_latest_uid(client)
    return uid_validity, max_uid

async def _get_uid_validity(client):
    response = await client.status("INBOX", "(UIDVALIDITY)")
    if response.result != "OK":
        return None

    for line in response.lines:
        if isinstance(line, (bytes, bytearray)):
            match = _UIDVALIDITY_RE.search(bytes(line))
            if match:
                return int(match.group(1))

    return None

async def get_latest_uid(client):
    """UID последнего письма в INBOX. Используется как baseline при первом
    подключении пользователя и при сбросе из-за смены UIDVALIDITY — аналог
    получения текущего historyId в Gmail API."""
    response = await client.uid_search("ALL", charset=None)
    if response.result != "OK":
        return 0

    uids = response.lines[0].split()
    return int(uids[-1]) if uids else 0

async def find_new_uids(client, last_uid, max_catchup=MAX_CATCHUP):
    """Возвращает (uids, skip_to_uid) для писем с UID > last_uid, по возрастанию.

    UID SEARCH "<last_uid+1>:*" по стандарту всегда возвращает минимум одно
    письмо (с максимальным UID в ящике), даже если новых нет — поэтому результат
    обязательно фильтруется по строгому условию uid > last_uid.

    Если новых писем накопилось больше max_catchup (бот долго простаивал),
    возвращаются только последние max_catchup UID, а skip_to_uid — это граница,
    до которой вызывающий код должен сразу продвинуть last_uid в БД (не отправляя
    письма), чтобы не флудить чат всей накопившейся историей.
    """
    response = await client.uid_search("UID", f"{last_uid + 1}:*", charset=None)
    if response.result != "OK":
        return [], None

    uids = sorted({int(u) for u in response.lines[0].split() if int(u) > last_uid})
    if not uids:
        return [], None

    if max_catchup and len(uids) > max_catchup:
        skip_to_uid = uids[-max_catchup - 1]
        return uids[-max_catchup:], skip_to_uid

    return uids, None

async def fetch_message(client, uid):
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
