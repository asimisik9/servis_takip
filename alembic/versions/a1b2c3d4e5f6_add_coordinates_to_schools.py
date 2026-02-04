"""add coordinates to schools

Revision ID: a1b2c3d4e5f6
Revises: d22a3dbf8bd0
Create Date: 2025-06-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd22a3dbf8bd0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add latitude and longitude columns to schools table."""
    op.add_column('schools', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('schools', sa.Column('longitude', sa.Float(), nullable=True))


def downgrade() -> None:
    """Remove latitude and longitude columns from schools table."""
    op.drop_column('schools', 'longitude')
    op.drop_column('schools', 'latitude')
