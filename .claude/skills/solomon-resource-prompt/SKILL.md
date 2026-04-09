---
description: "This skill should be used when creating a new MCP resource or prompt for Solomon's Library, adding a library:// URI, exposing data as a resource, or creating prompt templates."
version: 0.1.0
tags:
  - fastmcp
  - resources
  - prompts
  - mcp
  - solomon
---

# Solomon's Library — Resource & Prompt Pattern

Resources and prompts live in `src/solomons_library/resources/__init__.py` and `prompts/__init__.py`. For interactive tools (write/mutate), use `solomon-mcp-tool` instead.

## Resource Template

Add to `src/solomons_library/resources/__init__.py`.

Required imports (add to top if not present):
```python
import json
from fastmcp import Context
from fastmcp.resources import resource
from sqlalchemy import select
from solomons_library.cache import cache_get, cache_set, _make_key, _hash_args
from solomons_library.db import get_async_session_factory
from solomons_library.models import YourModel
```

### Static Resource (no parameters)

```python
@resource("library://your-domain", description="Description for clients", mime_type="application/json")
async def get_your_data(ctx: Context | None = None) -> str:
    """Docstring for the resource."""
    if ctx:
        await ctx.debug("Fetching your data")

    cache_key = _make_key("res", "your_data")
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit

    async_session = get_async_session_factory()
    async with async_session() as session:
        result = await session.execute(select(YourModel))
        items = result.scalars().all()
        data = json.dumps([
            {"id": i.id, "name": i.name}
            for i in items
        ])

    await cache_set(cache_key, data, ttl=30)
    return data
```

### Parameterized Resource (with URI template)

```python
@resource("library://your-domain/{item_id}", description="A specific item by ID", mime_type="application/json")
async def get_your_item(item_id: str, ctx: Context | None = None) -> str:
    """Returns a single item by its ID."""
    if ctx:
        await ctx.debug(f"Fetching item {item_id}")

    cache_key = _make_key("res", _hash_args("your_item", item_id))
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit

    try:
        pk = int(item_id)
    except ValueError:
        return json.dumps({"error": f"Invalid ID: {item_id!r}"})

    async_session = get_async_session_factory()
    async with async_session() as session:
        item = await session.get(YourModel, pk)
        if not item:
            return json.dumps({"error": f"Item {item_id} not found"})
        data = json.dumps({"id": item.id, "name": item.name})

    await cache_set(cache_key, data, ttl=30)
    return data
```

## Resource Conventions

| Convention | Details |
|-----------|---------|
| Return type | Always `str` (JSON-serialized via `json.dumps`) |
| URI format | `library://category` or `library://category/{param}` |
| Parameters | URI template params are `str` — cast internally (e.g., `int(item_id)`) |
| Caching | Always cache with TTL 30s using `_make_key`/`_hash_args` |
| Error format | Return `json.dumps({"error": "message"})` — never raise |
| MIME type | Always `"application/json"` |
| Imports needed | `json`, `resource` from `fastmcp.resources`, cache helpers, models |

## Resource Registration

After adding a resource function, add it to `ALL_RESOURCES` at the bottom of the file:

```python
ALL_RESOURCES = [
    get_library_stats, get_all_books, get_book_by_id,
    get_recent_embeddings, get_recent_uploads,
    get_your_data,  # <-- add here
]
```

Resources are auto-registered in `server.py` via the loop:
```python
for res_fn in ALL_RESOURCES:
    mcp.add_resource(res_fn)
```

---

## Prompt Template

Add to `src/solomons_library/prompts/__init__.py`:

### Single-Turn Prompt (returns string)

```python
@prompt(tags={"your_category"})
def your_prompt(topic: str, depth: str = "brief") -> str:
    """Generate a prompt for your use case."""
    if depth == "detailed":
        return (
            f"Provide a comprehensive analysis of '{topic}'. "
            f"Include all relevant details and cross-references."
        )
    return f"Provide a concise summary about '{topic}'."
```

### Multi-Turn Prompt (returns Message list)

```python
from fastmcp.prompts import Message, prompt


@prompt(tags={"your_category"})
def your_conversation_prompt(subject: str) -> list[Message]:
    """Generate a multi-turn prompt for your use case."""
    return [
        Message(
            f"Please analyze '{subject}' covering:\n"
            f"1. Key aspects\n"
            f"2. Important details\n"
            f"3. Conclusions"
        ),
        Message(
            "I'll analyze this systematically.",
            role="assistant",
        ),
    ]
```

## Prompt Conventions

| Convention | Details |
|-----------|---------|
| Decorator | `@prompt(tags={"category"})` |
| Return type | `str` for single-turn, `list[Message]` for multi-turn |
| Message role | Default is `"user"`, specify `role="assistant"` for assistant turns |
| Parameters | Use typed params with defaults for optional configuration |
| No async | Prompts are sync functions (no database access) |

## Prompt Registration

Add to `ALL_PROMPTS` at the bottom of the file:

```python
ALL_PROMPTS = [analyze_book, search_query, summarize_collection, your_prompt]
```

Prompts are auto-registered in `server.py` via:
```python
for prompt_fn in ALL_PROMPTS:
    mcp.add_prompt(prompt_fn)
```

## See Also

- `solomon-mcp-tool` — For creating interactive tools (vs. read-only resources)
- `solomon-model-migration` — For creating the model a resource exposes
