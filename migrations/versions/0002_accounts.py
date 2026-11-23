"""The account table: the e-mail address identifies a person.

Revision ID: 0002_accounts
Revises: 0001_tags
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_accounts"
down_revision = "0001_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts_user",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("password", sa.String(length=128), nullable=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("first_name", sa.String(length=150), nullable=False),
        sa.Column("last_name", sa.String(length=150), nullable=False),
        sa.Column("is_staff", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("date_joined", sa.DateTime(), nullable=False),
        sa.Column("role", sa.String(length=12), nullable=False),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.UniqueConstraint("email", name="accounts_user_email_key"),
    )


def downgrade() -> None:
    op.drop_table("accounts_user")
