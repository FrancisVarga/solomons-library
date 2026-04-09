---
description: "This skill should be used when creating a SQLAlchemy model, adding pgvector/HNSW columns, generating an Alembic migration, or modifying the database schema in Solomon's Library."
version: 0.1.0
tags:
  - sqlalchemy
  - alembic
  - pgvector
  - orm
  - database
  - solomon
---

# Solomon's Library — Model & Migration Pattern

Models live in `src/solomons_library/models/`. Export from `__init__.py`, then generate an Alembic migration.

## Model Template

### Standard Model

Create in `src/solomons_library/models/your_model.py`:

```python
from datetime import datetime

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from solomons_library.db.base import Base


class YourModel(Base):
    __tablename__ = "your_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
```

### Model with Vector Column (pgvector)

```python
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from solomons_library.db.base import Base


class YourVectorModel(Base):
    __tablename__ = "your_vectors"
    __table_args__ = (
        Index(
            "ix_your_vectors_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
```

### Model with Status Enum

```python
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from solomons_library.db.base import Base


class YourStatus(str, enum.Enum):
    """Lifecycle states."""
    PENDING = "pending"
    ACTIVE = "active"
    ARCHIVED = "archived"


class YourModel(Base):
    __tablename__ = "your_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default=YourStatus.PENDING.value)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
```

## Column Conventions

| Type | SQLAlchemy | Python Type |
|------|-----------|-------------|
| Short string | `String(N)` | `Mapped[str]` |
| Long text | `Text` | `Mapped[str]` |
| Optional string | `String(N), nullable=True` | `Mapped[str \| None]` |
| Integer | (implicit) | `Mapped[int]` |
| Timestamp (create) | `server_default=func.now()` | `Mapped[datetime]` |
| Timestamp (update) | `server_default=func.now(), onupdate=func.now()` | `Mapped[datetime]` |
| Vector (1536-dim) | `Vector(1536)` from pgvector | `Mapped[list[float]]` |
| Enum as string | `String(20), default=Enum.VALUE.value` | `Mapped[str]` |

## Multi-Tenancy Columns

Always add these for data isolation when the model stores user-facing data:

```python
project_name: Mapped[str | None] = mapped_column(String(200), index=True)
user: Mapped[str | None] = mapped_column(String(200), index=True)
agent: Mapped[str | None] = mapped_column(String(200), index=True)
```

## Registration Checklist

After creating a model:

1. **Export** from `src/solomons_library/models/__init__.py`:
   ```python
   from solomons_library.models.your_model import YourModel, YourStatus

   __all__ = ["Book", "Embedding", "FileUpload", "UploadStatus", "YourModel", "YourStatus"]
   ```

2. **Import in Alembic env** — Models are auto-detected via `Base.metadata` as long as they're imported in `models/__init__.py`

3. **Generate migration**:
   ```bash
   uv run alembic revision --autogenerate -m "add your_table"
   ```

4. **Review the migration** — Check for:
   - Correct `CREATE EXTENSION IF NOT EXISTS vector` if using pgvector
   - HNSW index creation via raw SQL (autogenerate may not handle it)
   - Proper `upgrade()` and `downgrade()` functions

5. **Run migration**:
   ```bash
   uv run alembic upgrade head
   ```

## Alembic Migration Notes

### pgvector Extension

If your migration adds the first vector column, include:
```python
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # ... create table ...
```

### HNSW Index (manual)

Autogenerate often doesn't handle HNSW indexes correctly. Add manually:
```python
def upgrade() -> None:
    # ... after table creation ...
    op.execute(
        "CREATE INDEX ix_your_vectors_embedding_hnsw ON your_vectors "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

def downgrade() -> None:
    op.drop_index("ix_your_vectors_embedding_hnsw")
    # ... drop table ...
```

### env.py Configuration

The project's `alembic/env.py` normalizes `DATABASE_URL` to sync `postgresql+psycopg://` for migrations. No changes needed unless adding a new database.

## Anti-patterns

| Wrong | Correct | Reason |
|-------|---------|--------|
| `Column(String(200))` | `mapped_column(String(200))` | Legacy API; inconsistent with project style |
| `default=datetime.utcnow` | `server_default=func.now()` | Python-side default skips timezone and is not async-safe |
| Trust autogenerate for HNSW | Always add HNSW index manually in migration | Alembic autogenerate does not render `postgresql_using` indexes correctly |
| `onupdate=func.now()` for Docket tasks | Use PostgreSQL trigger for server-side `updated_at` | `onupdate` only fires when the ORM session performs the UPDATE |

## See Also

- `solomon-mcp-tool` — For creating tools that operate on the model
- `solomon-resource-prompt` — For exposing model data as MCP resources
