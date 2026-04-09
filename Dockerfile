# ============================================================================
# Stage 1: Build dependencies
# ============================================================================
FROM ghcr.io/astral-sh/uv:0.7-python3.13-bookworm-slim AS builder

WORKDIR /app

# Enable uv cache and bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first (cached unless pyproject.toml/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Install the project itself
COPY README.md ./
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ============================================================================
# Stage 2: Production runtime
# ============================================================================
FROM python:3.13-slim-bookworm AS runtime

WORKDIR /app

# Install only the minimal runtime C libs needed by asyncpg / psycopg
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Run as non-root
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source and alembic config
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

# Ensure logs directory exists
RUN mkdir -p /app/logs && chown -R app:app /app

# Put the venv on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

# Run with Granian for high concurrency
# - workers: 4 OS processes (bypasses GIL)
# - runtime-threads: 2 async runtime threads per worker
# - backpressure: 64 pending requests per worker before rejecting
# - http: HTTP/1 (MCP clients don't use HTTP/2 yet)
CMD [ \
    "granian", \
    "solomons_library.asgi:app", \
    "--interface", "asgi", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "4", \
    "--runtime-threads", "2", \
    "--backpressure", "64", \
    "--http", "1" \
]
