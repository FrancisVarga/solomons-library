<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-10 | Updated: 2026-04-10 -->

# models

## Purpose
SQLAlchemy ORM models representing the three core database entities: books, vector embeddings, and file uploads. All models inherit from `db.base.Base` and use the SQLAlchemy 2.0 `Mapped[]` / `mapped_column()` annotation style.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Re-exports `Book`, `Embedding`, `FileUpload`, `UploadStatus` — also triggers metadata registration for Alembic |
| `book.py` | `Book` model: id, title, author, isbn (unique), created_at |
| `embedding.py` | `Embedding` model: id, text, source, model, project_name, user, agent, embedding (Vector(1536) with HNSW cosine index), created_at |
| `file_upload.py` | `FileUpload` model: id, filename, file_path, mime_type, file_size, status, error_message, chunk_count, project_name, user, agent, created_at, updated_at |

## For AI Agents

### Working In This Directory
- All new models MUST be imported in `__init__.py` so Alembic autogenerate detects them
- After adding/modifying models, generate a migration: `uv run alembic revision --autogenerate -m "description"`
- The `Embedding` model uses `pgvector.sqlalchemy.Vector(1536)` — all vectors are 1536 dimensions (OpenAI standard; Gemini vectors are zero-padded to match)
- The HNSW index on `Embedding.embedding` uses `vector_cosine_ops` for cosine distance search
- `FileUpload.status` uses string values from `UploadStatus` enum: pending, processing, completed, failed

### Testing Requirements
- After model changes, verify the migration generates correctly and applies cleanly
- Check that existing tools/resources still work with the updated schema

### Common Patterns
- `server_default=func.now()` for timestamp columns (DB-side default)
- `Mapped[str | None]` for nullable columns
- `mapped_column(String(N))` with explicit length limits
- Indexes on `project_name`, `user`, `agent`, `created_at` for filtered queries

## Dependencies

### Internal
- `solomons_library/db/base.py` — `Base` (DeclarativeBase)

### External
- `sqlalchemy` — ORM, column types, mapped_column
- `pgvector.sqlalchemy` — `Vector` type for embedding column

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
