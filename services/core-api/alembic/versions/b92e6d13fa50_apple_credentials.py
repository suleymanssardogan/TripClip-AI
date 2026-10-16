"""Encrypted Apple credentials and durable account-deletion revocation."""
from alembic import op
import sqlalchemy as sa
revision = "b92e6d13fa50"
down_revision = "a81d5c02ef49"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("apple_refresh_token_encrypted", sa.Text(), nullable=True))
    op.create_table("apple_revocations", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("encrypted_token", sa.Text(), nullable=False),
                    sa.Column("attempts", sa.Integer(), nullable=False),
                    sa.Column("available_at", sa.DateTime(), nullable=False))
    op.create_index("ix_apple_revocations_available_at", "apple_revocations", ["available_at"])


def downgrade():
    op.drop_table("apple_revocations")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("apple_refresh_token_encrypted")
