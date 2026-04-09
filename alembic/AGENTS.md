<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-10 | Updated: 2026-04-10 -->

# alembic

## Purpose
Database migration framework using Alembic. Manages schema evolution for the PostgreSQL + pgvector database, including Book, Embedding, and FileUpload tables.

## Key Files

| File | Description |
|------|-------------|
| `env.py` | Migration environment — loads `.env`, normalizes DB URL to `postgresql+psycopg://`, imports all models for autogenerate |
| `script.py.mako` | Template for new migration files |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `versions/` | Individual migration scripts (see `versions/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Generate new migrations: `uv run alembic revision --autogenerate -m "description"`
- Apply migrations: `uv run alembic upgrade head`
- `env.py` rewrites `DATABASE_URL` to use the sync `psycopg` driver (Alembic requires sync)
- All models must be imported in `solomons_library/models/__init__.py` for autogenerate to detect them
- Never edit `env.py` unless changing the migration strategy

### Testing Requirements
- Always run `uv run alembic upgrade head` after creating a new migration to verify it applies cleanly
- Check for `down_revision` chain integrity when adding migrations

### Common Patterns
- Import `Base` from `solomons_library.db.base` for `target_metadata`
- Import all models via `solomons_library.models` (side-effect import for metadata registration)

## Dependencies

### Internal
- `src/solomons_library/db/base.py` — `Base` (DeclarativeBase) for `target_metadata`
- `src/solomons_library/models/` — All ORM models registered on Base.metadata

### External
- `alembic` — Migration framework
- `sqlalchemy` — ORM (sync engine for migrations)
- `psycopg` — Sync PostgreSQL driver

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
