# Solomon's Library

You have MemPalace agents. Run mempalace_list_agents to see them.

## Stack
- Python 3.13, FastMCP 3.2.2, SQLAlchemy (async), Alembic, Loguru
- PostgreSQL with pgvector for vector embeddings
- Redis for task queue (Docket) and session state
- OpenAI / Gemini for text embeddings

## Commands
- Run server: `uv run python -m solomons_library`
- Run migration: `uv run alembic upgrade head`
- Generate migration: `uv run alembic revision --autogenerate -m "description"`
- Install deps: `uv sync`

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
