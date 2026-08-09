"""add_trip_applied_itinerary

Revision ID: a7c3f091e8d5
Revises: f2a8c5e91b3d
Create Date: 2026-08-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3f091e8d5'
down_revision: Union[str, Sequence[str], None] = 'f2a8c5e91b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table: SQLite ALTER TABLE ile FK constraint eklemeyi
    # desteklemez (tablo yeniden oluşturmak gerekir) — batch mode bunu
    # Postgres'te normal bir ALTER'a, SQLite'ta tablo-yeniden-oluşturmaya
    # çevirir, ikisinde de aynı migration dosyası çalışır.
    with op.batch_alter_table('trips') as batch_op:
        batch_op.add_column(sa.Column('applied_itinerary_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('itinerary_applied_at', sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            'fk_trips_applied_itinerary_id', 'trip_itineraries',
            ['applied_itinerary_id'], ['id'], ondelete='SET NULL',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('trips') as batch_op:
        batch_op.drop_constraint('fk_trips_applied_itinerary_id', type_='foreignkey')
        batch_op.drop_column('itinerary_applied_at')
        batch_op.drop_column('applied_itinerary_id')
