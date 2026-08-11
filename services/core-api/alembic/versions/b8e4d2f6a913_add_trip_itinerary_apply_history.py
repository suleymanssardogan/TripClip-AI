"""add_trip_itinerary_apply_history

Revision ID: b8e4d2f6a913
Revises: a7c3f091e8d5
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e4d2f6a913'
down_revision: Union[str, Sequence[str], None] = 'a7c3f091e8d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('trip_itinerary_apply_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trip_id', sa.Integer(), nullable=False),
    sa.Column('itinerary_id', sa.Integer(), nullable=True),
    sa.Column('previous_itinerary_id', sa.Integer(), nullable=True),
    sa.Column('previous_stops', sa.JSON(), nullable=False),
    sa.Column('is_undo', sa.Boolean(), nullable=False),
    sa.Column('actor_user_id', sa.Integer(), nullable=False),
    sa.Column('applied_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['itinerary_id'], ['trip_itineraries.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['previous_itinerary_id'], ['trip_itineraries.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trip_itinerary_apply_history_id'), 'trip_itinerary_apply_history', ['id'], unique=False)
    op.create_index(op.f('ix_trip_itinerary_apply_history_trip_id'), 'trip_itinerary_apply_history', ['trip_id'], unique=False)
    op.create_index(op.f('ix_trip_itinerary_apply_history_itinerary_id'), 'trip_itinerary_apply_history', ['itinerary_id'], unique=False)
    op.create_index(op.f('ix_trip_itinerary_apply_history_applied_at'), 'trip_itinerary_apply_history', ['applied_at'], unique=False)
    op.create_index(
        'ix_apply_history_trip_applied', 'trip_itinerary_apply_history',
        ['trip_id', 'applied_at'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_apply_history_trip_applied', table_name='trip_itinerary_apply_history')
    op.drop_index(op.f('ix_trip_itinerary_apply_history_applied_at'), table_name='trip_itinerary_apply_history')
    op.drop_index(op.f('ix_trip_itinerary_apply_history_itinerary_id'), table_name='trip_itinerary_apply_history')
    op.drop_index(op.f('ix_trip_itinerary_apply_history_trip_id'), table_name='trip_itinerary_apply_history')
    op.drop_index(op.f('ix_trip_itinerary_apply_history_id'), table_name='trip_itinerary_apply_history')
    op.drop_table('trip_itinerary_apply_history')
