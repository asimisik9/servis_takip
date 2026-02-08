"""Add multi-tenancy support

Revision ID: g1h2i3j4k5l6
Revises: f8a9b2c3d4e5_add_fcm_and_notifications
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.Enum('school', 'transport_company', name='organizationtype'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_organizations_type', 'organizations', ['type'])
    op.create_index('ix_organizations_name', 'organizations', ['name'])

    # 2. Create school_company_contracts table
    op.create_table(
        'school_company_contracts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('school_org_id', sa.String(), nullable=False),
        sa.Column('company_org_id', sa.String(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['school_org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('school_org_id', 'company_org_id', name='uq_school_company_contract')
    )
    op.create_index('ix_contracts_school_org_id', 'school_company_contracts', ['school_org_id'])
    op.create_index('ix_contracts_company_org_id', 'school_company_contracts', ['company_org_id'])
    op.create_index('ix_contracts_is_active', 'school_company_contracts', ['is_active'])

    # 3. Add organization_id to users table
    op.add_column('users', sa.Column('organization_id', sa.String(), nullable=True))
    op.create_foreign_key(
        'fk_users_organization_id',
        'users', 'organizations',
        ['organization_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_users_organization_id', 'users', ['organization_id'])

    # 4. Add organization_id to schools table
    op.add_column('schools', sa.Column('organization_id', sa.String(), nullable=True))
    op.create_foreign_key(
        'fk_schools_organization_id',
        'schools', 'organizations',
        ['organization_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_schools_organization_id', 'schools', ['organization_id'])

    # 5. Add organization_id to buses table
    op.add_column('buses', sa.Column('organization_id', sa.String(), nullable=True))
    op.create_foreign_key(
        'fk_buses_organization_id',
        'buses', 'organizations',
        ['organization_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_buses_organization_id', 'buses', ['organization_id'])


def downgrade() -> None:
    # Remove from buses
    op.drop_index('ix_buses_organization_id', 'buses')
    op.drop_constraint('fk_buses_organization_id', 'buses', type_='foreignkey')
    op.drop_column('buses', 'organization_id')

    # Remove from schools
    op.drop_index('ix_schools_organization_id', 'schools')
    op.drop_constraint('fk_schools_organization_id', 'schools', type_='foreignkey')
    op.drop_column('schools', 'organization_id')

    # Remove from users
    op.drop_index('ix_users_organization_id', 'users')
    op.drop_constraint('fk_users_organization_id', 'users', type_='foreignkey')
    op.drop_column('users', 'organization_id')

    # Drop school_company_contracts table
    op.drop_index('ix_contracts_is_active', 'school_company_contracts')
    op.drop_index('ix_contracts_company_org_id', 'school_company_contracts')
    op.drop_index('ix_contracts_school_org_id', 'school_company_contracts')
    op.drop_table('school_company_contracts')

    # Drop organizations table
    op.drop_index('ix_organizations_name', 'organizations')
    op.drop_index('ix_organizations_type', 'organizations')
    op.drop_table('organizations')
    
    # Drop enum type
    sa.Enum(name='organizationtype').drop(op.get_bind(), checkfirst=True)
