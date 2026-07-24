"""add_user_apns_token

Revision ID: b4f8e1a9c2d3
Revises: 9c1a4f2b7e3d
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4f8e1a9c2d3'
down_revision: Union[str, Sequence[str], None] = '9c1a4f2b7e3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('apns_token', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'apns_token')
