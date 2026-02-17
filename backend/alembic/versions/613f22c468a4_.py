"""empty message

Revision ID: 613f22c468a4
Revises: abf95e794d89, add_audit_entities_features
Create Date: 2025-10-20 11:49:25.546904

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel                                 # New


# revision identifiers, used by Alembic.
revision: str = '613f22c468a4'
down_revision: Union[str, Sequence[str], None] = ('abf95e794d89', 'add_audit_entities_features')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
