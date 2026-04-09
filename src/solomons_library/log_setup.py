import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """Route standard library logging through Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    """Configure Loguru as the sole logging sink."""
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    logger.add("logs/solomons_library.log", rotation="10 MB", retention="7 days", level="INFO")

    # Intercept stdlib logging through Loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "granian", "granian.access", "sqlalchemy.engine", "alembic"):
        logging.getLogger(name).handlers = [InterceptHandler()]

    # Silence noisy Docket scheduler and MCP internals
    for name in ("docket", "mcp", "httpcore", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)
