from fastmcp import Context
from fastmcp.tools import tool
from sqlalchemy import select

from solomons_library.db import get_async_session_factory
from solomons_library.models import Book


@tool(tags={"books", "write"})
async def add_book(title: str, author: str, isbn: str | None = None, ctx: Context | None = None) -> dict:
    """Add a new book to Solomon's Library."""
    if ctx:
        await ctx.info(f"Adding book: {title} by {author}")

    async_session = get_async_session_factory()
    async with async_session() as session:
        book = Book(title=title, author=author, isbn=isbn)
        session.add(book)
        await session.commit()
        await session.refresh(book)

        if ctx:
            await ctx.info(f"Book added with ID {book.id}")

        return {"id": book.id, "title": book.title, "author": book.author, "isbn": book.isbn}


@tool(tags={"books", "read"}, annotations={"readOnlyHint": True})
async def list_books(limit: int = 20, ctx: Context | None = None) -> list[dict]:
    """List books in Solomon's Library."""
    if ctx:
        await ctx.debug(f"Listing up to {limit} books")

    async_session = get_async_session_factory()
    async with async_session() as session:
        result = await session.execute(select(Book).limit(limit))
        books = result.scalars().all()
        return [
            {"id": b.id, "title": b.title, "author": b.author, "isbn": b.isbn}
            for b in books
        ]


@tool(tags={"books", "read"}, annotations={"readOnlyHint": True})
async def get_book(book_id: int, ctx: Context | None = None) -> dict:
    """Get a specific book by its ID."""
    if ctx:
        await ctx.debug(f"Fetching book {book_id}")

    async_session = get_async_session_factory()
    async with async_session() as session:
        book = await session.get(Book, book_id)
        if not book:
            return {"error": f"Book with ID {book_id} not found"}
        return {"id": book.id, "title": book.title, "author": book.author, "isbn": book.isbn}
