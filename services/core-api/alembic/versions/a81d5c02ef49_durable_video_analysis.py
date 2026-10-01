"""Persist URL inputs for video analysis outbox jobs."""
from alembic import op
import sqlalchemy as sa

revision = "a81d5c02ef49"
down_revision = "f7c21a904d63"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("videos", sa.Column("source_url", sa.String(2048), nullable=True))
    op.add_column("videos", sa.Column("source_platform", sa.String(64), nullable=True))


def downgrade():
    with op.batch_alter_table("videos") as batch:
        batch.drop_column("source_platform")
        batch.drop_column("source_url")
