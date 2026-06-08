from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, LargeBinary, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)

    imap_host: Mapped[str] = mapped_column(String(255))
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    email: Mapped[str] = mapped_column(String(255))

    # Способ авторизации на IMAP: сейчас всегда "password", позже добавится "oauth".
    # Хранится отдельно от encrypted_secret, чтобы при логине можно было собрать
    # нужный объект Credentials (см. auth/credentials.py и database/crud.py).
    auth_method: Mapped[str] = mapped_column(String(32), default="password")
    encrypted_secret: Mapped[bytes] = mapped_column(LargeBinary)

    # None — почта ещё не опрашивалась ни разу (нужно зафиксировать стартовый UID,
    # не присылая всю историю). 0 — валидный технический случай (пустой ящик при
    # подключении), поэтому как "неинициализировано" используем именно None.
    last_uid: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
