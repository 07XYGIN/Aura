from collections.abc import AsyncGenerator
import time

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import PG_DATABASE_URL
from app.core.logging_config import install_sql_logging, log_sql_result


engine = create_async_engine(
    PG_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
install_sql_logging(engine)


class LoggingAsyncSession(AsyncSession):
    async def execute(self, *args, **kwargs):
        started_at = time.perf_counter()
        result = await super().execute(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        return log_sql_result(result, elapsed_ms)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=LoggingAsyncSession,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
