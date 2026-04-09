import json

from fastmcp import Context
from fastmcp.resources import resource
from sqlalchemy import func, select

from solomons_library.cache import cache_get, cache_set, _make_key, _hash_args
from solomons_library.db import get_async_session_factory
from solomons_library.models import Book, Embedding, FileUpload


@resource("library://stats", description="Library statistics", mime_type="application/json")
async def get_library_stats(ctx: Context | None = None) -> str:
    """Provides library statistics: book count, embedding count, and latest activity."""
    if ctx:
        await ctx.debug("Fetching library stats")

    cache_key = _make_key("res", "stats")
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit

    async_session = get_async_session_factory()
    async with async_session() as session:
        book_count = (await session.execute(select(func.count(Book.id)))).scalar() or 0
        embedding_count = (await session.execute(select(func.count(Embedding.id)))).scalar() or 0

    data = json.dumps({"books": book_count, "embeddings": embedding_count})
    await cache_set(cache_key, data, ttl=30)
    return data


@resource("library://books", description="All books in the library", mime_type="application/json")
async def get_all_books(ctx: Context | None = None) -> str:
    """Returns all books in the library as JSON."""
    if ctx:
        await ctx.debug("Fetching all books")

    cache_key = _make_key("res", "books")
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit

    async_session = get_async_session_factory()
    async with async_session() as session:
        result = await session.execute(select(Book))
        books = result.scalars().all()
        data = json.dumps([
            {"id": b.id, "title": b.title, "author": b.author, "isbn": b.isbn}
            for b in books
        ])

    await cache_set(cache_key, data, ttl=30)
    return data


@resource("library://books/{book_id}", description="A specific book by ID", mime_type="application/json")
async def get_book_by_id(book_id: str, ctx: Context | None = None) -> str:
    """Returns a single book by its ID."""
    if ctx:
        await ctx.debug(f"Fetching book {book_id}")

    cache_key = _make_key("res", _hash_args("book", book_id))
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit

    async_session = get_async_session_factory()
    async with async_session() as session:
        book = await session.get(Book, int(book_id))
        if not book:
            return json.dumps({"error": f"Book {book_id} not found"})
        data = json.dumps({"id": book.id, "title": book.title, "author": book.author, "isbn": book.isbn})

    await cache_set(cache_key, data, ttl=30)
    return data


@resource("library://embeddings/recent", description="Recent embeddings", mime_type="application/json")
async def get_recent_embeddings(ctx: Context | None = None) -> str:
    """Returns the 10 most recent embeddings stored."""
    if ctx:
        await ctx.debug("Fetching recent embeddings")

    cache_key = _make_key("res", "embeddings_recent")
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit

    async_session = get_async_session_factory()
    async with async_session() as session:
        result = await session.execute(
            select(Embedding).order_by(Embedding.created_at.desc()).limit(10)
        )
        embeddings = result.scalars().all()
        data = json.dumps([
            {"id": e.id, "text": e.text[:200], "source": e.source, "model": e.model}
            for e in embeddings
        ])

    await cache_set(cache_key, data, ttl=30)
    return data


@resource("library://uploads/recent", description="Recent file uploads", mime_type="application/json")
async def get_recent_uploads(ctx: Context | None = None) -> str:
    """Returns the 20 most recent file uploads with status."""
    if ctx:
        await ctx.debug("Fetching recent uploads")

    cache_key = _make_key("res", "uploads_recent")
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit

    async_session = get_async_session_factory()
    async with async_session() as session:
        result = await session.execute(
            select(FileUpload).order_by(FileUpload.created_at.desc()).limit(20)
        )
        uploads = result.scalars().all()
        data = json.dumps([
            {
                "id": u.id,
                "filename": u.filename,
                "mime_type": u.mime_type,
                "file_size": u.file_size,
                "status": u.status,
                "chunk_count": u.chunk_count,
                "project_name": u.project_name,
                "created_at": u.created_at.isoformat(),
            }
            for u in uploads
        ])

    await cache_set(cache_key, data, ttl=30)
    return data


ALL_RESOURCES = [get_library_stats, get_all_books, get_book_by_id, get_recent_embeddings, get_recent_uploads]
