"""student organization phase B constraints

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-02-11 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "j4k5l6m7n8o9"
down_revision: Union[str, None] = "i3j4k5l6m7n8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase B data-fix:
    # 1) Backfill students.organization_id from related school when possible.
    op.execute(
        """
        UPDATE students AS s
        SET organization_id = sc.organization_id
        FROM schools AS sc
        WHERE s.organization_id IS NULL
          AND s.school_id = sc.id
          AND sc.organization_id IS NOT NULL
        """
    )

    # 2) If there is exactly one organization in DB, assign remaining NULL students to it.
    op.execute(
        """
        DO $$
        DECLARE
            org_count integer;
            single_org_id varchar;
        BEGIN
            SELECT COUNT(*), MIN(id)
            INTO org_count, single_org_id
            FROM organizations;

            IF org_count = 1 THEN
                UPDATE students
                SET organization_id = single_org_id
                WHERE organization_id IS NULL;
            END IF;
        END $$;
        """
    )

    # 3) Enforce NOT NULL only if legacy data is fully backfilled.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM students WHERE organization_id IS NULL
            ) THEN
                ALTER TABLE students
                ALTER COLUMN organization_id SET NOT NULL;
            END IF;
        END $$;
        """
    )

    # Enforce user role/org matrix for new writes without breaking legacy rows.
    op.execute(
        """
        ALTER TABLE users
        ADD CONSTRAINT ck_users_role_organization_matrix
        CHECK (
            (
                role::text = 'super_admin'
                AND organization_id IS NULL
            )
            OR
            (
                role::text IN ('admin', 'sofor', 'veli')
                AND organization_id IS NOT NULL
            )
        ) NOT VALID
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role_organization_matrix", "users", type_="check")
    op.alter_column(
        "students",
        "organization_id",
        existing_type=sa.String(),
        nullable=True,
    )
