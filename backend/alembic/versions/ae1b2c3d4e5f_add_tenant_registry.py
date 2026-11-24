"""add tenant registry

Revision ID: ae1b2c3d4e5f
Revises: fc86b4aa3d65
Create Date: 2026-04-16

"""
from alembic import op
import sqlalchemy as sa

revision = 'ae1b2c3d4e5f'
down_revision = 'fc86b4aa3d65'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tenant',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('db_schema', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('contact_email', sa.String(), nullable=True),
    )


def downgrade():
    op.drop_table('tenant')
