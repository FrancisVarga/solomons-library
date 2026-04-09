"""FastMCP middleware configuration for Solomon's Library.

Middleware executes in order: first added = outermost layer.
Order: error handling → retry → rate limiting → response limiting → timing → logging

Note: Response caching is handled by the Redis-backed cache module
(solomons_library.cache), not by middleware.
"""

from __future__ import annotations

from fastmcp.server.middleware import Middleware
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware, RetryMiddleware
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
from fastmcp.server.middleware.rate_limiting import SlidingWindowRateLimitingMiddleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware

from solomons_library.cache import RedisCachingMiddleware


def get_middleware() -> list[Middleware]:
    """Build the middleware stack in correct order (outermost first)."""
    return [
        # 1. Error handling — catches exceptions from all subsequent middleware
        ErrorHandlingMiddleware(
            include_traceback=False,
            transform_errors=True,
        ),
        # 2. Retry — auto-retry on transient failures
        RetryMiddleware(
            max_retries=2,
            retry_exceptions=(ConnectionError, TimeoutError, OSError),
        ),
        # 3. Rate limiting — reject excess requests early
        SlidingWindowRateLimitingMiddleware(
            max_requests=100,
            window_minutes=1,
        ),
        # 4. Redis caching — serve cached responses for read-only tools and resources
        RedisCachingMiddleware(
            cached_tools={"list_books", "get_book", "search_embeddings",
                          "get_upload_status", "list_uploads"},
            tool_ttl=30,
            resource_ttl=30,
        ),
        # 5. Response limiting — truncate oversized responses
        ResponseLimitingMiddleware(
            max_size=500_000,
            truncation_suffix="\n\n[Response truncated...]",
        ),
        # 6. Timing — track execution duration
        TimingMiddleware(),
        # 7. Logging — record actual execution (innermost)
        StructuredLoggingMiddleware(
            include_payloads=False,
        ),
    ]
