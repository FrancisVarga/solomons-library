from __future__ import annotations

import asyncio
import os
import re

from fastmcp import Context
from fastmcp.tools import tool
from loguru import logger
from sqlalchemy import select

from solomons_library.config import settings
from solomons_library.db import get_async_session_factory
from solomons_library.models import Embedding

# ---------------------------------------------------------------------------
# Smart chunking
# ---------------------------------------------------------------------------

# ~6000 tokens ≈ 24000 chars for text-embedding-3-small (8191 token limit)
DEFAULT_CHUNK_SIZE = 2000  # chars — sweet spot for embedding quality
DEFAULT_CHUNK_OVERLAP = 200  # chars — preserves context at boundaries


def _split_into_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks at semantic boundaries.

    Strategy (in priority order):
    1. Split on markdown headings (## / ###)
    2. Split on double newlines (paragraphs)
    3. Split on single newlines (lines)
    4. Split on sentence boundaries (. ! ?)
    5. Hard split at chunk_size as last resort

    Chunks smaller than chunk_size are merged with the next chunk.
    """
    if len(text) <= chunk_size:
        return [text]

    # Try semantic split points in priority order
    segments = _split_at_headings(text)
    if len(segments) <= 1:
        segments = _split_at_paragraphs(text)

    # Merge small segments and split large ones into final chunks
    return _merge_and_split(segments, chunk_size, chunk_overlap)


def _split_at_headings(text: str) -> list[str]:
    """Split on markdown headings (##, ###, etc.)."""
    parts = re.split(r'(?=\n#{1,4} )', text)
    return [p.strip() for p in parts if p.strip()]


def _split_at_paragraphs(text: str) -> list[str]:
    """Split on double newlines (paragraph boundaries)."""
    parts = re.split(r'\n\s*\n', text)
    return [p.strip() for p in parts if p.strip()]


def _split_at_sentences(text: str, chunk_size: int) -> list[str]:
    """Split oversized text at sentence boundaries."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 > chunk_size and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _merge_and_split(
    segments: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Merge small segments together; split oversized ones."""
    chunks: list[str] = []
    current = ""

    for segment in segments:
        # If adding this segment stays under limit, merge it
        if len(current) + len(segment) + 1 <= chunk_size:
            current = f"{current}\n\n{segment}" if current else segment
            continue

        # Flush current chunk if it has content
        if current:
            chunks.append(current.strip())
            # Keep overlap from the tail of the previous chunk
            if chunk_overlap > 0:
                current = current[-chunk_overlap:].lstrip() + "\n\n" + segment
                if len(current) <= chunk_size:
                    continue
                # If overlap + new segment is still too big, just use segment
                current = segment
            else:
                current = segment

        # If a single segment exceeds chunk_size, split at sentences
        if len(current) > chunk_size:
            sub_chunks = _split_at_sentences(current, chunk_size)
            # All but last become finalized chunks
            chunks.extend(sub_chunks[:-1])
            current = sub_chunks[-1] if sub_chunks else ""

    if current.strip():
        chunks.append(current.strip())

    return chunks


async def _embed_openai(text_content: str) -> tuple[list[float], str]:
    """Generate embedding via OpenAI text-embedding-3-small."""
    import openai

    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text_content,
    )
    return response.data[0].embedding, "openai:text-embedding-3-small"


async def _embed_gemini(text_content: str) -> tuple[list[float], str]:
    """Generate embedding via Gemini gemini-embedding-exp-03-07 (zero-padded to 1536)."""
    from google import genai

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = await client.aio.models.embed_content(
        model="gemini-embedding-exp-03-07",
        contents=text_content,
    )
    raw = response.embeddings[0].values  # type: ignore[union-attr]
    vector = list(raw) if raw else []
    # Pad to 1536 dimensions to match OpenAI vector size
    if len(vector) < 1536:
        vector.extend([0.0] * (1536 - len(vector)))
    return vector[:1536], "gemini:gemini-embedding-exp-03-07"


async def _generate_embedding(text_content: str) -> tuple[list[float], str]:
    """Generate embedding using OpenAI (primary) with Gemini fallback."""
    if settings.OPENAI_API_KEY:
        try:
            return await _embed_openai(text_content)
        except Exception as e:
            logger.warning(f"OpenAI embedding failed: {e}, falling back to Gemini")

    if settings.GEMINI_API_KEY:
        return await _embed_gemini(text_content)

    raise RuntimeError("No embedding API key configured (set OPENAI_API_KEY or GEMINI_API_KEY)")


@tool(task=True, tags={"embeddings", "write"})
async def embed_text(
    text_content: str,
    source: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ctx: Context | None = None,
) -> dict:
    """Embed text using OpenAI or Gemini and store the vector in the database.

    Large text is automatically split into overlapping chunks at semantic
    boundaries (headings, paragraphs, sentences). Each chunk gets its own
    embedding for better search precision.

    Args:
        text_content: The text to embed.
        source: Optional source identifier (e.g., filename or URL).
        chunk_size: Maximum characters per chunk (default 2000).
        chunk_overlap: Overlap between chunks to preserve context (default 200).
    """
    chunks = _split_into_chunks(text_content, chunk_size, chunk_overlap)
    total_chunks = len(chunks)

    if ctx:
        await ctx.info(f"Embedding {len(text_content)} chars in {total_chunks} chunk(s)")
        await ctx.report_progress(progress=0, total=100)

    project_name = settings.PROJECT_NAME
    try:
        user = os.getlogin()
    except OSError:
        user = os.environ.get("USER") or os.environ.get("USERNAME", "unknown")

    # Generate all embeddings in parallel
    if ctx:
        await ctx.info("Generating embeddings in parallel...")

    embedding_tasks = [_generate_embedding(chunk) for chunk in chunks]
    vectors_and_models = await asyncio.gather(*embedding_tasks)

    if ctx:
        await ctx.report_progress(progress=50, total=100)
        await ctx.info(f"All {total_chunks} embedding(s) generated, storing in database...")

    model_name = vectors_and_models[0][1] if vectors_and_models else ""

    # Store all chunks in parallel
    async def _store_chunk(i: int, chunk: str, vector: list[float], model: str) -> dict:
        chunk_source = source
        if total_chunks > 1 and source:
            chunk_source = f"{source}#chunk-{i + 1}"

        async_session = get_async_session_factory()
        async with async_session() as session:
            embedding = Embedding(
                text=chunk,
                source=chunk_source,
                model=model,
                project_name=project_name,
                user=user,
                embedding=vector,
            )
            session.add(embedding)
            await session.commit()
            await session.refresh(embedding)

        return {"id": embedding.id, "chunk": i + 1, "text_length": len(chunk)}

    store_tasks = [
        _store_chunk(i, chunk, vector, model)
        for i, (chunk, (vector, model)) in enumerate(zip(chunks, vectors_and_models))
    ]
    results = await asyncio.gather(*store_tasks)

    if ctx:
        await ctx.report_progress(progress=100, total=100)
        await ctx.info(f"All {total_chunks} chunk(s) stored")

    return {
        "model": model_name,
        "dimensions": 1536,
        "source": source,
        "project_name": project_name,
        "user": user,
        "total_text_length": len(text_content),
        "chunks": total_chunks,
        "embeddings": sorted(results, key=lambda r: r["chunk"]),
    }


@tool(tags={"embeddings", "read"}, annotations={"readOnlyHint": True})
async def search_embeddings(query: str, limit: int = 5, ctx: Context | None = None) -> list[dict]:
    """Search stored embeddings by semantic similarity to a query.

    Generates an embedding for the query text and finds the closest
    matches using cosine distance (pgvector <=> operator).
    """
    if ctx:
        await ctx.info(f"Searching embeddings for: {query!r}")

    query_vector, _ = await _generate_embedding(query)

    async_session = get_async_session_factory()
    async with async_session() as session:
        distance = Embedding.embedding.cosine_distance(query_vector)
        stmt = (
            select(Embedding, distance.label("distance"))
            .order_by(distance)
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

    if ctx:
        await ctx.info(f"Found {len(rows)} results")

    return [
        {
            "id": emb.id,
            "text": emb.text[:200],
            "source": emb.source,
            "model": emb.model,
            "project_name": emb.project_name,
            "user": emb.user,
            "similarity": round(1 - dist, 4),
        }
        for emb, dist in rows
    ]
