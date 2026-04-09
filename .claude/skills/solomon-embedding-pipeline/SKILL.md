---
description: "This skill should be used when extending the embedding pipeline in Solomon's Library, adding a new embedding provider, modifying the chunking strategy, tuning vector dimensions, or implementing the OpenAI-to-Gemini fallback pattern."
version: 0.1.0
tags:
  - embeddings
  - openai
  - gemini
  - pgvector
  - chunking
  - solomon
---

# Solomon's Library — Embedding Pipeline Pattern

All pipeline code lives in `src/solomons_library/tools/embed.py`.

## Pipeline Overview

```
Input Text
  ↓
_split_into_chunks() → list[str]  (semantic chunking)
  ↓
_generate_embedding() → (vector, model_name)  (OpenAI primary, Gemini fallback)
  ↓
Store Embedding ORM → PostgreSQL/pgvector  (1536-dim HNSW cosine index)
  ↓
cache_invalidate("sl:search:*", "sl:res:*")
```

All pipeline code lives in `src/solomons_library/tools/embed.py`.

## Adding a New Embedding Provider

### Step 1: Add the provider function

```python
async def _embed_your_provider(text_content: str) -> tuple[list[float], str]:
    """Generate embedding via YourProvider."""
    import your_sdk

    client = your_sdk.AsyncClient(api_key=settings.YOUR_API_KEY)
    response = await client.embed(model="model-name", input=text_content)
    raw = response.embeddings[0]
    vector = list(raw) if raw else []

    # CRITICAL: Pad or truncate to 1536 dimensions to match pgvector column
    if len(vector) < 1536:
        vector.extend([0.0] * (1536 - len(vector)))
    return vector[:1536], "your_provider:model-name"
```

### Step 2: Add the API key to config

In `src/solomons_library/config.py`:
```python
YOUR_API_KEY: str = field(default_factory=lambda: os.environ.get("YOUR_API_KEY", ""))
```

### Step 3: Wire into the fallback chain

In `_generate_embedding()`:
```python
@cached(namespace="embed", ttl=3600, key_args=(0,))
async def _generate_embedding(text_content: str) -> tuple[list[float], str]:
    if settings.OPENAI_API_KEY:
        try:
            return await _embed_openai(text_content)
        except Exception as e:
            logger.warning(f"OpenAI failed: {e}, trying next provider")

    if settings.YOUR_API_KEY:
        try:
            return await _embed_your_provider(text_content)
        except Exception as e:
            logger.warning(f"YourProvider failed: {e}, trying Gemini")

    if settings.GEMINI_API_KEY:
        return await _embed_gemini(text_content)

    raise RuntimeError("No embedding API key configured")
```

## Key Design Decisions

### Vector Dimension: 1536

All providers must output exactly 1536 floats. The pgvector column `Vector(1536)` and the HNSW index are fixed at this dimension. If a provider returns fewer dimensions, **zero-pad**. If more, **truncate**.

```python
# Padding pattern (from Gemini provider):
if len(vector) < 1536:
    vector.extend([0.0] * (1536 - len(vector)))
return vector[:1536], "provider:model"
```

### Return Tuple: `(vector, model_name)`

Every provider returns `tuple[list[float], str]`. The model name follows `provider:model-version` format (e.g., `"openai:text-embedding-3-small"`, `"gemini:gemini-embedding-exp-03-07"`). This is stored in `Embedding.model` for audit trail.

### Caching

`_generate_embedding()` uses `@cached(namespace="embed", ttl=3600, key_args=(0,))`:
- 1-hour TTL for generated embeddings
- Only the first arg (`text_content`) is used as cache key
- `ctx` is automatically excluded from cache keys

## Chunking Strategy

Configuration in `embed.py`:
```python
DEFAULT_CHUNK_SIZE = 2000    # chars — sweet spot for embedding quality
DEFAULT_CHUNK_OVERLAP = 200  # chars — preserves context at boundaries
```

Split priority (semantic boundaries):
1. Markdown headings (`## `, `### `, `#### `)
2. Double newlines (paragraphs)
3. Single newlines (lines)
4. Sentence boundaries (`. ! ?`)
5. Hard split at `chunk_size` (last resort)

Small segments are merged up to `chunk_size`. Oversized segments are split at the next semantic boundary. Overlap is preserved by keeping the last `chunk_overlap` chars from the previous chunk.

### Modifying Chunking

To add a new split strategy, insert it into `_split_into_chunks()`:
```python
def _split_into_chunks(text, chunk_size=DEFAULT_CHUNK_SIZE, chunk_overlap=DEFAULT_CHUNK_OVERLAP):
    if len(text) <= chunk_size:
        return [text]

    segments = _split_at_headings(text)
    if len(segments) <= 1:
        segments = _split_at_your_boundary(text)  # <-- new strategy
    if len(segments) <= 1:
        segments = _split_at_paragraphs(text)

    return _merge_and_split(segments, chunk_size, chunk_overlap)
```

## Parallel Embedding & Storage

The `embed_text` tool processes chunks in parallel:

```python
# Generate all embeddings in parallel
embedding_tasks = [_generate_embedding(chunk) for chunk in chunks]
vectors_and_models = await asyncio.gather(*embedding_tasks)

# Store all chunks in parallel
store_tasks = [_store_chunk(i, chunk, vector, model) for i, ...]
results = await asyncio.gather(*store_tasks)
```

Progress is reported at key milestones:
- `0/100` — Start
- `50/100` — All embeddings generated
- `100/100` — All chunks stored

## Anti-patterns

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Returning raw provider vector without dimension check | pgvector INSERT fails or vector mismatch | Always pad/truncate to 1536 |
| Adding cache key_args beyond index 0 | `ctx` bleeds into cache key, causing misses | Keep `key_args=(0,)` |
| Raising inside `_generate_embedding` without logger.warning | Silent fallback skip | Log before falling through |

## See Also

- `solomon-mcp-tool` — For creating the tool wrapper around pipeline operations
- `solomon-model-migration` — For modifying the Embedding model or adding vector columns
