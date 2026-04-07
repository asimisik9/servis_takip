"""perf: add index on students.organization_id for tenant filter performance

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-04-07 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'o9p0q1r2s3t4'
down_revision: Union[str, None] = 'n8o9p0q1r2s3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_students_organization_id', 'students', ['organization_id'])


def downgrade() -> None:
    op.drop_index('ix_students_organization_id', table_name='students')
