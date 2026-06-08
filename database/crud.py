from sqlalchemy import select

from auth.credentials import PasswordCredentials
from auth.crypto import decrypt_secret, encrypt_secret
from database.db import async_session
from database.models import User

async def get_all_users():
    async with async_session() as session:
        result = await session.execute(select(User))
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
                last_uid=None,
            )
            session.add(user)
        else:
            user.imap_host = imap_host
            user.imap_port = imap_port
            user.email = email
            user.auth_method = "password"
            user.encrypted_secret = encrypted_secret
            user.last_uid = None  # переподключение — отслеживаем почту с чистого листа

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

def build_credentials(user):
    """Собирает объект Credentials по способу авторизации, сохранённому в БД.
    Сейчас поддерживается только "password"; добавление "oauth" не потребует
    изменений в imap/ — только новой ветки здесь и нового подкласса Credentials."""
    secret = decrypt_secret(user.encrypted_secret)

    if user.auth_method == "password":
        return PasswordCredentials(user.email, secret)

    raise ValueError(f"Неизвестный способ авторизации: {user.auth_method}")
