"""ASGI entrypoint for running Solomon's Library with an external server (Granian)."""

from solomons_library.server import mcp

app = mcp.http_app(transport="http")
