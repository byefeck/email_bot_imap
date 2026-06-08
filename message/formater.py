import html

SEPARATOR = "─" * 18
TRUNCATION_NOTE = "…\n<i>(письмо обрезано)</i>"


def _esc(value):
    return html.escape(value or "")


def _attachments_summary(attachments):
    if not attachments:
        return ""

    photos = [a for a in attachments if a.mime_type.startswith("image/")]
    files = [a for a in attachments if not a.mime_type.startswith("image/")]

    if len(attachments) <= 3:
        return ", ".join(_esc(a.filename) for a in attachments)

    parts = []
    if photos:
        parts.append(f"фото ×{len(photos)}")
    if files:
        parts.append(f"файлы ×{len(files)}")
    return ", ".join(parts)


def _build_header(msg_dict):
    lines = [f"✉️ <b>Тема:</b> {_esc(msg_dict['subject'])}"]

    sender_name = _esc(msg_dict["sender_name"])
    sender_email = _esc(msg_dict["sender_email"])
    lines.append(f"👤 <b>От:</b> {sender_name} &lt;{sender_email}&gt;")

    if msg_dict.get("date"):
        lines.append(f"🕒 <b>Получено:</b> {_esc(msg_dict['date'])}")

    summary = _attachments_summary(msg_dict.get("attachments"))
    if summary:
        lines.append(f"📎 <b>Вложения:</b> {summary}")

    return "\n".join(lines)


def _fit_body(body, limit):
    """Обрезает тело письма так, чтобы итоговое сообщение (шапка + тело +
    при необходимости пометка об обрезке) не превышало
    лимит. Режет по границе строки, не разрывая html-сущности."""
    if len(body) <= limit:
        return body, False

    cut = body[:limit]
    last_break = max(cut.rfind("\n"), cut.rfind(" "))
    if last_break > 0:
        cut = cut[:last_break]

    last_amp = cut.rfind("&")
    if last_amp != -1 and ";" not in cut[last_amp:]:
        cut = cut[:last_amp]

    return cut.rstrip(), True


def format_msg(msg_dict, limit=4096):
    header = _build_header(msg_dict)
    body = _esc(msg_dict["text"])

    fixed_len = len(header) + 1 + len(SEPARATOR) + 2

    available = max(limit - fixed_len, 0)
    note_len = len(TRUNCATION_NOTE) + 1
    fitted_body, truncated = _fit_body(body, available)
    if truncated and available > note_len:
        fitted_body, _ = _fit_body(body, available - note_len)
        fitted_body = f"{fitted_body}\n{TRUNCATION_NOTE}"

    return f"{header}\n{SEPARATOR}\n\n{fitted_body}"
