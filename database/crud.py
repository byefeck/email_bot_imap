from sqlalchemy import select

from auth.credentials import PasswordCredentials
from auth.crypto import decrypt_secret, encrypt_secret
from database.db import async_session
from database.models import User

async def get_all_users():
    """Возвращает пользователей с подключённым ящиком — после "Сбросить почту"
    (см. clear_mailbox) email становится None, и опрашивать такую запись
    в mail_loop не нужно, хотя сама строка User остаётся (в ней привязка чата)."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email.isnot(None)))
        return list(result.scalars().all())

async def get_user_by_telegram_id(telegram_id):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

async def upsert_user(telegram_id, imap_host, imap_port, email, password):
    """Сохраняет (или переподключает) учётку пользователя. Способ авторизации
    пока всегда "password" — позже здесь же появится ветка для oauth-токенов."""
    encrypted_secret = encrypt_secret(password)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_id,
                imap_host=imap_host,
                imap_port=imap_port,
                email=email,
                auth_method="password",
                encrypted_secret=encrypted_secret,
                uid_validity=None,
                last_uid=None,
            )
            session.add(user)
        else:
            user.imap_host = imap_host
            user.imap_port = imap_port
            user.email = email
            user.auth_method = "password"
            user.encrypted_secret = encrypted_secret
            # переподключение — отслеживаем почту с чистого листа
            user.uid_validity = None
            user.last_uid = None

        await session.commit()
        await session.refresh(user)
        return user

async def update_last_uid(telegram_id, last_uid):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.last_uid = last_uid
            await session.commit()

async def set_mailbox_baseline(telegram_id, uid_validity, last_uid):
    """Фиксирует пару (uid_validity, last_uid) как новую стартовую точку слежения —
    используется при первом подключении ящика и при смене UIDVALIDITY (папка
    пересоздана, старые UID невалидны). В обоих случаях новые письма не шлём,
    просто запоминаем текущий максимальный UID — аналог фиксации historyId в Gmail API."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.uid_validity = uid_validity
            user.last_uid = last_uid
            await session.commit()

async def set_destination(telegram_id, chat_id, thread_id):
    """Привязывает место доставки писем — групповой чат (и опционально топик
    в нём), пойманные из апдейта команды /bind (см. bot/handlers.py)."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.dest_chat_id = chat_id
            user.dest_thread_id = thread_id
            await session.commit()

async def clear_destination(telegram_id):
    """Снимает привязку чата/топика — письма снова идут в личные сообщения."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.dest_chat_id = None
            user.dest_thread_id = None
            await session.commit()

async def clear_mailbox(telegram_id):
    """Стирает данные почтового ящика (включая зашифрованный пароль) и сбрасывает
    слежение по UID — mail_loop перестаёт опрашивать эту запись (см. get_all_users).
    Привязку чата (dest_chat_id/dest_thread_id) не трогаем: строка User остаётся,
    и при повторном подключении почты привязка сохранится."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.imap_host = None
            user.imap_port = None
            user.email = None
            user.encrypted_secret = None
            user.uid_validity = None
            user.last_uid = None
            await session.commit()

def get_destination(user):
    """Куда слать письма пользователя: привязанные группа/топик, если они
    заданы, иначе — личные сообщения (поведение по умолчанию)."""
    if user.dest_chat_id is not None:
        return user.dest_chat_id, user.dest_thread_id
    return user.telegram_id, None

def build_credentials(user):
    """Собирает объект Credentials по способу авторизации, сохранённому в БД.
    Сейчас поддерживается только "password"; добавление "oauth" не потребует
    изменений в imap/ — только новой ветки здесь и нового подкласса Credentials."""
    secret = decrypt_secret(user.encrypted_secret)

    if user.auth_method == "password":
        return PasswordCredentials(user.email, secret)

    raise ValueError(f"Неизвестный способ авторизации: {user.auth_method}")
