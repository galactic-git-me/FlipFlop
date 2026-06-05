from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from sqlalchemy.pool import NullPool
from app.config import get_settings
import os

settings = get_settings()

# Override with SQLite if DATABASE_URL env var is set explicitly, or use config default
_database_url = os.getenv("DATABASE_URL", settings.database_url)
_is_sqlite = _database_url.startswith("sqlite")

if _is_sqlite:
    # NullPool: each session gets its own connection, preventing pool exhaustion
    # when long-running scans hold connections while API reads are waiting.
    # WAL mode (set in the connect listener) allows concurrent reads alongside writes.
    engine = create_async_engine(
        _database_url,
        echo=False,
        connect_args={"timeout": 30},
        poolclass=NullPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(conn, _):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
else:
    engine = create_async_engine(
        _database_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
