"""add mcp_tool_name to modelmetadata

Revision ID: fc86b4aa3d65
Revises: 294458739e75
Create Date: 2026-03-27 11:17:29.037312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel                                 # New


# revision identifiers, used by Alembic.
revision: str = 'fc86b4aa3d65'
down_revision: Union[str, Sequence[str], None] = '294458739e75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add mcp_tool_name column and backfill known model records."""
    op.add_column('modelmetadata', sa.Column('mcp_tool_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    # Backfill mcp_tool_name and correct locations for existing model rows
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE modelmetadata SET mcp_tool_name = 'predict_attachment', "
        "location = 'http://sam-attachment-monitor:8002' "
        "WHERE name = 'SAM'"
    ))
    conn.execute(sa.text(
        "UPDATE modelmetadata SET mcp_tool_name = 'llm_inference' "
        "WHERE name = 'Universal LLM' OR name ILIKE '%universal%llm%'"
    ))
    conn.execute(sa.text(
        "UPDATE modelmetadata SET mcp_tool_name = 'predict_subjects', "
        "location = 'http://annif-api:8004' "
        "WHERE name = 'Annif' OR name ILIKE '%annif%'"
    ))


def downgrade() -> None:
    """Remove mcp_tool_name column (location changes are not reversed)."""
    op.drop_column('modelmetadata', 'mcp_tool_name')
