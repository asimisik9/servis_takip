"""add super_admin role

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2024-02-08 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h2i3j4k5l6m7'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: Add new enum value to existing enum type
    # We need to add the value outside of a transaction for asyncpg
    connection = op.get_bind()
    
    # Check if super_admin already exists in enum
    result = connection.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
            AND enumlabel = 'super_admin'
        )
    """))
    exists = result.scalar()
    
    if not exists:
        # Add the new enum value
        op.execute("ALTER TYPE userrole ADD VALUE 'super_admin'")
        # Commit this change before using the new value
        op.execute("COMMIT")
    
    # Now update existing admin users (with organization_id = NULL) to super_admin
    op.execute("""
        UPDATE users 
        SET role = 'super_admin' 
        WHERE role = 'admin' AND organization_id IS NULL
    """)


def downgrade() -> None:
    # Revert super_admin back to admin
    op.execute("""
        UPDATE users 
        SET role = 'admin' 
        WHERE role = 'super_admin'
    """)
    
    # Note: PostgreSQL does not support removing enum values easily
    # The super_admin value will remain in the enum type
