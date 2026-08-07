"""add_trip_optimizer

Revision ID: f2a8c5e91b3d
Revises: d49decdb0665
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a8c5e91b3d'
down_revision: Union[str, Sequence[str], None] = 'd49decdb0665'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('places', sa.Column('opening_hours', sa.String(), nullable=True))

    op.create_table('trip_itineraries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trip_id', sa.Integer(), nullable=False),
    sa.Column('strategy_name', sa.String(), nullable=False),
    sa.Column('optimization_score', sa.Float(), nullable=False),
    sa.Column('total_distance_km', sa.Float(), nullable=False),
    sa.Column('total_travel_time_minutes', sa.Float(), nullable=False),
    sa.Column('params', sa.JSON(), nullable=True),
    sa.Column('warnings', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trip_itineraries_id'), 'trip_itineraries', ['id'], unique=False)
    op.create_index(op.f('ix_trip_itineraries_trip_id'), 'trip_itineraries', ['trip_id'], unique=False)
    op.create_index(op.f('ix_trip_itineraries_created_at'), 'trip_itineraries', ['created_at'], unique=False)
    op.create_index('ix_trip_itineraries_trip_created', 'trip_itineraries', ['trip_id', 'created_at'], unique=False)

    op.create_table('trip_itinerary_stops',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('itinerary_id', sa.Integer(), nullable=False),
    sa.Column('place_id', sa.Integer(), nullable=True),
    sa.Column('day_index', sa.Integer(), nullable=False),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.Column('arrival_time', sa.String(), nullable=True),
    sa.Column('departure_time', sa.String(), nullable=True),
    sa.Column('visit_duration_minutes', sa.Integer(), nullable=False),
    sa.Column('travel_time_to_next_minutes', sa.Float(), nullable=True),
    sa.Column('travel_distance_to_next_km', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['itinerary_id'], ['trip_itineraries.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['place_id'], ['places.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trip_itinerary_stops_id'), 'trip_itinerary_stops', ['id'], unique=False)
    op.create_index(op.f('ix_trip_itinerary_stops_itinerary_id'), 'trip_itinerary_stops', ['itinerary_id'], unique=False)
    op.create_index(op.f('ix_trip_itinerary_stops_place_id'), 'trip_itinerary_stops', ['place_id'], unique=False)
    op.create_index(
        'ix_itinerary_stops_itinerary_day_order', 'trip_itinerary_stops',
        ['itinerary_id', 'day_index', 'order_index'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_itinerary_stops_itinerary_day_order', table_name='trip_itinerary_stops')
    op.drop_index(op.f('ix_trip_itinerary_stops_place_id'), table_name='trip_itinerary_stops')
    op.drop_index(op.f('ix_trip_itinerary_stops_itinerary_id'), table_name='trip_itinerary_stops')
    op.drop_index(op.f('ix_trip_itinerary_stops_id'), table_name='trip_itinerary_stops')
    op.drop_table('trip_itinerary_stops')

    op.drop_index('ix_trip_itineraries_trip_created', table_name='trip_itineraries')
    op.drop_index(op.f('ix_trip_itineraries_created_at'), table_name='trip_itineraries')
    op.drop_index(op.f('ix_trip_itineraries_trip_id'), table_name='trip_itineraries')
    op.drop_index(op.f('ix_trip_itineraries_id'), table_name='trip_itineraries')
    op.drop_table('trip_itineraries')

    op.drop_column('places', 'opening_hours')
