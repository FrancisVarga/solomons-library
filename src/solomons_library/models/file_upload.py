from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from solomons_library.db.base import Base


class UploadStatus(str, enum.Enum):
    """Lifecycle states for a file upload."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileUpload(Base):
    __tablename__ = "file_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(200))
    file_size: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default=UploadStatus.PENDING.value)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(default=0)
    project_name: Mapped[str | None] = mapped_column(String(200), index=True)
    user: Mapped[str | None] = mapped_column(String(200), index=True)
    agent: Mapped[str | None] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
