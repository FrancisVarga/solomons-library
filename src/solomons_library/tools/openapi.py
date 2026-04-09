from __future__ import annotations

import httpx
from fastmcp import Context
from fastmcp.tools import tool


@tool(tags={"openapi", "utility"}, annotations={"readOnlyHint": True})
async def import_openapi_spec(spec_url: str, name: str = "imported-api", ctx: Context | None = None) -> dict:
    """Import an OpenAPI spec and describe how to mount it as an MCP sub-server.

    Fetches the OpenAPI specification from the given URL and returns
    information about the endpoints it contains. Use FastMCP.from_openapi()
    to mount this spec as a full MCP server.
    """
    if ctx:
        await ctx.info(f"Fetching OpenAPI spec from {spec_url}")

    async with httpx.AsyncClient() as client:
        resp = await client.get(spec_url)
        resp.raise_for_status()
        spec = resp.json()

    info = spec.get("info", {})
    paths = spec.get("paths", {})

    endpoints = []
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                endpoints.append({
                    "method": method.upper(),
                    "path": path,
                    "summary": details.get("summary", ""),
                    "operation_id": details.get("operationId", ""),
                })

    if ctx:
        await ctx.info(f"Found {len(endpoints)} endpoints in {info.get('title', name)}")

    return {
        "name": name,
        "title": info.get("title", ""),
        "version": info.get("version", ""),
        "endpoint_count": len(endpoints),
        "endpoints": endpoints[:20],
        "usage": f"from fastmcp import FastMCP; import httpx; mcp = FastMCP.from_openapi(openapi_spec=spec, client=httpx.AsyncClient(base_url='BASE_URL'), name='{name}')",
    }
