"""add_trip_sharing

Revision ID: d49decdb0665
Revises: c7e2a4f9d1b6
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd49decdb0665'
down_revision: Union[str, Sequence[str], None] = 'c7e2a4f9d1b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    share_status = sa.Enum('pending', 'accepted', 'declined', 'expired', 'revoked', name='sharestatus')
    collaborator_role = sa.Enum('viewer', 'editor', name='collaboratorrole')

    op.create_table('trip_shares',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trip_id', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('role', collaborator_role, nullable=False),
    sa.Column('status', share_status, nullable=False),
    sa.Column('accepted_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('responded_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['accepted_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trip_shares_id'), 'trip_shares', ['id'], unique=False)
    op.create_index(op.f('ix_trip_shares_trip_id'), 'trip_shares', ['trip_id'], unique=False)
    op.create_index(op.f('ix_trip_shares_status'), 'trip_shares', ['status'], unique=False)
    op.create_index(op.f('ix_trip_shares_created_at'), 'trip_shares', ['created_at'], unique=False)
    op.create_index('ix_trip_shares_trip_status', 'trip_shares', ['trip_id', 'status'], unique=False)

    op.create_table('share_tokens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('share_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('max_uses', sa.Integer(), nullable=True),
    sa.Column('use_count', sa.Integer(), nullable=False),
    sa.Column('revoked_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['share_id'], ['trip_shares.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('share_id', name='uq_share_tokens_share_id'),
    sa.UniqueConstraint('token_hash', name='uq_share_tokens_token_hash')
    )
    op.create_index(op.f('ix_share_tokens_id'), 'share_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_share_tokens_share_id'), 'share_tokens', ['share_id'], unique=False)
    op.create_index(op.f('ix_share_tokens_token_hash'), 'share_tokens', ['token_hash'], unique=False)

    op.create_table('trip_collaborators',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trip_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', collaborator_role, nullable=False),
    sa.Column('share_id', sa.Integer(), nullable=True),
    sa.Column('joined_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['share_id'], ['trip_shares.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('trip_id', 'user_id', name='uq_trip_collaborators_trip_user')
    )
    op.create_index(op.f('ix_trip_collaborators_id'), 'trip_collaborators', ['id'], unique=False)
    op.create_index(op.f('ix_trip_collaborators_trip_id'), 'trip_collaborators', ['trip_id'], unique=False)
    op.create_index(op.f('ix_trip_collaborators_user'), 'trip_collaborators', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_trip_collaborators_user'), table_name='trip_collaborators')
    op.drop_index(op.f('ix_trip_collaborators_trip_id'), table_name='trip_collaborators')
    op.drop_index(op.f('ix_trip_collaborators_id'), table_name='trip_collaborators')
    op.drop_table('trip_collaborators')

    op.drop_index(op.f('ix_share_tokens_token_hash'), table_name='share_tokens')
    op.drop_index(op.f('ix_share_tokens_share_id'), table_name='share_tokens')
    op.drop_index(op.f('ix_share_tokens_id'), table_name='share_tokens')
    op.drop_table('share_tokens')

    op.drop_index('ix_trip_shares_trip_status', table_name='trip_shares')
    op.drop_index(op.f('ix_trip_shares_created_at'), table_name='trip_shares')
    op.drop_index(op.f('ix_trip_shares_status'), table_name='trip_shares')
    op.drop_index(op.f('ix_trip_shares_trip_id'), table_name='trip_shares')
    op.drop_index(op.f('ix_trip_shares_id'), table_name='trip_shares')
    op.drop_table('trip_shares')

    sa.Enum(name='sharestatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='collaboratorrole').drop(op.get_bind(), checkfirst=True)
