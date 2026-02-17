"""added password reset

Revision ID: 6771e6c3ea10
Revises: ef94801d33c5
Create Date: 2025-10-14 10:27:44.947053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel                                 # New


# revision identifiers, used by Alembic.
revision: str = '6771e6c3ea10'
down_revision: Union[str, Sequence[str], None] = 'ef94801d33c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
