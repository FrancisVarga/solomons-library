"""Skill discovery tools — semantic search and retrieval of project skills."""

from __future__ import annotations

from pathlib import Path

from fastmcp import Context
from fastmcp.tools import tool
from sqlalchemy import select

from solomons_library.db import get_async_session_factory
from solomons_library.models import Embedding
from solomons_library.tools.embed import _generate_embedding

SKILLS_PROJECT = "solomon-skills"


def _get_skills_dir() -> Path:
    """Return the project skills directory."""
    return Path.cwd() / ".claude" / "skills"


@tool(tags={"skills", "write"})
async def index_skills(
    ctx: Context | None = None,
) -> dict:
    """Index all project skills as embeddings for semantic search.

    Reads every SKILL.md, generates embeddings, and stores them with
    source='skill:<name>'. Skips skills that are already indexed.
    Run this after adding or updating skills.
    """
    skills_dir = _get_skills_dir()
    if not skills_dir.exists():
        return {"error": "No skills directory found"}

    async_session = get_async_session_factory()
    indexed = 0
    skipped = 0

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        skill_name = skill_dir.name
        source = f"skill:{skill_name}"

        # Check if already indexed
        async with async_session() as session:
            existing = await session.execute(
                select(Embedding.id)
                .where(Embedding.source == source)
                .where(Embedding.project_name == SKILLS_PROJECT)
                .limit(1)
            )
            if existing.scalar() is not None:
                skipped += 1
                continue

        content = skill_file.read_text(encoding="utf-8")
        if ctx:
            await ctx.info(f"Indexing skill: {skill_name}")

        vector, model_name = await _generate_embedding(content)

        async with async_session() as session:
            emb = Embedding(
                text=content,
                source=source,
                model=model_name,
                project_name=SKILLS_PROJECT,
                user="system",
                agent="skill-indexer",
                embedding=vector,
            )
            session.add(emb)
            await session.commit()

        indexed += 1

    if ctx:
        await ctx.info(f"Indexed {indexed} skill(s), skipped {skipped} (already indexed)")

    return {"indexed": indexed, "skipped": skipped}


@tool(tags={"skills", "write"})
async def reindex_skills(
    ctx: Context | None = None,
) -> dict:
    """Re-index all project skills, replacing existing embeddings.

    Deletes all existing skill embeddings and re-indexes from scratch.
    Use after modifying skill content.
    """
    async_session = get_async_session_factory()

    # Delete existing skill embeddings
    async with async_session() as session:
        existing = await session.execute(
            select(Embedding)
            .where(Embedding.project_name == SKILLS_PROJECT)
        )
        rows = existing.scalars().all()
        for row in rows:
            await session.delete(row)
        await session.commit()
        deleted = len(rows)

    if ctx:
        await ctx.info(f"Deleted {deleted} existing skill embedding(s), re-indexing...")

    return await index_skills(ctx=ctx)


@tool(tags={"skills", "read"}, annotations={"readOnlyHint": True})
async def search_skills(
    query: str,
    limit: int = 3,
    ctx: Context | None = None,
) -> list[dict]:
    """Search project skills by semantic similarity.

    Uses vector embeddings to find skills matching a natural language query.
    Returns skill names, descriptions, and similarity scores.
    Use get_skill to read the full content of a matched skill.

    Args:
        query: Natural language query (e.g., "how to add a database table").
        limit: Maximum results to return (default 3).
    """
    if ctx:
        await ctx.info(f"Searching skills for: {query!r}")

    query_vector, _ = await _generate_embedding(query)

    async_session = get_async_session_factory()
    async with async_session() as session:
        distance = Embedding.embedding.cosine_distance(query_vector)
        stmt = (
            select(Embedding, distance.label("distance"))
            .where(Embedding.project_name == SKILLS_PROJECT)
            .order_by(distance)
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

    if not rows:
        if ctx:
            await ctx.info("No skills indexed yet. Run index_skills first.")
        return []

    if ctx:
        await ctx.info(f"Found {len(rows)} matching skill(s)")

    results = []
    for emb, dist in rows:
        skill_name = emb.source.replace("skill:", "") if emb.source else ""
        # Extract description from frontmatter
        description = ""
        if emb.text:
            for line in emb.text.splitlines():
                stripped = line.strip()
                if stripped.startswith("description:"):
                    description = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                    break

        results.append({
            "name": skill_name,
            "description": description,
            "similarity": round(1 - dist, 4),
            "uri": f"skill://{skill_name}/SKILL.md",
        })

    return results


@tool(tags={"skills", "read"}, annotations={"readOnlyHint": True})
async def get_skill(
    skill_name: str,
    ctx: Context | None = None,
) -> dict:
    """Get the full content of a project skill by name.

    Returns the complete SKILL.md content for use as development guidance.

    Args:
        skill_name: Skill name (e.g., "solomon-mcp-tool", "solomon-model-migration").
    """
    if ctx:
        await ctx.debug(f"Reading skill: {skill_name}")

    skill_file = _get_skills_dir() / skill_name / "SKILL.md"
    if not skill_file.exists():
        return {"error": f"Skill '{skill_name}' not found"}

    content = skill_file.read_text(encoding="utf-8")

    return {
        "name": skill_name,
        "uri": f"skill://{skill_name}/SKILL.md",
        "content": content,
    }
