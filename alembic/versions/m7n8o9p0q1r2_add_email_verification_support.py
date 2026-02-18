"""add email verification columns and tokens table

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2026-02-18 20:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m7n8o9p0q1r2"
down_revision: Union[str, None] = "l6m7n8o9p0q1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    if not _column_exists("users", "is_email_verified"):
        op.add_column(
            "users",
            sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    if not _column_exists("users", "email_verified_at"):
        op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))

    # Decision: all existing users become unverified.
    op.execute("UPDATE users SET is_email_verified = false")

    if not _table_exists("email_verification_tokens"):
        op.create_table(
            "email_verification_tokens",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("requested_ip", sa.String(length=64), nullable=True),
            sa.Column("requested_user_agent", sa.String(length=1024), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("email_verification_tokens", "ix_email_verification_tokens_user_id"):
        op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])

    if not _index_exists("email_verification_tokens", "ix_email_verification_tokens_token_hash"):
        op.create_index(
            "ix_email_verification_tokens_token_hash",
            "email_verification_tokens",
            ["token_hash"],
            unique=True,
        )


def downgrade() -> None:
    if _index_exists("email_verification_tokens", "ix_email_verification_tokens_token_hash"):
        op.drop_index("ix_email_verification_tokens_token_hash", table_name="email_verification_tokens")

    if _index_exists("email_verification_tokens", "ix_email_verification_tokens_user_id"):
        op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")

    if _table_exists("email_verification_tokens"):
        op.drop_table("email_verification_tokens")

    if _column_exists("users", "email_verified_at"):
        op.drop_column("users", "email_verified_at")

    if _column_exists("users", "is_email_verified"):
        op.drop_column("users", "is_email_verified")
