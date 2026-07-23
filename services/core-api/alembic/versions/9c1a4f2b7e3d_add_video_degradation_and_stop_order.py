"""add_video_degradation_and_stop_order

Revision ID: 9c1a4f2b7e3d
Revises: 522707fe5956
Create Date: 2026-07-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c1a4f2b7e3d'
down_revision: Union[str, Sequence[str], None] = '522707fe5956'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('videos', sa.Column('degradation', sa.JSON(), nullable=True))
    op.add_column('videos', sa.Column('stop_order', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('videos', 'stop_order')
    op.drop_column('videos', 'degradation')
