<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-10 | Updated: 2026-04-10 -->

# db

## Purpose
Database layer providing the SQLAlchemy declarative base, async/sync engine factories, and session factories. This is the foundation that all models, tools, and resources build upon.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Re-exports `Base`, `get_async_engine`, `get_async_session_factory`, `get_engine`, `get_session_factory` |
| `base.py` | `Base` — SQLAlchemy `DeclarativeBase` subclass, shared by all ORM models |
| `session.py` | Engine and session factories: async (asyncpg) for runtime, sync (psycopg) for Alembic |

## For AI Agents

### Working In This Directory
- `Base` is the single declarative base — all models inherit from it
- `get_async_engine()` uses `postgresql+asyncpg://` (rewritten from `DATABASE_URL` by `config.py`)
- `get_engine()` uses `postgresql+psycopg://` (sync, for Alembic only)
- `get_async_session_factory()` returns an `async_sessionmaker` bound to the async engine with `expire_on_commit=False`
- `get_async_session_factory()` is the second most connected node in the codebase (12 edges) — used by every tool and resource

### Testing Requirements
- Changes here affect the entire application — verify by running the server
- Ensure both async (runtime) and sync (Alembic) paths still work after modifications

### Common Patterns
- URL normalization: `re.sub(r"^postgresql(\+\w+)?://", "postgresql+asyncpg://", ...)` for async
- Session usage: `async_session = get_async_session_factory(); async with async_session() as session:`
- Never create raw engines in tools/resources — always use the factories

## Dependencies

### Internal
- `solomons_library/config.py` — `settings.DATABASE_URL` and `settings.async_database_url`

### External
- `sqlalchemy[asyncio]` — ORM core, async engine, async sessionmaker
- `asyncpg` — Async PostgreSQL driver (runtime)
- `psycopg` — Sync PostgreSQL driver (Alembic migrations)

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
