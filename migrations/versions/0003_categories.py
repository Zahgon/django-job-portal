"""The job category table.

Revision ID: 0003_categories
Revises: 0002_accounts
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_categories"
down_revision = "0002_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories_category",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.UniqueConstraint("name", name="categories_category_name_key"),
        sa.UniqueConstraint("slug", name="categories_category_slug_key"),
    )


def downgrade() -> None:
    op.drop_table("categories_category")
