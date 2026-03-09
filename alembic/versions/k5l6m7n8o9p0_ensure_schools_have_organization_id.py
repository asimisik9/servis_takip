"""ensure schools.organization_id exists and is indexed

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-02-11 16:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "k5l6m7n8o9p0"
down_revision: Union[str, None] = "j4k5l6m7n8o9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = :table_name
                  AND column_name = :column_name
            )
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return bool(result.scalar())


def _index_exists(conn, index_name: str) -> bool:
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE indexname = :index_name
            )
            """
        ),
        {"index_name": index_name},
    )
    return bool(result.scalar())


def _fk_exists(conn, table_name: str, constraint_name: str) -> bool:
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE table_name = :table_name
                  AND constraint_name = :constraint_name
                  AND constraint_type = 'FOREIGN KEY'
            )
            """
        ),
        {"table_name": table_name, "constraint_name": constraint_name},
    )
    return bool(result.scalar())


def upgrade() -> None:
    conn = op.get_bind()

    if not _column_exists(conn, "schools", "organization_id"):
        op.add_column("schools", sa.Column("organization_id", sa.String(), nullable=True))

    # Backfill: derive school organization from contact person when available.
    op.execute(
        """
        UPDATE schools AS s
        SET organization_id = u.organization_id
        FROM users AS u
        WHERE s.organization_id IS NULL
          AND s.contact_person_id = u.id
          AND u.organization_id IS NOT NULL
        """
    )

    # Fallback: if platform has exactly one organization, bind remaining NULL schools to it.
    op.execute(
        """
        WITH single_org AS (
            SELECT MIN(id) AS id
            FROM organizations
            HAVING COUNT(*) = 1
        )
        UPDATE schools AS s
        SET organization_id = single_org.id
        FROM single_org
        WHERE s.organization_id IS NULL
        """
    )

    if not _fk_exists(conn, "schools", "fk_schools_organization_id"):
        op.create_foreign_key(
            "fk_schools_organization_id",
            "schools",
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _index_exists(conn, "ix_schools_organization_id"):
        op.create_index("ix_schools_organization_id", "schools", ["organization_id"])


def downgrade() -> None:
    # Intentionally no-op to avoid destructive rollback on shared environments.
    pass
