import os
from dataclasses import dataclass
from email.header import decode_header
from email.utils import collapse_rfc2231_value

# Совсем мелкие inline-картинки (логотипы, подписи, трекинг-пиксели) не несут
# полезной нагрузки — отбрасываем их по размеру, не дожидаясь явного inline.
MIN_IMAGE_SIZE = int(os.getenv("ATTACHMENT_MIN_IMAGE_SIZE", "10240"))


@dataclass
class Attachment:
    filename: str
    mime_type: str
    size: int
    data: bytes


def _decode_filename(part):
    filename = part.get_filename()
    if not filename:
        return ""

    decoded = []
    for text, charset in decode_header(filename):
        if isinstance(text, bytes):
            decoded.append(text.decode(charset or "utf-8", errors="ignore"))
        else:
            decoded.append(text)
    return collapse_rfc2231_value("".join(decoded))


def _is_real_attachment(part, filename):
    """Реальное вложение — это часть с Content-Disposition: attachment либо
    часть с непустым именем файла, которая explicitly не помечена как inline
    (логотипы/подписи/трекинг-пиксели идут с Content-Disposition: inline и/или
    Content-ID и не должны пересылаться)."""
    disposition = (part.get_content_disposition() or "").lower()
    if disposition == "attachment":
        return True
    if disposition == "inline":
        return False
    return bool(filename)


def extract_attachments(msg):
    """Собирает реальные вложения письма: имя файла, MIME-тип, размер и байты
    (уже декодированные из base64/quoted-printable). Inline-картинки и мелкий
    декоративный мусор отфильтровываются."""
    attachments = []

    for part in msg.walk():
        if part.is_multipart():
            continue

        filename = _decode_filename(part)
        if not _is_real_attachment(part, filename):
            continue

        data = part.get_payload(decode=True)
        if not data:
            continue

        mime_type = part.get_content_type()
        size = len(data)

        if mime_type.startswith("image/") and size < MIN_IMAGE_SIZE:
            continue

        attachments.append(Attachment(
            filename=filename or "attachment",
            mime_type=mime_type,
            size=size,
            data=data,
        ))

    return attachments
