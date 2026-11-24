"""drop unused user-defined feature tables

Removes the orphaned userdefinedunderlyingfeatures and userdefinedtargetfeatures
tables. Both were never wired into the application; user-specific features are
handled via the mappinguserauditfeatures / mappinguseraudittargetfeatures tables.

Revision ID: d3a1f7c2b8e4
Revises: b4e7d21a9c33
Create Date: 2026-07-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd3a1f7c2b8e4'
down_revision: Union[str, Sequence[str], None] = 'b3f1a2e9c847'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('userdefinedtargetfeatures')
    op.drop_table('userdefinedunderlyingfeatures')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        'userdefinedunderlyingfeatures',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('feature_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('data_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('audit_id', sa.Integer(), nullable=False),
        sa.Column('user_audit_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['audit_id'], ['audit.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_audit_id'], ['mappingaudituser.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'userdefinedtargetfeatures',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('target_feature', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('function_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('audit_id', sa.Integer(), nullable=False),
        sa.Column('user_audit_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['audit_id'], ['audit.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_audit_id'], ['mappingaudituser.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
