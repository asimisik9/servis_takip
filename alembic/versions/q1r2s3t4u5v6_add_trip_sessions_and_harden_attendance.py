"""attendance: add trip sessions, trip student state, and single-bus safety

Revision ID: q1r2s3t4u5v6
Revises: p0q1r2s3t4u5
Create Date: 2026-04-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "q1r2s3t4u5v6"
down_revision: Union[str, None] = "p0q1r2s3t4u5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


trip_type_enum = postgresql.ENUM("to_school", "from_school", name="triptype")
attendance_status_enum = postgresql.ENUM("indi", "bindi", name="attendancestatus", create_type=False)


def upgrade() -> None:
    conn = op.get_bind()
    duplicate_assignment = conn.execute(
        sa.text(
            """
            SELECT student_id
            FROM student_bus_assignments
            GROUP BY student_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate_assignment:
        raise RuntimeError(
            "Cannot enforce single active bus per student because duplicate student_bus_assignments exist. "
            "Clean up duplicate rows first."
        )

    trip_type_enum.create(conn, checkfirst=True)

    op.create_table(
        "trip_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bus_id", sa.String(), nullable=False),
        sa.Column("driver_id", sa.String(), nullable=True),
        sa.Column("trip_type", trip_type_enum, nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["bus_id"], ["buses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["driver_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bus_id", "trip_type", "service_date", name="uq_trip_session_bus_type_date"),
    )
    op.create_index("ix_trip_sessions_bus_id", "trip_sessions", ["bus_id"], unique=False)
    op.create_index("ix_trip_sessions_service_date", "trip_sessions", ["service_date"], unique=False)

    op.add_column("attendance_logs", sa.Column("trip_session_id", sa.String(), nullable=True))
    op.add_column("attendance_logs", sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("attendance_logs", sa.Column("idempotency_key", sa.String(), nullable=True))
    op.add_column("attendance_logs", sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("attendance_logs", sa.Column("reverted_by_driver_id", sa.String(), nullable=True))
    op.create_index("ix_attendance_logs_trip_session_id", "attendance_logs", ["trip_session_id"], unique=False)
    op.create_unique_constraint("uq_attendance_logs_idempotency_key", "attendance_logs", ["idempotency_key"])
    op.create_foreign_key(
        "fk_attendance_logs_trip_session_id",
        "attendance_logs",
        "trip_sessions",
        ["trip_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_attendance_logs_reverted_by_driver_id",
        "attendance_logs",
        "users",
        ["reverted_by_driver_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "trip_student_states",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("trip_session_id", sa.String(), nullable=False),
        sa.Column("student_id", sa.String(), nullable=False),
        sa.Column("last_status", attendance_status_enum, nullable=True),
        sa.Column("last_log_id", sa.String(), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("route_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["last_log_id"], ["attendance_logs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trip_session_id"], ["trip_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_session_id", "student_id", name="uq_trip_session_student"),
    )
    op.create_index("ix_trip_student_states_trip_session_id", "trip_student_states", ["trip_session_id"], unique=False)
    op.create_index("ix_trip_student_states_student_id", "trip_student_states", ["student_id"], unique=False)

    op.create_unique_constraint(
        "uq_student_single_bus_assignment",
        "student_bus_assignments",
        ["student_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_student_single_bus_assignment", "student_bus_assignments", type_="unique")

    op.drop_index("ix_trip_student_states_student_id", table_name="trip_student_states")
    op.drop_index("ix_trip_student_states_trip_session_id", table_name="trip_student_states")
    op.drop_table("trip_student_states")

    op.drop_constraint("fk_attendance_logs_trip_session_id", "attendance_logs", type_="foreignkey")
    op.drop_constraint("fk_attendance_logs_reverted_by_driver_id", "attendance_logs", type_="foreignkey")
    op.drop_constraint("uq_attendance_logs_idempotency_key", "attendance_logs", type_="unique")
    op.drop_index("ix_attendance_logs_trip_session_id", table_name="attendance_logs")
    op.drop_column("attendance_logs", "reverted_by_driver_id")
    op.drop_column("attendance_logs", "reverted_at")
    op.drop_column("attendance_logs", "idempotency_key")
    op.drop_column("attendance_logs", "recorded_at")
    op.drop_column("attendance_logs", "trip_session_id")

    op.drop_index("ix_trip_sessions_service_date", table_name="trip_sessions")
    op.drop_index("ix_trip_sessions_bus_id", table_name="trip_sessions")
    op.drop_table("trip_sessions")

    trip_type_enum.drop(op.get_bind(), checkfirst=True)
