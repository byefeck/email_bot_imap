import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Локально — sqlite+aiosqlite (файл рядом с проектом), в проде — postgresql+asyncpg.
# Переключение полностью определяется DATABASE_URL из .env, код БД от этого не зависит.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./local.db")

engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
