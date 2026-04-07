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
    op.execute("CREATE INDEX IF NOT EXISTS ix_schools_organization_id ON schools (organization_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_buses_school_id ON buses (school_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_id_organization_id ON users (id, organization_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_id_organization_id")
    op.execute("DROP INDEX IF EXISTS ix_buses_school_id")
    op.execute("DROP INDEX IF EXISTS ix_schools_organization_id")
