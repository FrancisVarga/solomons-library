<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-10 | Updated: 2026-04-10 -->

# resources

## Purpose
MCP resource endpoints that expose library data via `library://` URIs. Resources are read-only data views cached in Redis, providing stats, book listings, recent embeddings, and upload history.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | All resource definitions and `ALL_RESOURCES` list for registration in `server.py` |

## For AI Agents

### Working In This Directory
- Resources use `@resource("library://uri", ...)` decorator from `fastmcp.resources`
- All resources return JSON strings (not dicts) — this is the MCP resource convention
- Resources are registered in `server.py` via `mcp.add_resource(fn)`
- New resources must be added to the `ALL_RESOURCES` list

### Available Resources

| URI | Description |
|-----|-------------|
| `library://stats` | Book count, embedding count |
| `library://books` | All books as JSON array |
| `library://books/{book_id}` | Single book by ID |
| `library://embeddings/recent` | 10 most recent embeddings |
| `library://uploads/recent` | 20 most recent file uploads |

### Common Patterns
```python
@resource("library://my-resource", description="...", mime_type="application/json")
async def get_my_resource(ctx: Context | None = None) -> str:
    cache_key = _make_key("res", "my_resource")
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit
    # ... fetch data ...
    data = json.dumps(result)
    await cache_set(cache_key, data, ttl=30)
    return data
```

## Dependencies

### Internal
- `solomons_library/db/` — `get_async_session_factory()`
- `solomons_library/models/` — `Book`, `Embedding`, `FileUpload`
- `solomons_library/cache.py` — `cache_get`, `cache_set`, `_make_key`, `_hash_args`

### External
- `fastmcp` — `Context`, `@resource` decorator
- `sqlalchemy` — Queries via `select()`, `func.count()`

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
