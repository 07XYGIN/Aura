from datetime import date
import uuid

from sqlalchemy import String, Date, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "login_user"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()")
    )

    user_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True
    )

    psd: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    create_at: Mapped[date] = mapped_column(
        Date,
        server_default=text("(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')")
    )

    code: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
