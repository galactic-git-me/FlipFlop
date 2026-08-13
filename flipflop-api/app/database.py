from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings
import os

settings = get_settings()

# Postgres only — no SQLite fallback. SQLite's single-writer lock made this
# app's concurrent scan-scoring workload (many overlapping /scans requests,
# each opening several DB sessions at once) serialize hard and stall; this
# app is designed around Postgres's real concurrent-write support and must
# never silently downgrade to SQLite again.
_database_url = os.getenv("DATABASE_URL", settings.database_url)
if not _database_url.startswith("postgresql"):
    raise RuntimeError(
        f"DATABASE_URL must be a postgresql+asyncpg:// connection string, got: {_database_url!r}. "
        "This app requires Postgres for concurrent-write support — SQLite is not supported."
    )

engine = create_async_engine(
    _database_url,
    echo=False,
    pool_size=30,  # Increased to handle concurrent workers + dashboard
    max_overflow=15,  # Allow up to 45 total connections before failing
    pool_pre_ping=True,  # Test connection before reuse
    pool_recycle=300,  # Reduced from 3600s — recycle dead connections faster (5 min)
    pool_timeout=10,  # Wait max 10s for available connection before failing
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


async def init_db():
    """Initialize database tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_db_pool_stats() -> dict:
    """Get current connection pool statistics."""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total_connections": pool.size() + pool.overflow(),
    }
