from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserMapper(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    password: Mapped[str] = mapped_column(String(100), nullable=False)