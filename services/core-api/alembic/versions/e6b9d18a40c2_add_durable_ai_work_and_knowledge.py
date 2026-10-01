"""Durable AI follow-up work and reviewed place knowledge sources."""
from alembic import op
import sqlalchemy as sa

revision = "e6b9d18a40c2"
down_revision = "d4a9c2e6f108"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("deferred_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("lease_until", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("last_error", sa.String(100)))
    op.create_index("ix_deferred_jobs_due", "deferred_jobs", ["status", "available_at"])
    op.create_table("place_knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("place_id", sa.Integer(), sa.ForeignKey("places.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("source_title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("place_id", "source_url", name="uq_place_knowledge_source"))
    op.create_index("ix_place_knowledge_documents_place_id", "place_knowledge_documents", ["place_id"])


def downgrade():
    op.drop_table("place_knowledge_documents")
    op.drop_table("deferred_jobs")
