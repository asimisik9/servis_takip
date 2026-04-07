"""perf: add missing indexes on schools.organization_id, buses.school_id, users composite

Revision ID: p0q1r2s3t4u5
Revises: o9p0q1r2s3t4
Create Date: 2026-04-07 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'p0q1r2s3t4u5'
down_revision: Union[str, None] = 'o9p0q1r2s3t4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tenant filter on schools (used in bus queries joining schools.organization_id)
    op.create_index('ix_schools_organization_id', 'schools', ['organization_id'])
    # Bus lookup by school (admin bus listing by school)
    op.create_index('ix_buses_school_id', 'buses', ['school_id'])
    # Composite index for cross-tenant user lookup (id + org guard)
    op.create_index('ix_users_id_organization_id', 'users', ['id', 'organization_id'])


def downgrade() -> None:
    op.drop_index('ix_users_id_organization_id', table_name='users')
    op.drop_index('ix_buses_school_id', table_name='buses')
    op.drop_index('ix_schools_organization_id', table_name='schools')
