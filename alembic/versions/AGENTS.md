<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-10 | Updated: 2026-04-10 -->

# versions

## Purpose
Alembic migration scripts tracking the schema evolution of Solomon's Library database. Migrations run in chain order via `down_revision` links.

## Key Files

| File | Description |
|------|-------------|
| `232940a192d3_create_books_table.py` | Initial books table creation |
| `e09975821e7f_initial_books_and_embeddings_tables_.py` | Books and embeddings tables with pgvector extension |
| `4efb13cb7aed_add_project_name_and_user_to_embeddings.py` | Add `project_name` and `user` columns to embeddings |
| `2773e984198b_add_indexes_on_project_name_and_user.py` | B-tree indexes on `project_name` and `user` |
| `e44cbc66db5c_add_index_on_created_at.py` | Index on `created_at` for time-ordered queries |
| `ac09a18d51d3_add_hnsw_index_on_embedding_column.py` | HNSW cosine index on the `embedding` vector column |
| `1ad31a3a4213_add_agent_column_to_embeddings.py` | Add `agent` column to embeddings for tracking source agent |
| `ae22f01f608b_add_file_uploads_table.py` | New `file_uploads` table for upload tracking |

## For AI Agents

### Working In This Directory
- Never edit existing migration files — create new ones instead
- Generate: `uv run alembic revision --autogenerate -m "description"`
- Apply: `uv run alembic upgrade head`
- Each file has `revision`, `down_revision`, and `upgrade()`/`downgrade()` functions
- The HNSW index migration uses `postgresql_using="hnsw"` with `vector_cosine_ops`

### Common Patterns
- pgvector operations use `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` in early migrations
- Index creation uses `op.create_index()` with `postgresql_using` and `postgresql_ops` kwargs
- Column additions use `op.add_column()` with nullable defaults for backward compatibility

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
