"""add_trips_and_trip_stops

Revision ID: c7e2a4f9d1b6
Revises: a3f7c9e1b5d2
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e2a4f9d1b6'
down_revision: Union[str, Sequence[str], None] = 'a3f7c9e1b5d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('trips',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('total_distance_km', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trips_id'), 'trips', ['id'], unique=False)
    op.create_index(op.f('ix_trips_user_id'), 'trips', ['user_id'], unique=False)
    op.create_index(op.f('ix_trips_created_at'), 'trips', ['created_at'], unique=False)
    op.create_index('ix_trips_user_created', 'trips', ['user_id', 'created_at'], unique=False)

    op.create_table('trip_stops',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trip_id', sa.Integer(), nullable=False),
    sa.Column('place_id', sa.Integer(), nullable=False),
    sa.Column('day_index', sa.Integer(), nullable=False),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['place_id'], ['places.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trip_stops_id'), 'trip_stops', ['id'], unique=False)
    op.create_index(op.f('ix_trip_stops_trip_id'), 'trip_stops', ['trip_id'], unique=False)
    op.create_index(op.f('ix_trip_stops_place_id'), 'trip_stops', ['place_id'], unique=False)
    op.create_index('ix_trip_stops_trip_day_order', 'trip_stops', ['trip_id', 'day_index', 'order_index'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_trip_stops_trip_day_order', table_name='trip_stops')
    op.drop_index(op.f('ix_trip_stops_place_id'), table_name='trip_stops')
    op.drop_index(op.f('ix_trip_stops_trip_id'), table_name='trip_stops')
    op.drop_index(op.f('ix_trip_stops_id'), table_name='trip_stops')
    op.drop_table('trip_stops')

    op.drop_index('ix_trips_user_created', table_name='trips')
    op.drop_index(op.f('ix_trips_created_at'), table_name='trips')
    op.drop_index(op.f('ix_trips_user_id'), table_name='trips')
    op.drop_index(op.f('ix_trips_id'), table_name='trips')
    op.drop_table('trips')
