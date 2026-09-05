"""Add canonical_format_hit

Revision ID: c961f1f9fde9
Revises: 0f4a61c5ea63
Create Date: 2026-08-18 18:38:47.420221

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c961f1f9fde9"
down_revision: Union[str, Sequence[str], None] = "0f4a61c5ea63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


HNSW_INDEX_DDL = """
    CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
    """


def upgrade() -> None:
    """Upgrade schema."""
    # This revision only adds eval_runs.canonical_format_hit.
    #
    # Autogenerate originally emitted a drop_index for ix_document_chunks_embedding here: the HNSW
    # index is created with raw SQL in f5da07b9db1a (pgvector operator classes aren't expressible in
    # the model), so Alembic can't see it in Base.metadata and reports it as a stray index to remove.
    # Applying that drop left every vector similarity search doing a sequential scan. Re-create the
    # index idempotently instead, so migrating to head always leaves it in place.
    op.add_column("eval_runs", sa.Column("canonical_format_hit", sa.Boolean(), nullable=True))
    op.execute(HNSW_INDEX_DDL)


def downgrade() -> None:
    """Downgrade schema."""
    # The index belongs to f5da07b9db1a, so leave it alone here — only reverse this revision's column.
    op.drop_column("eval_runs", "canonical_format_hit")
