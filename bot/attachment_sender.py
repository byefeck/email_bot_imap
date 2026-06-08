import logging
import os

from aiogram.types import BufferedInputFile, InputMediaDocument, InputMediaPhoto

from message.formater import format_msg

CAPTION_LIMIT = 1024

# Жёсткие лимиты Telegram Bot API — не настройки, а ограничения протокола.
PHOTO_MAX_SIZE = 10 * 1024 * 1024
DOCUMENT_MAX_SIZE = 50 * 1024 * 1024
GROUP_LIMIT = 10

PHOTO_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ANIMATION_MIME_TYPES = {"image/gif"}

# Предохранитель от лавины тяжёлых вложений в одном письме.
MAX_TOTAL_SIZE = int(os.getenv("ATTACHMENT_MAX_TOTAL_SIZE", str(50 * 1024 * 1024)))
MAX_COUNT = int(os.getenv("ATTACHMENT_MAX_COUNT", "20"))


def _format_size(size):
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} МБ"
    return f"{max(size, 1) / 1024:.0f} КБ"


def _input_file(att):
    return BufferedInputFile(att.data, filename=att.filename)


def _classify(att):
    if att.mime_type in ANIMATION_MIME_TYPES:
        return "animation"
    if att.mime_type in PHOTO_MIME_TYPES and att.size <= PHOTO_MAX_SIZE:
        return "photo"
    return "document"


def _apply_safety_net(attachments):
    """Обрезает список вложений по суммарному размеру/количеству, чтобы одно
    письмо не залило чат десятком тяжёлых файлов. Возвращает (выбранные,
    сколько отброшено)."""
    selected = []
    total = 0
    for att in attachments:
        if len(selected) >= MAX_COUNT or total + att.size > MAX_TOTAL_SIZE:
            break
        selected.append(att)
        total += att.size
    return selected, len(attachments) - len(selected)


def _group_runs(attachments):
    """Бьёт список на подряд идущие вложения одного типа отправки, чанками не
    больше GROUP_LIMIT (для media_group). Анимации всегда идут отдельно."""
    groups = []
    current_kind, current = None, []

    for att in attachments:
        kind = _classify(att)
        if kind == "animation":
            if current:
                groups.append((current_kind, current))
                current_kind, current = None, []
            groups.append(("animation", [att]))
            continue

        if kind != current_kind or len(current) >= GROUP_LIMIT:
            if current:
                groups.append((current_kind, current))
            current_kind, current = kind, []
        current.append(att)

    if current:
        groups.append((current_kind, current))

    return groups


async def send_email_to_telegram(bot, msg_dict, chat_id, thread_id):
    """Пересылает письмо в Telegram в строгом порядке ФОТО → ДОКУМЕНТЫ → ТЕКСТ,
    минимизируя число сообщений: если вложения — это только фото и оформленный
    текст влезает в подпись, текст уходит подписью к первому фото альбома
    (вариант А). Иначе фото и документы уходят отдельными альбомами без
    подписи, а текст — последним сообщением (вариант Б)."""
    selected, skipped = _apply_safety_net(msg_dict.get("attachments") or [])
    photos = [att for att in selected if _classify(att) == "photo"]
    others = [att for att in selected if _classify(att) != "photo"]

    if photos and not others:
        caption = format_msg(msg_dict, limit=CAPTION_LIMIT)
        if len(caption) <= CAPTION_LIMIT:
            await _send_photo_albums(bot, chat_id, thread_id, photos, caption=caption)
            await _notify_skipped(bot, chat_id, thread_id, skipped)
            return

    await _send_photo_albums(bot, chat_id, thread_id, photos)
    for kind, group in _group_runs(others):
        if kind == "animation":
            await _send_animation(bot, chat_id, thread_id, group[0])
        else:
            await _send_document_group(bot, chat_id, thread_id, group)

    await bot.send_message(
        chat_id=chat_id, message_thread_id=thread_id,
        text=format_msg(msg_dict, limit=4096), parse_mode="HTML",
    )
    await _notify_skipped(bot, chat_id, thread_id, skipped)


async def _notify_skipped(bot, chat_id, thread_id, skipped):
    if skipped:
        await _send_placeholder(
            bot, chat_id, thread_id,
            f"📎 Ещё {skipped} вложений не переслано — превышен лимит вложений на письмо."
        )


async def _send_photo_albums(bot, chat_id, thread_id, photos, caption=None):
    """Шлёт фото альбомами не больше GROUP_LIMIT штук; подпись ставится только
    на первое фото самого первого альбома."""
    for index, chunk in enumerate(_chunk(photos, GROUP_LIMIT)):
        chunk_caption = caption if index == 0 else None
        if len(chunk) == 1:
            await _send_single_photo(bot, chat_id, thread_id, chunk[0], caption=chunk_caption)
        else:
            await _send_photo_group(bot, chat_id, thread_id, chunk, caption=chunk_caption)


def _chunk(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]


async def _send_placeholder(bot, chat_id, thread_id, text):
    await bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text=text)


async def _send_too_big_placeholder(bot, chat_id, thread_id, att):
    await _send_placeholder(
        bot, chat_id, thread_id,
        f"📎 {att.filename} ({_format_size(att.size)}) — слишком большое для пересылки в Telegram"
    )


async def _send_failed_placeholder(bot, chat_id, thread_id, att):
    await _send_placeholder(bot, chat_id, thread_id, f"⚠️ Не удалось переслать вложение «{att.filename}».")


# ---------------------------------------------------------------------------
# Фото — альбомами, с поштучным фоллбэком на документ при ошибке отправки
# ---------------------------------------------------------------------------

async def _send_photo_group(bot, chat_id, thread_id, attachments, caption=None):
    if len(attachments) == 1:
        await _send_single_photo(bot, chat_id, thread_id, attachments[0], caption=caption)
        return

    media = []
    for index, att in enumerate(attachments):
        if index == 0 and caption:
            media.append(InputMediaPhoto(media=_input_file(att), caption=caption, parse_mode="HTML"))
        else:
            media.append(InputMediaPhoto(media=_input_file(att)))

    try:
        await bot.send_media_group(chat_id=chat_id, message_thread_id=thread_id, media=media)
    except Exception as e:
        logging.warning(f"Не удалось отправить альбом фото ({len(attachments)} шт.), шлём по одному: {e}")
        for index, att in enumerate(attachments):
            await _send_single_photo(bot, chat_id, thread_id, att, caption=caption if index == 0 else None)


async def _send_single_photo(bot, chat_id, thread_id, att, caption=None):
    try:
        await bot.send_photo(
            chat_id=chat_id, message_thread_id=thread_id, photo=_input_file(att),
            caption=caption, parse_mode="HTML" if caption else None,
        )
        return
    except Exception as e:
        logging.warning(f"Не удалось отправить «{att.filename}» как фото, пробуем как документ: {e}")

    await _send_as_document_with_fallback(bot, chat_id, thread_id, att, caption=caption)


# ---------------------------------------------------------------------------
# Документы — группами, с поштучным фоллбэком и заглушками при ошибке/размере
# ---------------------------------------------------------------------------

async def _send_document_group(bot, chat_id, thread_id, attachments):
    sendable = []
    for att in attachments:
        if att.size > DOCUMENT_MAX_SIZE:
            await _send_too_big_placeholder(bot, chat_id, thread_id, att)
        else:
            sendable.append(att)

    if not sendable:
        return

    if len(sendable) == 1:
        await _send_single_document(bot, chat_id, thread_id, sendable[0])
        return

    media = [InputMediaDocument(media=_input_file(att)) for att in sendable]
    try:
        await bot.send_media_group(chat_id=chat_id, message_thread_id=thread_id, media=media)
    except Exception as e:
        logging.warning(f"Не удалось отправить группу документов ({len(sendable)} шт.), шлём по одному: {e}")
        for att in sendable:
            await _send_single_document(bot, chat_id, thread_id, att)


async def _send_single_document(bot, chat_id, thread_id, att, caption=None):
    try:
        await bot.send_document(
            chat_id=chat_id, message_thread_id=thread_id, document=_input_file(att),
            caption=caption, parse_mode="HTML" if caption else None,
        )
    except Exception as e:
        logging.error(f"Не удалось отправить вложение «{att.filename}»: {e}")
        await _send_failed_placeholder(bot, chat_id, thread_id, att)


async def _send_as_document_with_fallback(bot, chat_id, thread_id, att, caption=None):
    """Используется как фоллбэк, когда вложение не удалось отправить как фото —
    проверяет лимит документа и шлёт заглушку, если ни один способ не сработал."""
    if att.size > DOCUMENT_MAX_SIZE:
        await _send_too_big_placeholder(bot, chat_id, thread_id, att)
        return

    try:
        await bot.send_document(
            chat_id=chat_id, message_thread_id=thread_id, document=_input_file(att),
            caption=caption, parse_mode="HTML" if caption else None,
        )
    except Exception as e:
        logging.error(f"Не удалось отправить вложение «{att.filename}» ни как фото, ни как документ: {e}")
        await _send_failed_placeholder(bot, chat_id, thread_id, att)


# ---------------------------------------------------------------------------
# Анимации (gif) — отдельными сообщениями, с фоллбэком на документ
# ---------------------------------------------------------------------------

async def _send_animation(bot, chat_id, thread_id, att):
    if att.size > DOCUMENT_MAX_SIZE:
        await _send_too_big_placeholder(bot, chat_id, thread_id, att)
        return

    try:
        await bot.send_animation(chat_id=chat_id, message_thread_id=thread_id, animation=_input_file(att))
        return
    except Exception as e:
        logging.warning(f"Не удалось отправить «{att.filename}» как анимацию, пробуем как документ: {e}")

    try:
        await bot.send_document(chat_id=chat_id, message_thread_id=thread_id, document=_input_file(att))
    except Exception as e:
        logging.error(f"Не удалось отправить вложение «{att.filename}» ни как анимацию, ни как документ: {e}")
        await _send_failed_placeholder(bot, chat_id, thread_id, att)
