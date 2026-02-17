"""add audit entities and user defined features

Revision ID: add_audit_entities_features
Revises: [PREVIOUS_REVISION]
Create Date: 2025-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'add_audit_entities_features'
down_revision: Union[str, Sequence[str], None] = None  # UPDATE THIS WITH YOUR LATEST REVISION
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Create MappingAuditEntities table
    op.create_table(
        'mappingauditentities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('audit_id', sa.Integer(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['audit_id'], ['audit.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create UserDefinedUnderlyingFeatures table
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

    # Create UserDefinedTargetFeatures table
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


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('userdefinedtargetfeatures')
    op.drop_table('userdefinedunderlyingfeatures')
    op.drop_table('mappingauditentities')
