import json

from fastmcp import Context
from fastmcp.resources import resource
from sqlalchemy import func, select

from solomons_library.db import get_async_session_factory
from solomons_library.models import Book, Embedding


@resource("library://stats", description="Library statistics", mime_type="application/json")
async def get_library_stats(ctx: Context | None = None) -> str:
    """Provides library statistics: book count, embedding count, and latest activity."""
    if ctx:
        await ctx.debug("Fetching library stats")

    async_session = get_async_session_factory()
    async with async_session() as session:
        book_count = (await session.execute(select(func.count(Book.id)))).scalar() or 0
        embedding_count = (await session.execute(select(func.count(Embedding.id)))).scalar() or 0

    return json.dumps({"books": book_count, "embeddings": embedding_count})


@resource("library://books", description="All books in the library", mime_type="application/json")
async def get_all_books(ctx: Context | None = None) -> str:
    """Returns all books in the library as JSON."""
    if ctx:
        await ctx.debug("Fetching all books")

    async_session = get_async_session_factory()
    async with async_session() as session:
        result = await session.execute(select(Book))
        books = result.scalars().all()
        return json.dumps([
            {"id": b.id, "title": b.title, "author": b.author, "isbn": b.isbn}
            for b in books
        ])


@resource("library://books/{book_id}", description="A specific book by ID", mime_type="application/json")
async def get_book_by_id(book_id: str, ctx: Context | None = None) -> str:
    """Returns a single book by its ID."""
    if ctx:
        await ctx.debug(f"Fetching book {book_id}")

    async_session = get_async_session_factory()
    async with async_session() as session:
        book = await session.get(Book, int(book_id))
        if not book:
            return json.dumps({"error": f"Book {book_id} not found"})
        return json.dumps({"id": book.id, "title": book.title, "author": book.author, "isbn": book.isbn})


@resource("library://embeddings/recent", description="Recent embeddings", mime_type="application/json")
async def get_recent_embeddings(ctx: Context | None = None) -> str:
    """Returns the 10 most recent embeddings stored."""
    if ctx:
        await ctx.debug("Fetching recent embeddings")

    async_session = get_async_session_factory()
    async with async_session() as session:
        result = await session.execute(
            select(Embedding).order_by(Embedding.created_at.desc()).limit(10)
        )
        embeddings = result.scalars().all()
        return json.dumps([
            {"id": e.id, "text": e.text[:200], "source": e.source, "model": e.model}
            for e in embeddings
        ])


ALL_RESOURCES = [get_library_stats, get_all_books, get_book_by_id, get_recent_embeddings]
