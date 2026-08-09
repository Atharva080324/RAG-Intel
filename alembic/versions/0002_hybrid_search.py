"""Add indexed PostgreSQL full-text search for hybrid retrieval."""
from alembic import op

revision = "0002_hybrid_search"
down_revision = "0001_phase_one"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("ALTER TABLE chunks ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED")
    op.execute("CREATE INDEX ix_chunks_search_vector ON chunks USING GIN (search_vector)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_search_vector")
    op.execute("ALTER TABLE chunks DROP COLUMN search_vector")
