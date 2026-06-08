from email.header import decode_header

from message.parser import parse_sender
from message.cleaner import clean_html

def _decode_header_value(value):
    if not value:
        return ""
    decoded = []
    for text, charset in decode_header(value):
        if isinstance(text, bytes):
            decoded.append(text.decode(charset or "utf-8", errors="ignore"))
        else:
            decoded.append(text)
    return "".join(decoded)

def _decode_payload(part):
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="ignore")
    except LookupError:
        return payload.decode("utf-8", errors="ignore")

def _is_attachment(part):
    if (part.get_content_disposition() or "").lower() == "attachment":
        return True
    return bool(part.get_filename())

def get_text(msg):
    text_plain = None
    text_html = None

    for part in msg.walk():
        if part.is_multipart() or _is_attachment(part):
            continue

        content_type = part.get_content_type()
        if content_type == "text/plain" and text_plain is None:
            text_plain = _decode_payload(part)
        elif content_type == "text/html" and text_html is None:
            text_html = clean_html(_decode_payload(part))

    if text_plain:
        return text_plain
    if text_html:
        return text_html
    return ""

def has_attachments(msg):
    for part in msg.walk():
        if part.is_multipart():
            continue
        if _is_attachment(part):
            return True
    return False

def imap_message_to_dict(msg):
    """Приводит email.message.Message из IMAP к dict, который ожидает format_msg —
    тому же, что раньше возвращал gmail/parse_message (sender_name, sender_email,
    subject, text, has_att)."""
    sender = _decode_header_value(msg.get("From")) or "Неизвестно"
    name, sender_email = parse_sender(sender)
    subject = _decode_header_value(msg.get("Subject")) or "Без темы"

    return {
        "sender_name": name,
        "sender_email": sender_email,
        "subject": subject,
        "text": get_text(msg),
        "has_att": has_attachments(msg)
    }
