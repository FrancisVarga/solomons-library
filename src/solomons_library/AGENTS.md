<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-10 | Updated: 2026-04-10 -->

# solomons_library

## Purpose
Main application package for Solomon's Library. Contains the FastMCP server, configuration, database layer, ORM models, MCP tools/resources/prompts, middleware stack, caching, and logging infrastructure.

## Key Files

| File | Description |
|------|-------------|
| `server.py` | FastMCP instance creation, lifespan management, tool/resource/prompt registration, `/health` route |
| `config.py` | Frozen `Settings` dataclass loaded from environment variables via `python-dotenv` |
| `middleware.py` | 7-layer middleware stack: error handling → retry → rate limiting → Redis cache → response limiting → timing → logging |
| `cache.py` | Redis-backed caching: async helpers, `@cached` decorator, `RedisCachingMiddleware` for MCP protocol-level caching |
| `log_setup.py` | Loguru configuration — routes stdlib logging through Loguru, file rotation, silences noisy internals |
| `asgi.py` | ASGI entrypoint for external servers (Granian): exposes `app = mcp.http_app()` |
| `__main__.py` | CLI entrypoint: `python -m solomons_library` → calls `server.main()` |
| `__init__.py` | Package marker (empty) |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `db/` | Database engine, session factories, and declarative base (see `db/AGENTS.md`) |
| `models/` | SQLAlchemy ORM models: Book, Embedding, FileUpload (see `models/AGENTS.md`) |
| `tools/` | MCP tool implementations: books, embeddings, uploads, OpenAPI, skills (see `tools/AGENTS.md`) |
| `resources/` | MCP resource endpoints: library stats, books, embeddings, uploads (see `resources/AGENTS.md`) |
| `prompts/` | MCP prompt templates: analyze_book, search_query, summarize_collection (see `prompts/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- **Entry point flow**: `config.py` → `db/` → `models/` → `tools/` + `resources/` + `prompts/` → `middleware.py` → `server.py` → `__main__.py`
- `server.py` is the god node (18 edges) — it wires everything together
- All tools are registered explicitly in `server.py` via `mcp.add_tool()`
- The lifespan context manager in `server.py` initializes the async DB engine and Redis connection
- Environment variables: `DATABASE_URL` (required), `OPENAI_API_KEY`, `GEMINI_API_KEY`, `REDIS_URL`, `SERVER_HOST`, `SERVER_PORT`, `PROJECT_NAME`

### Testing Requirements
- Run server: `uv run python -m solomons_library`
- Health check: `GET /health` returns `"OK"`
- No test suite yet — verify by running and invoking MCP tools

### Common Patterns
- Tools accept `ctx: Context | None = None` for MCP logging and progress reporting
- Write operations invalidate Redis caches via `cache_invalidate("sl:*")`
- Background tasks use `@tool(task=True)` which routes through Docket/Redis
- All async DB access: `async_session = get_async_session_factory(); async with async_session() as session:`
- Embedding generation: `_generate_embedding()` tries OpenAI first, falls back to Gemini

## Dependencies

### External
- `fastmcp[code-mode,tasks]` — MCP framework + Docket task queue
- `sqlalchemy[asyncio]` — Async ORM with asyncpg driver
- `redis.asyncio` — Async Redis client for caching
- `loguru` — Structured logging
- `openai` / `google-genai` — Embedding providers

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
