---
description: "This skill should be used when creating a new MCP tool for Solomon's Library, adding a tool function, scaffolding a tool module, or implementing CRUD operations as MCP tools."
version: 0.1.0
tags:
  - fastmcp
  - tools
  - mcp
  - solomon
---

# Solomon's Library — MCP Tool Pattern

Tools live in `src/solomons_library/tools/<module>.py`. After creation, register in `server.py`.

## Tool Template

### Read-Only Tool (with manual caching)

```python
from fastmcp import Context
from fastmcp.tools import tool
from sqlalchemy import select

from solomons_library.cache import cache_get, cache_set, _make_key, _hash_args
from solomons_library.db import get_async_session_factory
from solomons_library.models import YourModel


@tool(tags={"your_domain", "read"}, annotations={"readOnlyHint": True})
async def get_thing(thing_id: int, ctx: Context | None = None) -> dict:
    """Get a specific thing by its ID."""
    if ctx:
        await ctx.debug(f"Fetching thing {thing_id}")

    cache_key = _make_key("thing", _hash_args("get", thing_id))
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit

    async_session = get_async_session_factory()
    async with async_session() as session:
        thing = await session.get(YourModel, thing_id)
        if not thing:
            return {"error": f"Thing with ID {thing_id} not found"}
        data = {"id": thing.id, "name": thing.name}

    await cache_set(cache_key, data, ttl=30)
    return data
```

### Write Tool (with cache invalidation)

```python
from solomons_library.cache import cache_invalidate, cached


@tool(tags={"your_domain", "write"})
async def add_thing(name: str, ctx: Context | None = None) -> dict:
    """Add a new thing to the library."""
    if ctx:
        await ctx.info(f"Adding thing: {name}")

    async_session = get_async_session_factory()
    async with async_session() as session:
        thing = YourModel(name=name)
        session.add(thing)
        await session.commit()
        await session.refresh(thing)

        if ctx:
            await ctx.info(f"Thing added with ID {thing.id}")

        # Invalidate relevant caches
        await cache_invalidate("sl:thing:*", "sl:res:*")

        return {"id": thing.id, "name": thing.name}
```

## Conventions

### Decorator Arguments

| Argument | Usage |
|----------|-------|
| `tags={"domain", "read"}` | Two-level: domain category + read/write |
| `annotations={"readOnlyHint": True}` | Only on read-only tools |
| `task=True` | Only for background tasks (Docket) |

### Parameters

- **Always** end with `ctx: Context | None = None`
- Use `str | None = None` for optional params (Python 3.13 union syntax)
- Required params have no default

### Return Values

- Return `dict` for single items, `list[dict]` for collections
- Return `{"error": "message"}` on failure — **never raise exceptions**
- Always include `id` in returned dicts

### Logging via Context

```python
if ctx:
    await ctx.info("Important action")      # User-visible info
    await ctx.debug("Internal detail")      # Debug-level
    await ctx.error("Something went wrong") # Error-level
```

### Caching

- **Read tools**: Use manual `cache_get`/`cache_set` with `_make_key` and `_hash_args`
- **Write tools**: Call `cache_invalidate("sl:domain:*", "sl:res:*")` after mutations
- **Expensive compute**: Use `@cached(namespace="domain", ttl=3600)` decorator
- Standard TTL: 30s for reads, 300s for search results, 3600s for embeddings

## Registration Checklist

After creating a tool, you must:

1. **Import** in `src/solomons_library/server.py`:
   ```python
   from solomons_library.tools.your_module import your_tool  # noqa: E402
   ```

2. **Register** in the tool loop:
   ```python
   for t in [
       # ... existing tools ...
       your_tool,
   ]:
       mcp.add_tool(t)
   ```

3. **Export** from `tools/__init__.py` if the module has a public API

## See Also

- `solomon-background-task` — For tools with `task=True`
- `solomon-model-migration` — For creating the model a tool operates on
