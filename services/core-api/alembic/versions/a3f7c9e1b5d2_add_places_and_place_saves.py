"""add_places_and_place_saves

Revision ID: a3f7c9e1b5d2
Revises: b4f8e1a9c2d3
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c9e1b5d2'
down_revision: Union[str, Sequence[str], None] = 'b4f8e1a9c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('places',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('name_key', sa.String(), nullable=False),
    sa.Column('lat', sa.Float(), nullable=False),
    sa.Column('lng', sa.Float(), nullable=False),
    sa.Column('city', sa.String(), nullable=True),
    sa.Column('address', sa.String(), nullable=True),
    sa.Column('category', sa.String(), nullable=True),
    sa.Column('first_seen_video_id', sa.Integer(), nullable=True),
    sa.Column('save_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['first_seen_video_id'], ['videos.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_places_id'), 'places', ['id'], unique=False)
    op.create_index(op.f('ix_places_name_key'), 'places', ['name_key'], unique=False)
    op.create_index(op.f('ix_places_city'), 'places', ['city'], unique=False)
    op.create_index(op.f('ix_places_category'), 'places', ['category'], unique=False)
    op.create_index(op.f('ix_places_created_at'), 'places', ['created_at'], unique=False)
    op.create_index('ix_places_city_name_key', 'places', ['city', 'name_key'], unique=False)

    op.create_table('place_saves',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('place_id', sa.Integer(), nullable=False),
    sa.Column('video_id', sa.Integer(), nullable=True),
    sa.Column('saved_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['place_id'], ['places.id'], ),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'place_id', name='uq_place_saves_user_place')
    )
    op.create_index(op.f('ix_place_saves_id'), 'place_saves', ['id'], unique=False)
    op.create_index(op.f('ix_place_saves_user_id'), 'place_saves', ['user_id'], unique=False)
    op.create_index(op.f('ix_place_saves_place_id'), 'place_saves', ['place_id'], unique=False)
    op.create_index(op.f('ix_place_saves_saved_at'), 'place_saves', ['saved_at'], unique=False)
    op.create_index('ix_place_saves_user_saved', 'place_saves', ['user_id', 'saved_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_place_saves_user_saved', table_name='place_saves')
    op.drop_index(op.f('ix_place_saves_saved_at'), table_name='place_saves')
    op.drop_index(op.f('ix_place_saves_place_id'), table_name='place_saves')
    op.drop_index(op.f('ix_place_saves_user_id'), table_name='place_saves')
    op.drop_index(op.f('ix_place_saves_id'), table_name='place_saves')
    op.drop_table('place_saves')

    op.drop_index('ix_places_city_name_key', table_name='places')
    op.drop_index(op.f('ix_places_created_at'), table_name='places')
    op.drop_index(op.f('ix_places_category'), table_name='places')
    op.drop_index(op.f('ix_places_city'), table_name='places')
    op.drop_index(op.f('ix_places_name_key'), table_name='places')
    op.drop_index(op.f('ix_places_id'), table_name='places')
    op.drop_table('places')
