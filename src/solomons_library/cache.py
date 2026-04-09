"""Redis-backed caching for Solomon's Library.

Provides:
- Async cache helpers (``cache_get``, ``cache_set``, ``cache_invalidate``)
- A ``@cached`` decorator for per-function caching
- ``RedisCachingMiddleware`` — a FastMCP middleware that caches all
  read-only tool calls and resource reads at the MCP protocol level

Note: Uses pickle for serialization of cache values.  This is safe because
the cache only stores data that this application itself wrote — no untrusted
input is ever deserialized.
"""

from __future__ import annotations

import functools
import hashlib
import json
import pickle
from typing import Any, Callable

import mcp.types
import redis.asyncio as aioredis
from fastmcp.server.middleware.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult
from loguru import logger

from solomons_library.config import settings

# ---------------------------------------------------------------------------
# Module-level connection
# ---------------------------------------------------------------------------

_redis: aioredis.Redis | None = None

KEY_PREFIX = "sl:"


async def get_redis() -> aioredis.Redis | None:
    """Return a shared async Redis connection, or *None* if unavailable."""
    global _redis
    if _redis is not None:
        try:
            await _redis.ping()  # type: ignore[misc]
            return _redis
        except Exception:
            _redis = None

    try:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            socket_connect_timeout=2,
        )
        await _redis.ping()  # type: ignore[misc]
        logger.debug("Redis cache connected")
        return _redis
    except Exception as exc:
        logger.warning(f"Redis cache unavailable, running without cache: {exc}")
        _redis = None
        return None


async def close_redis() -> None:
    """Shut down the Redis connection pool."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _make_key(*parts: str) -> str:
    """Build a namespaced cache key."""
    return KEY_PREFIX + ":".join(parts)


def _hash_args(*args: Any) -> str:
    """Deterministic hash of arguments for cache key generation."""
    raw = json.dumps(args, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def cache_get(key: str) -> Any | None:
    """Fetch a value from Redis cache.  Returns *None* on miss or error."""
    r = await get_redis()
    if r is None:
        return None
    try:
        data = await r.get(key)
        if data is None:
            return None
        return pickle.loads(data)  # noqa: S301 — only deserializes self-written data
    except Exception as exc:
        logger.debug(f"Cache get failed for {key}: {exc}")
        return None


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    """Store a value in Redis cache with a TTL (seconds)."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.set(key, pickle.dumps(value), ex=ttl)
    except Exception as exc:
        logger.debug(f"Cache set failed for {key}: {exc}")


async def cache_invalidate(*patterns: str) -> None:
    """Delete all keys matching the given glob patterns."""
    r = await get_redis()
    if r is None:
        return
    for pattern in patterns:
        try:
            cursor = None
            while cursor != 0:
                cursor, keys = await r.scan(cursor=cursor or 0, match=pattern, count=100)
                if keys:
                    await r.delete(*keys)
        except Exception as exc:
            logger.debug(f"Cache invalidation failed for {pattern}: {exc}")


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def cached(namespace: str, ttl: int = 60, key_args: tuple[int, ...] | None = None):
    """Decorator that caches an async function's return value in Redis.

    Parameters
    ----------
    namespace:
        Cache namespace (e.g. ``"embed"``, ``"book"``).  Used as part of the
        Redis key: ``sl:<namespace>:<hash>``.
    ttl:
        Time-to-live in seconds.
    key_args:
        Positional indices of the arguments to include in the cache key.
        If *None*, all positional args are used.  Keyword-only args named
        ``ctx`` are always excluded.
    """

    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            # Build cache key from selected args
            if key_args is not None:
                hash_source = tuple(args[i] for i in key_args if i < len(args))
            else:
                hash_source = args
            # Include relevant kwargs (exclude ctx)
            kw_for_key = {k: v for k, v in kwargs.items() if k != "ctx"}
            cache_key = _make_key(namespace, _hash_args(*hash_source, kw_for_key))

            # Try cache
            hit = await cache_get(cache_key)
            if hit is not None:
                logger.debug(f"Cache hit: {namespace}")
                return hit

            # Miss — call the function
            result = await fn(*args, **kwargs)

            # Store result
            await cache_set(cache_key, result, ttl=ttl)
            return result

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# FastMCP Middleware
# ---------------------------------------------------------------------------


class RedisCachingMiddleware(Middleware):
    """FastMCP middleware that caches read-only tool and resource responses in Redis.

    Only tools listed in ``cached_tools`` are cached.  Write operations must
    never be cached.  Resource reads are cached by URI.

    Falls back gracefully when Redis is unavailable — requests pass through
    uncached.
    """

    def __init__(
        self,
        cached_tools: set[str] | None = None,
        tool_ttl: int = 30,
        resource_ttl: int = 30,
    ):
        self._cached_tools = cached_tools or {
            "list_books", "get_book", "search_embeddings",
            "get_upload_status", "list_uploads",
        }
        self._tool_ttl = tool_ttl
        self._resource_ttl = resource_ttl

    async def on_call_tool(
        self,
        context: MiddlewareContext[mcp.types.CallToolRequestParams],
        call_next: CallNext[mcp.types.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        tool_name = context.message.name
        if tool_name not in self._cached_tools:
            return await call_next(context)

        args_str = json.dumps(context.message.arguments or {}, sort_keys=True, default=str)
        cache_key = _make_key("mw", "tool", hashlib.sha256(
            f"{tool_name}:{args_str}".encode()
        ).hexdigest()[:16])

        hit = await cache_get(cache_key)
        if hit is not None:
            logger.debug(f"Middleware cache hit: {tool_name}")
            return hit

        result = await call_next(context)
        await cache_set(cache_key, result, ttl=self._tool_ttl)
        return result

    async def on_read_resource(
        self,
        context: MiddlewareContext[mcp.types.ReadResourceRequestParams],
        call_next: CallNext,
    ) -> Any:
        uri = str(context.message.uri)
        cache_key = _make_key("mw", "res", hashlib.sha256(uri.encode()).hexdigest()[:16])

        hit = await cache_get(cache_key)
        if hit is not None:
            logger.debug(f"Middleware cache hit: {uri}")
            return hit

        result = await call_next(context)
        await cache_set(cache_key, result, ttl=self._resource_ttl)
        return result
