"""Solomon's Library — FastMCP Server.

A knowledge library MCP server with embedding storage, book management,
and semantic search capabilities.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.client.sampling.handlers.openai import OpenAISamplingHandler
from fastmcp.server.providers.skills import ClaudeSkillsProvider
from fastmcp.server.transforms.search import BM25SearchTransform
from loguru import logger
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from solomons_library.config import settings
from solomons_library.db import get_async_engine
from solomons_library.log_setup import setup_logging
from solomons_library.middleware import get_middleware

# Set Docket URL for background task backend (Redis)
os.environ.setdefault("FASTMCP_DOCKET_URL", settings.REDIS_URL)

# ---------------------------------------------------------------------------
# Lifespan: manage async DB engine
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(server: FastMCP):  # noqa: ARG001
    setup_logging()
    logger.info("Solomon's Library starting up")
    engine = get_async_engine()
    try:
        yield {"db_engine": engine}
    finally:
        await engine.dispose()
        logger.info("Solomon's Library shut down")


# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Solomon's Library",
    instructions=(
        "A knowledge library server. "
        "Use embed_text to store knowledge as vector embeddings, "
        "search_embeddings to find similar content, "
        "and manage books with add_book / list_books / get_book. "
        "Browse library://stats for an overview."
    ),
    lifespan=lifespan,
    tasks=True,
    transforms=[
        BM25SearchTransform(max_results=5),
    ],
    sampling_handler=OpenAISamplingHandler(default_model="gpt-4o-mini"),
    sampling_handler_behavior="fallback",
    middleware=get_middleware(),
)

# ---------------------------------------------------------------------------
# Skills provider
# ---------------------------------------------------------------------------

try:
    mcp.add_provider(ClaudeSkillsProvider())
except Exception as e:
    logger.warning(f"Could not load Claude skills provider: {e}")

# ---------------------------------------------------------------------------
# Register tools
# ---------------------------------------------------------------------------

from solomons_library.tools.books import add_book, get_book, list_books  # noqa: E402
from solomons_library.tools.embed import embed_text, search_embeddings  # noqa: E402
from solomons_library.tools.openapi import import_openapi_spec  # noqa: E402

for t in [add_book, get_book, list_books, embed_text, search_embeddings, import_openapi_spec]:
    mcp.add_tool(t)

# ---------------------------------------------------------------------------
# Register resources
# ---------------------------------------------------------------------------

from solomons_library.resources import ALL_RESOURCES  # noqa: E402

for res_fn in ALL_RESOURCES:
    mcp.add_resource(res_fn)

# ---------------------------------------------------------------------------
# Register prompts
# ---------------------------------------------------------------------------

from solomons_library.prompts import ALL_PROMPTS  # noqa: E402

for prompt_fn in ALL_PROMPTS:
    mcp.add_prompt(prompt_fn)

# ---------------------------------------------------------------------------
# Custom routes (HTTP transport only)
# ---------------------------------------------------------------------------

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:  # noqa: ARG001
    return PlainTextResponse("OK")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run(transport="http", host=settings.SERVER_HOST, port=settings.SERVER_PORT)


if __name__ == "__main__":
    main()
