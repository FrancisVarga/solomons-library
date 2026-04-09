from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    DATABASE_URL: str = field(default_factory=lambda: os.environ["DATABASE_URL"])
    OPENAI_API_KEY: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    GEMINI_API_KEY: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    REDIS_URL: str = field(default_factory=lambda: os.environ.get("REDIS_URL", "redis://localhost:6379"))
    SERVER_HOST: str = field(default_factory=lambda: os.environ.get("SERVER_HOST", "0.0.0.0"))
    SERVER_PORT: int = field(default_factory=lambda: int(os.environ.get("SERVER_PORT", "8000")))
    PROJECT_NAME: str = field(default_factory=lambda: os.environ.get("PROJECT_NAME", "solomons-library"))

    @property
    def async_database_url(self) -> str:
        """Normalize any postgresql URL to postgresql+asyncpg:// for async engine."""
        import re
        return re.sub(r"^postgresql(\+\w+)?://", "postgresql+asyncpg://", self.DATABASE_URL)


settings = Settings()
