"""empty message

Revision ID: a10a65161996
Revises: 870aeda99117, f6c21fc4cd47
Create Date: 2025-09-18 10:16:29.318563

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel                                 # New


# revision identifiers, used by Alembic.
revision: str = 'a10a65161996'
down_revision: Union[str, Sequence[str], None] = ('870aeda99117', 'f6c21fc4cd47')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
