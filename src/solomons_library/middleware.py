"""FastMCP middleware configuration for Solomon's Library.

Middleware executes in order: first added = outermost layer.
Order: error handling → rate limiting → caching → response limiting → timing → logging
"""

from __future__ import annotations

from fastmcp.server.middleware import Middleware
from fastmcp.server.middleware.caching import (
    CallToolSettings,
    ListToolsSettings,
    ReadResourceSettings,
    ResponseCachingMiddleware,
)
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware, RetryMiddleware
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
from fastmcp.server.middleware.rate_limiting import SlidingWindowRateLimitingMiddleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware


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
        # 4. Response caching — avoid redundant computation
        ResponseCachingMiddleware(
            list_tools_settings=ListToolsSettings(ttl=60),
            call_tool_settings=CallToolSettings(
                enabled=True,
                included_tools=["list_books", "get_book"],
                ttl=30,
            ),
            read_resource_settings=ReadResourceSettings(ttl=30),
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
