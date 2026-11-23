"""The tag table.

Revision ID: 0001_tags
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_tags"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tags_tag",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tags_tag")
