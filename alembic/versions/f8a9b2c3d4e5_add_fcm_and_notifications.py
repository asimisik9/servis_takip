"""add fcm_token and enhance notifications

Revision ID: f8a9b2c3d4e5
Revises: a1b2c3d4e5f6
Create Date: 2026-02-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a9b2c3d4e5'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.columns "
        "  WHERE table_name = :table AND column_name = :column"
        ")"
    ), {"table": table, "column": column})
    return result.scalar()


def upgrade() -> None:
    conn = op.get_bind()

    # User tablosuna fcm_token ekle
    if not _column_exists(conn, 'users', 'fcm_token'):
        op.add_column('users', sa.Column('fcm_token', sa.String(), nullable=True))

    # Notification tablosuna yeni alanlar ekle
    if not _column_exists(conn, 'notifications', 'student_id'):
        op.add_column('notifications', sa.Column('student_id', sa.String(), sa.ForeignKey('students.id'), nullable=True))
    if not _column_exists(conn, 'notifications', 'title'):
        op.add_column('notifications', sa.Column('title', sa.String(), nullable=True, server_default='Servis Now'))
    if not _column_exists(conn, 'notifications', 'is_read'):
        op.add_column('notifications', sa.Column('is_read', sa.Boolean(), nullable=True, server_default='false'))

    # NotificationType enum oluştur
    notification_type_enum = sa.Enum(
        'eve_varis_eta', 'evden_alim_eta', 'okula_varis', 'eve_birakildi', 'genel',
        name='notificationtype'
    )
    notification_type_enum.create(op.get_bind(), checkfirst=True)
    
    if not _column_exists(conn, 'notifications', 'notification_type'):
        op.add_column('notifications', sa.Column(
            'notification_type',
            notification_type_enum,
            nullable=True,
            server_default='genel'
        ))

    # NotificationStatus enum'a 'beklemede' ekle
    op.execute("ALTER TYPE notificationstatus ADD VALUE IF NOT EXISTS 'beklemede'")


def downgrade() -> None:
    op.drop_column('notifications', 'notification_type')
    op.drop_column('notifications', 'is_read')
    op.drop_column('notifications', 'title')
    op.drop_column('notifications', 'student_id')
    op.drop_column('users', 'fcm_token')

    # Enum temizliği
    op.execute("DROP TYPE IF EXISTS notificationtype")
