from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from .config import settings

# Engine configuration depends on standalone mode
if settings.STANDALONE:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        pool_size=5,
        max_overflow=10
    )

# Async Session Local
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for all models
Base = declarative_base()


async def init_db():
    """Create all tables if they don't exist (standalone mode)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.STANDALONE:
            await conn.execute(
                __import__('sqlalchemy').text("PRAGMA journal_mode=WAL")
            )


# Dependency func to get DB session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
