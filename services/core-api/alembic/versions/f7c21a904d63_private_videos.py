"""Make existing and new video analyses private by default."""
from alembic import op
import sqlalchemy as sa

revision = "f7c21a904d63"
down_revision = "e6b9d18a40c2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("pending_file_erasures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_path", sa.String(2048), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_table("privacy_erasure_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("performed_at", sa.DateTime(), nullable=False))
    op.create_index("ix_privacy_erasure_records_performed_at", "privacy_erasure_records", ["performed_at"])
    op.add_column("videos", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_table("pending_file_erasures")
    op.drop_table("privacy_erasure_records")
    with op.batch_alter_table("videos") as batch:
        batch.drop_column("is_public")
