from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import PG_DATABASE_URL


engine = create_async_engine(PG_DATABASE_URL, echo=True)

SessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)
class Base(DeclarativeBase):
    pass

async def get_db():
    async with SessionLocal() as session:
        yield session