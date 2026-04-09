from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from solomons_library.db.base import Base


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        Index("ix_embeddings_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(500))
    model: Mapped[str] = mapped_column(String(100))
    project_name: Mapped[str | None] = mapped_column(String(200), index=True)
    user: Mapped[str | None] = mapped_column(String(200), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
