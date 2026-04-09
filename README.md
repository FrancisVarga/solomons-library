# Solomon's Library

A [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server for embedding storage, semantic search, and book management. Built with [FastMCP](https://github.com/jlowin/fastmcp), it stores 1536-dimensional text embeddings in PostgreSQL/pgvector and exposes tools, resources, and prompts over HTTP.

## Features

- **Semantic search** — embed text via OpenAI (primary) or Gemini (fallback) and find similar content with cosine similarity
- **Book management** — add, list, and retrieve books with ISBN tracking
- **OpenAPI ingestion** — import any OpenAPI spec and describe how to mount it as an MCP sub-server
- **Background tasks** — embedding generation runs as a Docket task backed by Redis
- **7-layer middleware** — error handling, retry, rate limiting, caching, response limiting, timing, and structured logging
- **BM25 search transform** — full-text search across all registered tools

## Prerequisites

- Python 3.13+
- PostgreSQL with [pgvector](https://github.com/pgvector/pgvector) extension
- Redis
- [uv](https://docs.astral.sh/uv/) package manager
- An API key for [OpenAI](https://platform.openai.com/) and/or [Google Gemini](https://ai.google.dev/)

## Quick Start

```bash
# Clone the repository
git clone https://github.com/FrancisVarga/solomons-library.git
cd solomons-library

# Install dependencies
uv sync

# Configure environment variables (see Configuration below)
cp .env.example .env  # or create .env manually

# Run database migrations
uv run alembic upgrade head

# Start the server
uv run python -m solomons_library
```

The server starts on `http://0.0.0.0:8000` by default. A health check is available at `GET /health`.

## Configuration

Set the following environment variables (via `.env` file or shell):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string (e.g. `postgresql://user:pass@localhost/solomons`) |
| `OPENAI_API_KEY` | No* | `""` | OpenAI API key for text-embedding-3-small |
| `GEMINI_API_KEY` | No* | `""` | Google Gemini API key (fallback embedding provider) |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis URL for Docket task queue |
| `SERVER_HOST` | No | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | No | `8000` | Server port |
| `PROJECT_NAME` | No | `solomons-library` | Project name attached to embeddings |

\* At least one of `OPENAI_API_KEY` or `GEMINI_API_KEY` is required for embedding functionality.

## MCP Interface

### Tools

| Tool | Tags | Description |
|------|------|-------------|
| `embed_text` | embeddings, write | Embed text and store the vector in the database (runs as background task) |
| `search_embeddings` | embeddings, read | Search stored embeddings by semantic similarity |
| `add_book` | books, write | Add a new book to the library |
| `list_books` | books, read | List books in the library |
| `get_book` | books, read | Get a specific book by ID |
| `import_openapi_spec` | openapi, utility | Fetch and analyze an OpenAPI spec for MCP mounting |

### Resources

| URI | Description |
|-----|-------------|
| `library://stats` | Library statistics (book count, embedding count) |
| `library://books` | All books as JSON |
| `library://books/{id}` | A specific book by ID |
| `library://embeddings/recent` | 10 most recent embeddings |

### Prompts

| Prompt | Description |
|--------|-------------|
| `analyze_book` | Literary analysis prompt for a specific book (title + author) |
| `search_query` | Knowledge base search prompt with brief/detailed depth |
| `summarize_collection` | Summarize the entire library collection |

## Architecture

```
src/solomons_library/
  __main__.py          # Entry point
  server.py            # FastMCP instance, lifespan, registration
  config.py            # Settings from environment variables
  middleware.py         # 7-layer middleware stack
  db/
    base.py            # SQLAlchemy declarative base
    session.py         # Async/sync engine and session factories
  models/
    book.py            # Book ORM model
    embedding.py       # Embedding ORM model with Vector(1536) + HNSW index
  tools/
    books.py           # Book CRUD tools
    embed.py           # Embedding generation + semantic search
    openapi.py         # OpenAPI spec importer
  resources/
    __init__.py        # MCP resource definitions
  prompts/
    __init__.py        # MCP prompt templates
```

### Middleware Stack

Middleware executes outermost-first:

1. **ErrorHandling** — catches exceptions from all subsequent layers
2. **Retry** — auto-retry on `ConnectionError`, `TimeoutError`, `OSError` (max 2)
3. **RateLimit** — sliding window, 100 requests/minute
4. **ResponseCaching** — TTL-based caching for `list_books`, `get_book`, and resource reads
5. **ResponseLimiting** — truncates responses exceeding 500KB
6. **Timing** — tracks execution duration
7. **StructuredLogging** — records execution (innermost)

### Embedding Pipeline

Embedding generation uses a fallback chain:

1. **OpenAI** `text-embedding-3-small` (1536 dimensions) — primary
2. **Google Gemini** `gemini-embedding-exp-03-07` — fallback, zero-padded to 1536 dimensions

Vectors are stored in PostgreSQL using pgvector with an HNSW cosine index (`m=16`, `ef_construction=64`) for fast approximate nearest-neighbor search.

## Database Migrations

Managed with Alembic. The project includes 6 migrations covering:

- Books and embeddings tables
- `project_name` and `user` columns on embeddings
- Indexes on `project_name`, `user`, `created_at`
- HNSW index on the embedding vector column

```bash
# Apply all migrations
uv run alembic upgrade head

# Generate a new migration after model changes
uv run alembic revision --autogenerate -m "description"

# Check current migration state
uv run alembic current
```

## Development

```bash
# Install dependencies
uv sync

# Run the server in development
uv run python -m solomons_library
```

## License

See [LICENSE](LICENSE) for details.
