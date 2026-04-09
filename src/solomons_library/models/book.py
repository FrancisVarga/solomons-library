from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from solomons_library.db.base import Base


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str] = mapped_column(String(300))
    isbn: Mapped[str | None] = mapped_column(String(13), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
