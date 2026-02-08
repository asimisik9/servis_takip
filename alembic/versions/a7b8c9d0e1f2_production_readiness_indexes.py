"""production readiness: indexes, speed nullable, cleanup

Revision ID: a7b8c9d0e1f2
Revises: f8a9b2c3d4e5
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f8a9b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create absences table (if not already created by create_tables) ──
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'absences')"
    ))
    absences_exists = result.scalar()
    
    if not absences_exists:
        op.create_table(
            'absences',
            sa.Column('id', sa.String(), primary_key=True),
            sa.Column('student_id', sa.String(), sa.ForeignKey('students.id'), nullable=False),
            sa.Column('parent_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('absence_date', sa.Date(), nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )
    
    op.create_index('ix_absences_student_date', 'absences', ['student_id', 'absence_date'], unique=True, if_not_exists=True)

    # ── Make bus_locations.speed nullable ──
    op.alter_column('bus_locations', 'speed',
                     existing_type=sa.DECIMAL(),
                     nullable=True)

    # ── Performance indexes (using raw SQL for IF NOT EXISTS + DESC support) ──
    
    # bus_locations: lookup by bus_id + ORDER BY timestamp DESC (most recent location)
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_bus_locations_bus_id_timestamp "
        "ON bus_locations (bus_id, timestamp DESC)"
    ))
    
    # bus_locations: cleanup old rows by timestamp
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_bus_locations_timestamp "
        "ON bus_locations (timestamp)"
    ))
    
    # attendance_logs: filter by student + date range
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_attendance_logs_student_id_log_time "
        "ON attendance_logs (student_id, log_time DESC)"
    ))
    
    # attendance_logs: filter by bus_id
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_attendance_logs_bus_id "
        "ON attendance_logs (bus_id)"
    ))
    
    # notifications: user's notifications sorted by date
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_notifications_recipient_id_created_at "
        "ON notifications (recipient_id, created_at DESC)"
    ))
    
    # notifications: unread count optimization
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_notifications_recipient_unread "
        "ON notifications (recipient_id, is_read)"
    ))
    
    # parent_student_relations: lookup by parent
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_parent_student_relations_parent_id "
        "ON parent_student_relations (parent_id)"
    ))
    
    # parent_student_relations: lookup by student
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_parent_student_relations_student_id "
        "ON parent_student_relations (student_id)"
    ))
    
    # student_bus_assignments: lookup by student
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_student_bus_assignments_student_id "
        "ON student_bus_assignments (student_id)"
    ))
    
    # student_bus_assignments: lookup by bus
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_student_bus_assignments_bus_id "
        "ON student_bus_assignments (bus_id)"
    ))


def downgrade() -> None:
    op.drop_index('ix_student_bus_assignments_bus_id', table_name='student_bus_assignments')
    op.drop_index('ix_student_bus_assignments_student_id', table_name='student_bus_assignments')
    op.drop_index('ix_parent_student_relations_student_id', table_name='parent_student_relations')
    op.drop_index('ix_parent_student_relations_parent_id', table_name='parent_student_relations')
    op.drop_index('ix_notifications_recipient_unread', table_name='notifications')
    op.drop_index('ix_notifications_recipient_id_created_at', table_name='notifications')
    op.drop_index('ix_attendance_logs_bus_id', table_name='attendance_logs')
    op.drop_index('ix_attendance_logs_student_id_log_time', table_name='attendance_logs')
    op.drop_index('ix_bus_locations_timestamp', table_name='bus_locations')
    op.drop_index('ix_bus_locations_bus_id_timestamp', table_name='bus_locations')
    
    op.alter_column('bus_locations', 'speed',
                     existing_type=sa.DECIMAL(),
                     nullable=False)
    
    op.drop_index('ix_absences_student_date', table_name='absences')
    op.drop_table('absences')
