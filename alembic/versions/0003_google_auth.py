"""Add Google OAuth identity fields."""
from alembic import op
import sqlalchemy as sa

revision = "0003_google_auth"
down_revision = "0002_hybrid_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=True)
    op.add_column("users", sa.Column("google_subject", sa.String(length=255), nullable=True))
    op.create_index("ix_users_google_subject", "users", ["google_subject"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_subject", table_name="users")
    op.drop_column("users", "google_subject")
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=False)
