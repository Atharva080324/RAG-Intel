"""Add HNSW index for vector embeddings and document_id index on chunks.

Revision ID: 0006_vector_hnsw_index
Revises: 0005_stored_files
Create Date: 2026-10-16
"""
from alembic import op

revision = "0006_vector_hnsw_index"
down_revision = "0005_stored_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. HNSW index for sub-millisecond approximate nearest neighbor search via cosine distance
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
        "ON chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64);"
    )
    # 2. Foreign key filter index for document-scoped queries (where document_id = :id)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_document_id ON chunks (document_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw;")
    op.execute("DROP INDEX IF EXISTS ix_chunks_document_id;")
