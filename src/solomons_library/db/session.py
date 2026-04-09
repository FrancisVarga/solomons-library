import re

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from solomons_library.config import settings


def get_engine():
    """Sync engine — used by Alembic migrations."""
    url = re.sub(r"^postgresql(\+\w+)?://", "postgresql+psycopg://", settings.DATABASE_URL)
    return create_engine(url)


def get_session_factory():
    """Sync session factory — used by Alembic."""
    return sessionmaker(bind=get_engine())


def get_async_engine():
    """Async engine — used by the FastMCP server at runtime."""
    return create_async_engine(settings.async_database_url)


def get_async_session_factory():
    """Async session factory — used by tools and resources."""
    return async_sessionmaker(bind=get_async_engine(), class_=AsyncSession, expire_on_commit=False)
