"""added emailverication

Revision ID: ef94801d33c5
Revises: 6549786505e1
Create Date: 2025-10-09 18:41:39.653339

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel                                 # New


# revision identifiers, used by Alembic.
revision: str = 'ef94801d33c5'
down_revision: Union[str, Sequence[str], None] = '6549786505e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
