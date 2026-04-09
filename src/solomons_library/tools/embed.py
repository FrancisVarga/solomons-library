from __future__ import annotations

import os

from fastmcp import Context
from fastmcp.tools import tool
from loguru import logger
from sqlalchemy import select

from solomons_library.config import settings
from solomons_library.db import get_async_session_factory
from solomons_library.models import Embedding


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
async def embed_text(text_content: str, source: str | None = None, ctx: Context | None = None) -> dict:
    """Embed text using OpenAI or Gemini and store the vector in the database.

    Generates a 1536-dimensional embedding vector and persists it alongside
    the original text for later similarity search.
    """
    if ctx:
        await ctx.info(f"Generating embedding for text ({len(text_content)} chars)")
        await ctx.report_progress(progress=0, total=100)

    vector, model_name = await _generate_embedding(text_content)

    if ctx:
        await ctx.report_progress(progress=50, total=100)
        await ctx.info(f"Embedding generated via {model_name}, storing in database")

    project_name = settings.PROJECT_NAME
    try:
        user = os.getlogin()
    except OSError:
        user = os.environ.get("USER") or os.environ.get("USERNAME", "unknown")

    async_session = get_async_session_factory()
    async with async_session() as session:
        embedding = Embedding(
            text=text_content,
            source=source,
            model=model_name,
            project_name=project_name,
            user=user,
            embedding=vector,
        )
        session.add(embedding)
        await session.commit()
        await session.refresh(embedding)

    if ctx:
        await ctx.report_progress(progress=100, total=100)
        await ctx.info(f"Embedding stored with ID {embedding.id} (project={project_name}, user={user})")

    return {
        "id": embedding.id,
        "model": model_name,
        "dimensions": len(vector),
        "source": source,
        "project_name": project_name,
        "user": user,
        "text_length": len(text_content),
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
