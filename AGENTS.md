<!-- Generated: 2026-04-10 | Updated: 2026-04-10 -->

# Solomon's Library

## Purpose
A FastMCP server providing embedding storage, semantic search, book management, and file upload processing over HTTP. Stores 1536-dimensional text embeddings in PostgreSQL/pgvector with HNSW cosine indexing. Exposes tools, resources, and prompts via the MCP protocol. Embedding generation uses OpenAI (primary) with Google Gemini fallback; background tasks run through a Redis-backed Docket queue.

## Key Files

| File | Description |
|------|-------------|
| `pyproject.toml` | Project metadata, dependencies (Python 3.13, FastMCP 3.2.2, SQLAlchemy, pgvector, etc.) |
| `compose.yml` | Docker Compose for PostgreSQL + pgvector and Redis services |
| `Dockerfile` | Container build for the MCP server |
| `alembic.ini` | Alembic migration configuration |
| `CLAUDE.md` | Project rules, stack overview, and dev commands for AI assistants |
| `README.md` | Human-facing project documentation |
| `.dockerignore` | Docker build exclusions |
| `.gitignore` | Git ignore patterns |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `src/` | Application source code (see `src/AGENTS.md`) |
| `alembic/` | Database migration framework and version scripts (see `alembic/AGENTS.md`) |
| `logs/` | Runtime log files (Loguru output, rotated at 10 MB) |
| `graphify-out/` | Knowledge graph output — read `GRAPH_REPORT.md` for architecture insights |

## For AI Agents

### Working In This Directory
- Always run `uv sync` after modifying `pyproject.toml`
- Start server with `uv run python -m solomons_library`
- Run migrations with `uv run alembic upgrade head`
- Generate migrations with `uv run alembic revision --autogenerate -m "description"`
- Read `graphify-out/GRAPH_REPORT.md` before answering architecture questions

### Architecture Flow
```
config.py → db/base + models → db/session.py → tools/resources/prompts → middleware.py → server.py → __main__ → mcp.run(http)
```

### God Nodes (most connected components)
1. `FastMCP Server Instance` (server.py) — 18 edges, central hub
2. `get_async_session_factory()` (db/session.py) — 12 edges, used by all tools/resources
3. `Book Model` / `Embedding Model` — core ORM entities
4. `_generate_embedding()` (tools/embed.py) — OpenAI→Gemini fallback router

### Testing Requirements
- No test suite yet — verify changes by running the server and hitting `/health`
- Lint with `ruff check`

### Common Patterns
- All tools accept optional `ctx: Context | None` for MCP logging/progress
- Write tools invalidate Redis caches after mutations
- Background tasks use `@tool(task=True)` for Docket queue integration
- All DB access uses `get_async_session_factory()` with async context managers
- Models use SQLAlchemy 2.0 `Mapped[]` / `mapped_column()` style

## Dependencies

### External
- `fastmcp[code-mode,tasks]` 3.2.2 — MCP server framework with Docket task queue
- `sqlalchemy[asyncio]` 2.0+ — Async ORM
- `pgvector` — PostgreSQL vector similarity extension
- `alembic` — Database migrations
- `openai` — Primary embedding provider
- `google-genai` — Fallback embedding provider (Gemini)
- `redis` / `py-key-value-aio[redis]` — Caching and task queue backend
- `loguru` — Structured logging
- `httpx` — Async HTTP client (OpenAPI import)
- `pymupdf`, `python-docx`, `beautifulsoup4`, `pyyaml` — File parsers

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
