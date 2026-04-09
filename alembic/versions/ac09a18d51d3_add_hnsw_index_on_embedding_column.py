"""add hnsw index on embedding column

Revision ID: ac09a18d51d3
Revises: e44cbc66db5c
Create Date: 2026-04-09 18:50:28.589965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac09a18d51d3'
down_revision: Union[str, Sequence[str], None] = 'e44cbc66db5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "CREATE INDEX ix_embeddings_embedding_hnsw ON embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_embeddings_embedding_hnsw", table_name="embeddings")
