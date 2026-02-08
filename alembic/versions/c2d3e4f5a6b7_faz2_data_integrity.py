"""faz2 data integrity - FK ondelete, unique constraints, nullable driver

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================
    # H8: Make buses.current_driver_id nullable
    # ==========================================
    op.alter_column('buses', 'current_driver_id',
                    existing_type=sa.String(),
                    nullable=True)

    # ==========================================
    # H7: Add unique constraints
    # ==========================================
    op.create_unique_constraint('uq_parent_student', 'parent_student_relations', ['parent_id', 'student_id'])
    op.create_unique_constraint('uq_bus_student', 'student_bus_assignments', ['bus_id', 'student_id'])
    op.create_unique_constraint('uq_student_absence_date', 'absences', ['student_id', 'absence_date'])

    # ==========================================
    # C4: Add ondelete to all foreign keys
    # Each FK needs to be dropped and recreated with ondelete
    # ==========================================

    # --- buses ---
    # buses.school_id -> RESTRICT
    op.drop_constraint('buses_school_id_fkey', 'buses', type_='foreignkey')
    op.create_foreign_key('buses_school_id_fkey', 'buses', 'schools', ['school_id'], ['id'], ondelete='RESTRICT')

    # buses.current_driver_id -> SET NULL
    op.drop_constraint('buses_current_driver_id_fkey', 'buses', type_='foreignkey')
    op.create_foreign_key('buses_current_driver_id_fkey', 'buses', 'users', ['current_driver_id'], ['id'], ondelete='SET NULL')

    # --- schools ---
    # schools.contact_person_id -> RESTRICT
    op.drop_constraint('schools_contact_person_id_fkey', 'schools', type_='foreignkey')
    op.create_foreign_key('schools_contact_person_id_fkey', 'schools', 'users', ['contact_person_id'], ['id'], ondelete='RESTRICT')

    # --- students ---
    # students.school_id -> RESTRICT
    op.drop_constraint('students_school_id_fkey', 'students', type_='foreignkey')
    op.create_foreign_key('students_school_id_fkey', 'students', 'schools', ['school_id'], ['id'], ondelete='RESTRICT')

    # --- parent_student_relations ---
    op.drop_constraint('parent_student_relations_parent_id_fkey', 'parent_student_relations', type_='foreignkey')
    op.create_foreign_key('parent_student_relations_parent_id_fkey', 'parent_student_relations', 'users', ['parent_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('parent_student_relations_student_id_fkey', 'parent_student_relations', type_='foreignkey')
    op.create_foreign_key('parent_student_relations_student_id_fkey', 'parent_student_relations', 'students', ['student_id'], ['id'], ondelete='CASCADE')

    # --- student_bus_assignments ---
    op.drop_constraint('student_bus_assignments_bus_id_fkey', 'student_bus_assignments', type_='foreignkey')
    op.create_foreign_key('student_bus_assignments_bus_id_fkey', 'student_bus_assignments', 'buses', ['bus_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('student_bus_assignments_student_id_fkey', 'student_bus_assignments', type_='foreignkey')
    op.create_foreign_key('student_bus_assignments_student_id_fkey', 'student_bus_assignments', 'students', ['student_id'], ['id'], ondelete='CASCADE')

    # --- attendance_logs ---
    op.drop_constraint('attendance_logs_student_id_fkey', 'attendance_logs', type_='foreignkey')
    op.create_foreign_key('attendance_logs_student_id_fkey', 'attendance_logs', 'students', ['student_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('attendance_logs_driver_id_fkey', 'attendance_logs', type_='foreignkey')
    op.create_foreign_key('attendance_logs_driver_id_fkey', 'attendance_logs', 'users', ['driver_id'], ['id'], ondelete='RESTRICT')

    op.drop_constraint('attendance_logs_bus_id_fkey', 'attendance_logs', type_='foreignkey')
    op.create_foreign_key('attendance_logs_bus_id_fkey', 'attendance_logs', 'buses', ['bus_id'], ['id'], ondelete='RESTRICT')

    # --- notifications ---
    op.drop_constraint('notifications_recipient_id_fkey', 'notifications', type_='foreignkey')
    op.create_foreign_key('notifications_recipient_id_fkey', 'notifications', 'users', ['recipient_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('notifications_student_id_fkey', 'notifications', type_='foreignkey')
    op.create_foreign_key('notifications_student_id_fkey', 'notifications', 'students', ['student_id'], ['id'], ondelete='SET NULL')

    # --- bus_locations ---
    op.drop_constraint('bus_locations_bus_id_fkey', 'bus_locations', type_='foreignkey')
    op.create_foreign_key('bus_locations_bus_id_fkey', 'bus_locations', 'buses', ['bus_id'], ['id'], ondelete='CASCADE')

    # --- absences ---
    op.drop_constraint('absences_student_id_fkey', 'absences', type_='foreignkey')
    op.create_foreign_key('absences_student_id_fkey', 'absences', 'students', ['student_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('absences_parent_id_fkey', 'absences', type_='foreignkey')
    op.create_foreign_key('absences_parent_id_fkey', 'absences', 'users', ['parent_id'], ['id'], ondelete='CASCADE')

    # --- audit_logs ---
    op.drop_constraint('audit_logs_user_id_fkey', 'audit_logs', type_='foreignkey')
    op.create_foreign_key('audit_logs_user_id_fkey', 'audit_logs', 'users', ['user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # Remove unique constraints
    op.drop_constraint('uq_parent_student', 'parent_student_relations', type_='unique')
    op.drop_constraint('uq_bus_student', 'student_bus_assignments', type_='unique')
    op.drop_constraint('uq_student_absence_date', 'absences', type_='unique')

    # Make buses.current_driver_id NOT NULL again
    op.alter_column('buses', 'current_driver_id',
                    existing_type=sa.String(),
                    nullable=False)

    # Revert all FK constraints to no ondelete (drop and recreate without ondelete)
    # buses
    op.drop_constraint('buses_school_id_fkey', 'buses', type_='foreignkey')
    op.create_foreign_key('buses_school_id_fkey', 'buses', 'schools', ['school_id'], ['id'])
    op.drop_constraint('buses_current_driver_id_fkey', 'buses', type_='foreignkey')
    op.create_foreign_key('buses_current_driver_id_fkey', 'buses', 'users', ['current_driver_id'], ['id'])

    # schools
    op.drop_constraint('schools_contact_person_id_fkey', 'schools', type_='foreignkey')
    op.create_foreign_key('schools_contact_person_id_fkey', 'schools', 'users', ['contact_person_id'], ['id'])

    # students
    op.drop_constraint('students_school_id_fkey', 'students', type_='foreignkey')
    op.create_foreign_key('students_school_id_fkey', 'students', 'schools', ['school_id'], ['id'])

    # parent_student_relations
    op.drop_constraint('parent_student_relations_parent_id_fkey', 'parent_student_relations', type_='foreignkey')
    op.create_foreign_key('parent_student_relations_parent_id_fkey', 'parent_student_relations', 'users', ['parent_id'], ['id'])
    op.drop_constraint('parent_student_relations_student_id_fkey', 'parent_student_relations', type_='foreignkey')
    op.create_foreign_key('parent_student_relations_student_id_fkey', 'parent_student_relations', 'students', ['student_id'], ['id'])

    # student_bus_assignments
    op.drop_constraint('student_bus_assignments_bus_id_fkey', 'student_bus_assignments', type_='foreignkey')
    op.create_foreign_key('student_bus_assignments_bus_id_fkey', 'student_bus_assignments', 'buses', ['bus_id'], ['id'])
    op.drop_constraint('student_bus_assignments_student_id_fkey', 'student_bus_assignments', type_='foreignkey')
    op.create_foreign_key('student_bus_assignments_student_id_fkey', 'student_bus_assignments', 'students', ['student_id'], ['id'])

    # attendance_logs
    op.drop_constraint('attendance_logs_student_id_fkey', 'attendance_logs', type_='foreignkey')
    op.create_foreign_key('attendance_logs_student_id_fkey', 'attendance_logs', 'students', ['student_id'], ['id'])
    op.drop_constraint('attendance_logs_driver_id_fkey', 'attendance_logs', type_='foreignkey')
    op.create_foreign_key('attendance_logs_driver_id_fkey', 'attendance_logs', 'users', ['driver_id'], ['id'])
    op.drop_constraint('attendance_logs_bus_id_fkey', 'attendance_logs', type_='foreignkey')
    op.create_foreign_key('attendance_logs_bus_id_fkey', 'attendance_logs', 'buses', ['bus_id'], ['id'])

    # notifications
    op.drop_constraint('notifications_recipient_id_fkey', 'notifications', type_='foreignkey')
    op.create_foreign_key('notifications_recipient_id_fkey', 'notifications', 'users', ['recipient_id'], ['id'])
    op.drop_constraint('notifications_student_id_fkey', 'notifications', type_='foreignkey')
    op.create_foreign_key('notifications_student_id_fkey', 'notifications', 'students', ['student_id'], ['id'])

    # bus_locations
    op.drop_constraint('bus_locations_bus_id_fkey', 'bus_locations', type_='foreignkey')
    op.create_foreign_key('bus_locations_bus_id_fkey', 'bus_locations', 'buses', ['bus_id'], ['id'])

    # absences
    op.drop_constraint('absences_student_id_fkey', 'absences', type_='foreignkey')
    op.create_foreign_key('absences_student_id_fkey', 'absences', 'students', ['student_id'], ['id'])
    op.drop_constraint('absences_parent_id_fkey', 'absences', type_='foreignkey')
    op.create_foreign_key('absences_parent_id_fkey', 'absences', 'users', ['parent_id'], ['id'])

    # audit_logs
    op.drop_constraint('audit_logs_user_id_fkey', 'audit_logs', type_='foreignkey')
    op.create_foreign_key('audit_logs_user_id_fkey', 'audit_logs', 'users', ['user_id'], ['id'])
