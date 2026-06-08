# Автоподбор IMAP-сервера по домену почты для веб-формы подключения.
# Пользователь всегда может изменить host/port вручную — это лишь подсказка.
IMAP_PRESETS = {
    "gmail.com": ("imap.gmail.com", 993),
    "googlemail.com": ("imap.gmail.com", 993),
    "mail.ru": ("imap.mail.ru", 993),
    "inbox.ru": ("imap.mail.ru", 993),
    "list.ru": ("imap.mail.ru", 993),
    "bk.ru": ("imap.mail.ru", 993),
    "internet.ru": ("imap.mail.ru", 993),
    "yandex.ru": ("imap.yandex.ru", 993),
    "ya.ru": ("imap.yandex.ru", 993),
    "yandex.com": ("imap.yandex.ru", 993),
    "outlook.com": ("outlook.office365.com", 993),
    "hotmail.com": ("outlook.office365.com", 993),
    "live.com": ("outlook.office365.com", 993),
    "yahoo.com": ("imap.mail.yahoo.com", 993),
    "icloud.com": ("imap.mail.me.com", 993),
    "rambler.ru": ("imap.rambler.ru", 993),
}

def guess_imap_server(email: str):
    if "@" not in email:
        return None
    domain = email.strip().lower().rsplit("@", 1)[-1]
    return IMAP_PRESETS.get(domain)
