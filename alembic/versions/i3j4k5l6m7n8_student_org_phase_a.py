"""student organization phase A

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-02-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "i3j4k5l6m7n8"
down_revision: Union[str, None] = "h2i3j4k5l6m7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) students.organization_id (nullable in phase A)
    op.add_column("students", sa.Column("organization_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_students_organization_id",
        "students",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_students_organization_id", "students", ["organization_id"])

    # 2) students.school_id optional
    op.alter_column(
        "students",
        "school_id",
        existing_type=sa.String(),
        nullable=True,
    )

    # 3) Pre-cutover violation/reporting views
    op.execute(
        """
        CREATE OR REPLACE VIEW vw_users_role_org_violations AS
        SELECT
            u.id,
            u.email,
            u.role::text AS role,
            u.organization_id
        FROM users u
        WHERE
            (u.role::text = 'super_admin' AND u.organization_id IS NOT NULL)
            OR
            (u.role::text IN ('admin', 'sofor', 'veli') AND u.organization_id IS NULL)
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW vw_students_missing_org AS
        SELECT
            s.id,
            s.student_number,
            s.full_name,
            s.school_id
        FROM students s
        WHERE s.organization_id IS NULL
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW vw_cross_tenant_parent_student_relations AS
        SELECT
            psr.id,
            psr.parent_id,
            psr.student_id,
            p.organization_id AS parent_organization_id,
            s.organization_id AS student_organization_id
        FROM parent_student_relations psr
        JOIN users p ON p.id = psr.parent_id
        JOIN students s ON s.id = psr.student_id
        WHERE
            p.organization_id IS NULL
            OR s.organization_id IS NULL
            OR p.organization_id <> s.organization_id
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW vw_cross_tenant_student_bus_assignments AS
        SELECT
            sba.id,
            sba.student_id,
            sba.bus_id,
            s.organization_id AS student_organization_id,
            b.organization_id AS bus_organization_id
        FROM student_bus_assignments sba
        JOIN students s ON s.id = sba.student_id
        JOIN buses b ON b.id = sba.bus_id
        WHERE
            s.organization_id IS NULL
            OR b.organization_id IS NULL
            OR s.organization_id <> b.organization_id
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vw_cross_tenant_student_bus_assignments")
    op.execute("DROP VIEW IF EXISTS vw_cross_tenant_parent_student_relations")
    op.execute("DROP VIEW IF EXISTS vw_students_missing_org")
    op.execute("DROP VIEW IF EXISTS vw_users_role_org_violations")

    op.alter_column(
        "students",
        "school_id",
        existing_type=sa.String(),
        nullable=False,
    )

    op.drop_index("ix_students_organization_id", table_name="students")
    op.drop_constraint("fk_students_organization_id", "students", type_="foreignkey")
    op.drop_column("students", "organization_id")
