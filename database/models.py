from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, LargeBinary, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)

    # Поля почтового ящика — nullable, потому что после "Сбросить почту"
    # (см. database/crud.clear_mailbox) строка User остаётся (в ней же лежит
    # привязка чата dest_chat_id/dest_thread_id), а сами эти поля обнуляются.
    imap_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_port: Mapped[int | None] = mapped_column(Integer, nullable=True, default=993)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Способ авторизации на IMAP: сейчас всегда "password", позже добавится "oauth".
    # Хранится отдельно от encrypted_secret, чтобы при логине можно было собрать
    # нужный объект Credentials (см. auth/credentials.py и database/crud.py).
    auth_method: Mapped[str] = mapped_column(String(32), default="password")
    encrypted_secret: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    # Состояние слежения за почтой по UID — аналог history_id из Gmail API.
    # Хранится парой, т.к. UID имеет смысл только в рамках конкретного
    # UIDVALIDITY папки (RFC 3501 §2.3.1.1): если папка пересоздана, сервер
    # выдаёт новый UIDVALIDITY и все старые UID становятся недействительными.
    #
    # None в обоих полях — почта ещё не опрашивалась ни разу (нужно
    # зафиксировать стартовый UID, не присылая всю историю). 0 в last_uid —
    # валидный технический случай (пустой ящик при подключении), поэтому как
    # "неинициализировано" используем именно None.
    uid_validity: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None)
    last_uid: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Куда пересылать письма: привязанные группа/топик (см. /bind в bot/handlers.py).
    # Если оба пустые — письма идут в личные сообщения пользователю (поведение
    # по умолчанию, см. database/crud.get_destination).
    dest_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None)
    dest_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
