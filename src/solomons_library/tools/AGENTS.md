<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-10 | Updated: 2026-04-10 -->

# tools

## Purpose
MCP tool implementations — the primary interface for clients to interact with Solomon's Library. Tools handle book CRUD, embedding generation/search, file uploads with background processing, OpenAPI spec import, and skill discovery.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Legacy barrel export of `ALL_TOOLS` (server.py now registers tools individually) |
| `books.py` | `add_book`, `list_books`, `get_book` — Book CRUD with Redis caching |
| `embed.py` | `embed_text` (background task), `search_embeddings` — smart chunking, OpenAI→Gemini fallback, parallel embedding generation |
| `upload.py` | `upload_file`, `process_upload` (background), `get_upload_status`, `list_uploads` — two-phase file upload pipeline |
| `openapi.py` | `import_openapi_spec` — fetch and analyze an OpenAPI spec, return mounting instructions |
| `skills.py` | `index_skills`, `reindex_skills`, `search_skills`, `get_skill` — semantic search over project skills |
| `parsers.py` | File content extractors: TXT, MD, CSV, PDF (pymupdf), DOCX, HTML (BeautifulSoup), JSON, YAML |

## For AI Agents

### Working In This Directory
- Every tool function must be decorated with `@tool(...)` from `fastmcp.tools`
- New tools must be registered in `server.py` via `mcp.add_tool(fn)` and imported there
- Write tools use `tags={"domain", "write"}`, read tools use `tags={"domain", "read"}, annotations={"readOnlyHint": True}`
- Background tasks use `@tool(task=True)` — these run in the Docket queue, not inline
- All tools accept `ctx: Context | None = None` as the last parameter for MCP logging

### Key Architectural Decisions
- **Smart chunking** (`embed.py`): Text is split at semantic boundaries (headings → paragraphs → sentences → hard split) with configurable overlap
- **OpenAI→Gemini fallback** (`embed.py`): `_generate_embedding()` tries OpenAI first, falls back to Gemini; Gemini vectors are zero-padded to 1536 dims
- **Two-phase uploads** (`upload.py`): `upload_file` saves to disk and creates a DB record, then calls `process_upload` as a background task
- **Cache invalidation**: Write tools call `cache_invalidate("sl:*")` to bust Redis caches after mutations

### Testing Requirements
- Tools that write data (add_book, embed_text, upload_file) should be tested against a real database
- Embedding tools require API keys — mock or use Gemini for testing (free tier)

### Common Patterns
```python
@tool(tags={"domain", "write"})
async def my_tool(param: str, ctx: Context | None = None) -> dict:
    async_session = get_async_session_factory()
    async with async_session() as session:
        # ... DB operations
    await cache_invalidate("sl:domain:*")
    return {"result": "..."}
```

## Dependencies

### Internal
- `solomons_library/db/` — `get_async_session_factory()`
- `solomons_library/models/` — `Book`, `Embedding`, `FileUpload`
- `solomons_library/config.py` — `settings` (API keys, project name)
- `solomons_library/cache.py` — `cached`, `cache_invalidate`, `cache_get`, `cache_set`

### External
- `fastmcp` — `Context`, `@tool` decorator
- `openai` — OpenAI embedding API
- `google-genai` — Gemini embedding API
- `httpx` — HTTP client for OpenAPI fetching
- `pymupdf`, `python-docx`, `beautifulsoup4`, `pyyaml` — File parsers

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
