"""add audit timing

Revision ID: b3f1a2e9c847
Revises: ae1b2c3d4e5f
Create Date: 2026-04-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = 'b3f1a2e9c847'
down_revision: Union[str, Sequence[str], None] = 'ae1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New columns on mappingaudituser
    op.add_column('mappingaudituser', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('mappingaudituser', sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('mappingaudituser', sa.Column('duration_seconds', sa.Integer(), nullable=True))
    op.add_column('mappingaudituser', sa.Column('active_seconds', sa.Integer(), nullable=False, server_default='0'))

    # New table for per-session active-time chunks
    op.create_table(
        'auditsessionchunk',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_audit_id', sa.Integer(), sa.ForeignKey('mappingaudituser.id', ondelete='CASCADE'), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_auditsessionchunk_user_audit_id', 'auditsessionchunk', ['user_audit_id'])


def downgrade() -> None:
    op.drop_index('ix_auditsessionchunk_user_audit_id', table_name='auditsessionchunk')
    op.drop_table('auditsessionchunk')

    op.drop_column('mappingaudituser', 'active_seconds')
    op.drop_column('mappingaudituser', 'duration_seconds')
    op.drop_column('mappingaudituser', 'submitted_at')
    op.drop_column('mappingaudituser', 'started_at')
