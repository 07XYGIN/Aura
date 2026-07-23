from collections.abc import AsyncGenerator
import time

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import PG_DATABASE_URL, SYNC_DATABASE_URL
from app.core.logging_config import install_sql_logging, log_sql_result


engine = create_async_engine(
    PG_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
install_sql_logging(engine)

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
install_sql_logging(sync_engine)


class LoggingAsyncSession(AsyncSession):
    """在详细日志模式下记录查询结果与耗时的异步会话。"""

    async def execute(self, *args, **kwargs):
        """执行 SQLAlchemy 语句，并将结果交给统一 SQL 日志处理器。"""
        started_at = time.perf_counter()
        result = await super().execute(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        return log_sql_result(result, elapsed_ms)


class LoggingSession(Session):
    """在详细日志模式下记录查询结果与耗时的同步会话。"""

    def execute(self, *args, **kwargs):
        """执行 SQLAlchemy 语句，并将结果交给统一 SQL 日志处理器。"""
        started_at = time.perf_counter()
        result = super().execute(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        return log_sql_result(result, elapsed_ms)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=LoggingAsyncSession,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
    class_=LoggingSession,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """为一次 FastAPI 请求提供自动关闭的异步数据库会话。"""
    async with AsyncSessionLocal() as session:
        yield session
